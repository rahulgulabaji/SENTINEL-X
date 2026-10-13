"""Tests for GET /v1/incidents/latest/summary/ai -- the AI COPILOT tab's
backend route. Follows the same mongomock + monkeypatched-singleton
convention as test_incidents_latest_summary.py (reuses its fixtures'
shape), plus a fake local HTTP server standing in for api.x.ai (same
technique as test_grok_summary_service.py) for the Grok-success case.

Run from backend/: pytest tests/test_incidents_latest_ai_summary.py -v
"""

from __future__ import annotations

import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import mongomock  # noqa: E402

from app.schemas.analysis import AnalysisResult, AnalysisStatus  # noqa: E402


@pytest.fixture()
def tmp_incident_repo(monkeypatch):
    import app.repositories.incident_repository as incident_repo_module
    from app.repositories.incident_repository import IncidentRepository

    db = mongomock.MongoClient()["sentinel_x_test"]
    repo = IncidentRepository(db)
    monkeypatch.setattr(incident_repo_module, "_repository", repo)
    yield repo
    monkeypatch.setattr(incident_repo_module, "_repository", None)


@pytest.fixture()
def tmp_job_repo(monkeypatch):
    import app.api.routes.analysis as analysis_routes_module
    from app.repositories.mongo_job_repository import MongoJobRepository

    db = mongomock.MongoClient()["sentinel_x_test"]
    repo = MongoJobRepository(db)
    monkeypatch.setattr(analysis_routes_module, "_job_repository", repo)
    yield repo
    monkeypatch.setattr(analysis_routes_module, "_job_repository", None)


@pytest.fixture()
def tmp_grok_service(monkeypatch):
    """Resets the incidents route module's GrokSummaryService singleton so
    each test starts with a clean cache and can swap in its own Settings
    (enabled/disabled, fake-server URL) without leaking across tests."""
    import app.api.routes.incidents as incidents_module

    monkeypatch.setattr(incidents_module, "_grok_summary_service", None)
    yield
    monkeypatch.setattr(incidents_module, "_grok_summary_service", None)


@pytest.fixture()
def client(tmp_incident_repo, tmp_job_repo, tmp_grok_service):
    import app.main as main_module
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def test_no_incidents_returns_null_not_error(client):
    resp = client.get("/api/v1/incidents/latest/summary/ai")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "incident": None,
        "summary": None,
        "ai_summary_text": None,
        "ai_summary_source": None,
        "ai_summary_error": None,
    }


def test_grok_disabled_by_default_returns_fallback_source(client, tmp_job_repo, tmp_incident_repo):
    # Default Settings() has GROK_ENABLED=False -- no env var set in this
    # test process -- so the route must serve the honest fallback, never
    # claim "grok", and never attempt a real network call to api.x.ai.
    job = AnalysisResult(
        job_id="job-fallback",
        status=AnalysisStatus.COMPLETED,
        filename="clip.mp4",
        anomaly_detected=True,
        anomaly_probability=0.95,
        likely_action="Fighting",
        action_confidence=0.385,
    )
    tmp_job_repo.create(job)
    tmp_incident_repo.create_from_job(job)

    resp = client.get("/api/v1/incidents/latest/summary/ai")
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident"]["job_id"] == "job-fallback"
    assert body["summary"]["ai_detected"]["likely_action"] == "Fighting"
    assert body["ai_summary_source"] == "fallback"
    assert body["ai_summary_text"] is not None
    assert "Fighting" in body["ai_summary_text"]
    assert body["ai_summary_error"] is not None
    # The error message may reference the *name* of the env var (that's
    # just documentation of what's missing), but no actual secret value
    # is configured in this test process, so there's nothing to leak --
    # see test_key_never_appears_in_response_even_when_configured for the
    # real "the key's value never appears" property.


def test_key_never_appears_in_response_even_when_configured(client, tmp_job_repo, tmp_incident_repo, monkeypatch):
    import app.api.routes.incidents as incidents_module
    from app.core.config import Settings
    from app.services.grok_summary_service import GrokSummaryService

    secret = "sk-super-secret-value-123"
    settings = Settings(GROK_ENABLED=True, XAI_API_KEY=secret, GROK_TIMEOUT_SECONDS=1.0)
    # Point at a closed local port so the call fails fast (connection
    # refused) and we hit the fallback path -- no real network call.
    monkeypatch.setattr(incidents_module, "_grok_summary_service", GrokSummaryService(settings))
    import app.services.grok_summary_service as grok_mod

    monkeypatch.setattr(grok_mod, "_XAI_CHAT_COMPLETIONS_URL", "http://127.0.0.1:1/v1/chat/completions")

    job = AnalysisResult(job_id="job-key", status=AnalysisStatus.COMPLETED, filename="c.mp4", anomaly_detected=True)
    tmp_job_repo.create(job)
    tmp_incident_repo.create_from_job(job)

    resp = client.get("/api/v1/incidents/latest/summary/ai")
    assert resp.status_code == 200
    assert secret not in resp.text


def _run_fake_server(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, port


def test_grok_success_populates_real_summary_text(client, tmp_job_repo, tmp_incident_repo, monkeypatch):
    class _Ok(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps(
                {"choices": [{"message": {"content": "A real Grok incident summary."}}]}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: ANN002
            pass

    server, thread, port = _run_fake_server(_Ok)
    try:
        import app.api.routes.incidents as incidents_module
        import app.services.grok_summary_service as grok_mod
        from app.core.config import Settings
        from app.services.grok_summary_service import GrokSummaryService

        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        monkeypatch.setattr(incidents_module, "_grok_summary_service", GrokSummaryService(settings))
        monkeypatch.setattr(grok_mod, "_XAI_CHAT_COMPLETIONS_URL", f"http://127.0.0.1:{port}/v1/chat/completions")

        job = AnalysisResult(
            job_id="job-grok-ok",
            status=AnalysisStatus.COMPLETED,
            filename="d.mp4",
            anomaly_detected=True,
            anomaly_probability=0.9,
            likely_action="Shoplifting",
            action_confidence=0.6,
        )
        tmp_job_repo.create(job)
        tmp_incident_repo.create_from_job(job)

        resp = client.get("/api/v1/incidents/latest/summary/ai")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_summary_source"] == "grok"
        assert body["ai_summary_text"] == "A real Grok incident summary."
        assert body["ai_summary_error"] is None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_grok_failure_degrades_to_fallback_not_500(client, tmp_job_repo, tmp_incident_repo, monkeypatch):
    class _ServerError(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server, thread, port = _run_fake_server(_ServerError)
    try:
        import app.api.routes.incidents as incidents_module
        import app.services.grok_summary_service as grok_mod
        from app.core.config import Settings
        from app.services.grok_summary_service import GrokSummaryService

        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        monkeypatch.setattr(incidents_module, "_grok_summary_service", GrokSummaryService(settings))
        monkeypatch.setattr(grok_mod, "_XAI_CHAT_COMPLETIONS_URL", f"http://127.0.0.1:{port}/v1/chat/completions")

        job = AnalysisResult(job_id="job-grok-fail", status=AnalysisStatus.COMPLETED, filename="e.mp4", anomaly_detected=True)
        tmp_job_repo.create(job)
        tmp_incident_repo.create_from_job(job)

        resp = client.get("/api/v1/incidents/latest/summary/ai")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_summary_source"] == "fallback"
        assert body["ai_summary_text"] is not None
        assert body["ai_summary_error"] is not None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_second_request_is_served_from_cache_not_a_second_grok_call(client, tmp_job_repo, tmp_incident_repo, monkeypatch):
    call_count = {"n": 0}

    class _CountingOk(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            call_count["n"] += 1
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps({"choices": [{"message": {"content": "Cached summary."}}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: ANN002
            pass

    server, thread, port = _run_fake_server(_CountingOk)
    try:
        import app.api.routes.incidents as incidents_module
        import app.services.grok_summary_service as grok_mod
        from app.core.config import Settings
        from app.services.grok_summary_service import GrokSummaryService

        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        monkeypatch.setattr(incidents_module, "_grok_summary_service", GrokSummaryService(settings))
        monkeypatch.setattr(grok_mod, "_XAI_CHAT_COMPLETIONS_URL", f"http://127.0.0.1:{port}/v1/chat/completions")

        job = AnalysisResult(job_id="job-cache", status=AnalysisStatus.COMPLETED, filename="f.mp4", anomaly_detected=True)
        tmp_job_repo.create(job)
        tmp_incident_repo.create_from_job(job)

        first = client.get("/api/v1/incidents/latest/summary/ai")
        second = client.get("/api/v1/incidents/latest/summary/ai")

        assert call_count["n"] == 1  # second request served from the service's own cache
        assert first.json()["ai_summary_text"] == second.json()["ai_summary_text"] == "Cached summary."
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_force_refresh_query_param_bypasses_cache(client, tmp_job_repo, tmp_incident_repo, monkeypatch):
    call_count = {"n": 0}

    class _CountingOk(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            call_count["n"] += 1
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps({"choices": [{"message": {"content": f"Summary #{call_count['n']}"}}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: ANN002
            pass

    server, thread, port = _run_fake_server(_CountingOk)
    try:
        import app.api.routes.incidents as incidents_module
        import app.services.grok_summary_service as grok_mod
        from app.core.config import Settings
        from app.services.grok_summary_service import GrokSummaryService

        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        monkeypatch.setattr(incidents_module, "_grok_summary_service", GrokSummaryService(settings))
        monkeypatch.setattr(grok_mod, "_XAI_CHAT_COMPLETIONS_URL", f"http://127.0.0.1:{port}/v1/chat/completions")

        job = AnalysisResult(job_id="job-refresh", status=AnalysisStatus.COMPLETED, filename="g.mp4", anomaly_detected=True)
        tmp_job_repo.create(job)
        tmp_incident_repo.create_from_job(job)

        client.get("/api/v1/incidents/latest/summary/ai")
        resp2 = client.get("/api/v1/incidents/latest/summary/ai?force_refresh=true")

        assert call_count["n"] == 2  # force_refresh made a real second call
        assert resp2.json()["ai_summary_text"] == "Summary #2"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_incident_with_unresolvable_job_still_returns_fallback_summary(client, tmp_incident_repo):
    job = AnalysisResult(
        job_id="job-missing-ai",
        status=AnalysisStatus.COMPLETED,
        filename="h.mp4",
        anomaly_detected=True,
        anomaly_probability=0.5,
        likely_action="Unknown",
        action_confidence=0.5,
    )
    tmp_incident_repo.create_from_job(job)  # NOT persisted to tmp_job_repo

    resp = client.get("/api/v1/incidents/latest/summary/ai")
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident"] is not None
    assert body["summary"]["location"]["available"] is False
    assert body["ai_summary_source"] == "fallback"
    assert "Location: unavailable." in body["ai_summary_text"]


def test_most_recently_created_incident_is_returned(client, tmp_incident_repo, tmp_job_repo):
    older = AnalysisResult(job_id="job-older-ai", status=AnalysisStatus.COMPLETED, filename="a.mp4", anomaly_detected=True)
    newer = AnalysisResult(job_id="job-newer-ai", status=AnalysisStatus.COMPLETED, filename="b.mp4", anomaly_detected=True)
    tmp_job_repo.create(older)
    tmp_job_repo.create(newer)
    tmp_incident_repo.create_from_job(older)
    tmp_incident_repo.create_from_job(newer)

    resp = client.get("/api/v1/incidents/latest/summary/ai")
    body = resp.json()
    assert body["incident"]["job_id"] == "job-newer-ai"


def test_existing_latest_summary_route_still_works_unmodified(client, tmp_incident_repo, tmp_job_repo):
    """Regression: adding /latest/summary/ai must not change the behavior
    of the existing /latest/summary route it shares a helper with."""
    job = AnalysisResult(job_id="job-shared", status=AnalysisStatus.COMPLETED, filename="i.mp4", anomaly_detected=True)
    tmp_job_repo.create(job)
    tmp_incident_repo.create_from_job(job)

    resp = client.get("/api/v1/incidents/latest/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident"]["job_id"] == "job-shared"
    assert "ai_summary_text" not in body
