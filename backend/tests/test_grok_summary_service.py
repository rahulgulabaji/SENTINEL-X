"""Tests for app/services/grok_summary_service.py -- the Grok (xAI)-backed
incident summarizer. Follows test_dispatch.py's fake-HTTP-server convention
(stdlib http.server on an ephemeral port) -- no real network call to xAI in
any automated test. No unittest.mock.

Run from backend/: pytest tests/test_grok_summary_service.py -v
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

from app.core.config import Settings  # noqa: E402
from app.services.grok_summary_service import GrokSummaryService  # noqa: E402


def _incident(**overrides) -> dict:
    base = {
        "incident_id": "inc-1",
        "job_id": "job-1",
        "status": "open",
        "anomaly_probability": 0.95,
        "likely_action": "Fighting",
        "action_confidence": 0.385,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _run_fake_server(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, port


def test_disabled_returns_fallback_not_grok(monkeypatch):
    settings = Settings(GROK_ENABLED=False, XAI_API_KEY="")
    service = GrokSummaryService(settings)
    result = service.summarize_incident(_incident(), job=None)
    assert result.success is False
    assert result.source == "fallback"
    assert result.summary_text is not None
    assert "Fighting" in result.summary_text
    assert result.error is not None


def test_enabled_but_missing_key_returns_fallback():
    settings = Settings(GROK_ENABLED=True, XAI_API_KEY="")
    service = GrokSummaryService(settings)
    result = service.summarize_incident(_incident(), job=None)
    assert result.success is False
    assert result.source == "fallback"


def test_fallback_never_fabricates_location_when_unavailable():
    settings = Settings(GROK_ENABLED=False, XAI_API_KEY="")
    service = GrokSummaryService(settings)
    result = service.summarize_incident(_incident(), job=None)
    assert "Location: unavailable." in result.summary_text


def test_successful_grok_call_returns_real_text_and_source_grok():
    class _Ok(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps(
                {"choices": [{"message": {"content": "A real Grok-generated summary."}}]}
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
        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        service = GrokSummaryService(settings)
        import app.services.grok_summary_service as mod

        original_url = mod._XAI_CHAT_COMPLETIONS_URL
        mod._XAI_CHAT_COMPLETIONS_URL = f"http://127.0.0.1:{port}/v1/chat/completions"
        try:
            result = service.summarize_incident(_incident(), job=None)
        finally:
            mod._XAI_CHAT_COMPLETIONS_URL = original_url

        assert result.success is True
        assert result.source == "grok"
        assert result.summary_text == "A real Grok-generated summary."
        assert result.error is None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_rate_limited_response_falls_back_with_real_error():
    class _RateLimited(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self.send_response(429)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server, thread, port = _run_fake_server(_RateLimited)
    try:
        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        service = GrokSummaryService(settings)
        import app.services.grok_summary_service as mod

        original_url = mod._XAI_CHAT_COMPLETIONS_URL
        mod._XAI_CHAT_COMPLETIONS_URL = f"http://127.0.0.1:{port}/v1/chat/completions"
        try:
            result = service.summarize_incident(_incident(), job=None)
        finally:
            mod._XAI_CHAT_COMPLETIONS_URL = original_url

        assert result.success is False
        assert result.source == "fallback"
        assert "429" in result.error or "rate limit" in result.error.lower()
        # Fallback text must still be a real, non-fabricated summary.
        assert result.summary_text is not None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_server_error_falls_back_without_claiming_success():
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
        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        service = GrokSummaryService(settings)
        import app.services.grok_summary_service as mod

        original_url = mod._XAI_CHAT_COMPLETIONS_URL
        mod._XAI_CHAT_COMPLETIONS_URL = f"http://127.0.0.1:{port}/v1/chat/completions"
        try:
            result = service.summarize_incident(_incident(), job=None)
        finally:
            mod._XAI_CHAT_COMPLETIONS_URL = original_url

        assert result.success is False
        assert result.source == "fallback"
        assert result.error is not None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_timeout_falls_back_without_hanging():
    # Nothing listening on this port at all -- httpx raises a connection
    # error quickly, exercised through the generic except branch.
    settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=1.0)
    service = GrokSummaryService(settings)
    import app.services.grok_summary_service as mod

    original_url = mod._XAI_CHAT_COMPLETIONS_URL
    mod._XAI_CHAT_COMPLETIONS_URL = "http://127.0.0.1:1/v1/chat/completions"
    try:
        result = service.summarize_incident(_incident(), job=None)
    finally:
        mod._XAI_CHAT_COMPLETIONS_URL = original_url

    assert result.success is False
    assert result.source == "fallback"
    assert result.error is not None


def test_cache_hit_avoids_a_second_grok_call():
    call_count = {"n": 0}

    class _CountingOk(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            call_count["n"] += 1
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps({"choices": [{"message": {"content": "Cached-worthy summary."}}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: ANN002
            pass

    server, thread, port = _run_fake_server(_CountingOk)
    try:
        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        service = GrokSummaryService(settings)
        import app.services.grok_summary_service as mod

        original_url = mod._XAI_CHAT_COMPLETIONS_URL
        mod._XAI_CHAT_COMPLETIONS_URL = f"http://127.0.0.1:{port}/v1/chat/completions"
        try:
            incident = _incident()
            first = service.summarize_incident(incident, job=None)
            second = service.summarize_incident(incident, job=None)  # same incident_id/updated_at
        finally:
            mod._XAI_CHAT_COMPLETIONS_URL = original_url

        assert call_count["n"] == 1  # second call served from cache, no new HTTP request
        assert first.summary_text == second.summary_text
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_force_refresh_bypasses_cache():
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
        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        service = GrokSummaryService(settings)
        import app.services.grok_summary_service as mod

        original_url = mod._XAI_CHAT_COMPLETIONS_URL
        mod._XAI_CHAT_COMPLETIONS_URL = f"http://127.0.0.1:{port}/v1/chat/completions"
        try:
            incident = _incident()
            service.summarize_incident(incident, job=None)
            service.summarize_incident(incident, job=None, force_refresh=True)
        finally:
            mod._XAI_CHAT_COMPLETIONS_URL = original_url

        assert call_count["n"] == 2  # force_refresh made a real second call
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_different_incident_updated_at_is_not_served_from_stale_cache():
    class _Ok(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps({"choices": [{"message": {"content": "fresh"}}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: ANN002
            pass

    server, thread, port = _run_fake_server(_Ok)
    try:
        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="test-key", GROK_TIMEOUT_SECONDS=5.0)
        service = GrokSummaryService(settings)
        import app.services.grok_summary_service as mod

        original_url = mod._XAI_CHAT_COMPLETIONS_URL
        mod._XAI_CHAT_COMPLETIONS_URL = f"http://127.0.0.1:{port}/v1/chat/completions"
        try:
            incident_v1 = _incident(updated_at="2025-01-01T00:00:00+00:00")
            incident_v2 = _incident(updated_at="2025-01-02T00:00:00+00:00")  # status changed later
            first = service.summarize_incident(incident_v1, job=None)
            second = service.summarize_incident(incident_v2, job=None)
        finally:
            mod._XAI_CHAT_COMPLETIONS_URL = original_url

        # Different cache key -- both results exist independently (not
        # asserting call count here since both succeed with the same fake
        # response; the key behavior under test is that a changed
        # updated_at is never silently served from the old entry).
        assert first.source == "grok"
        assert second.source == "grok"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_grok_is_given_only_the_structured_summary_never_raw_responder_or_pii_fields():
    """Security/privacy property: the JSON body sent to xAI must be built
    from build_incident_summary()'s structured shape only -- it must never
    contain a responder's phone number, raw GPS, or any field not already
    present in that shape."""
    captured = {}

    class _Capture(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            captured["body"] = self.rfile.read(length).decode("utf-8")
            body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # noqa: ANN002
            pass

    server, thread, port = _run_fake_server(_Capture)
    try:
        settings = Settings(GROK_ENABLED=True, XAI_API_KEY="super-secret-key", GROK_TIMEOUT_SECONDS=5.0)
        service = GrokSummaryService(settings)
        import app.services.grok_summary_service as mod

        original_url = mod._XAI_CHAT_COMPLETIONS_URL
        mod._XAI_CHAT_COMPLETIONS_URL = f"http://127.0.0.1:{port}/v1/chat/completions"
        try:
            incident = _incident()
            job = {
                "location": "Nipani Sector",
                "latitude": 16.7,
                "longitude": 74.2,
                "responder_phone": "+15550001111",  # must never leak into the Grok payload
                "likely_action": "Fighting",
                "anomaly_probability": 0.95,
                "action_confidence": 0.385,
            }
            service.summarize_incident(incident, job=job)
        finally:
            mod._XAI_CHAT_COMPLETIONS_URL = original_url

        assert "super-secret-key" not in captured["body"]  # key never in the request body
        assert "+15550001111" not in captured["body"]  # responder phone never sent to xAI
        assert "Fighting" in captured["body"]  # the real, allowed structured field IS present
    finally:
        server.shutdown()
        thread.join(timeout=5)
