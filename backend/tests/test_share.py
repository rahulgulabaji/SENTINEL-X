"""Tests for the voluntary live-location-sharing (share-link) API.

Same philosophy as test_dispatch.py: mongomock-backed repositories swapped
into the module singletons via monkeypatch, real (local, closed-port or
fake-server) HTTP calls for SMS gateway interaction, no unittest.mock.

Run from backend/: pytest tests/test_share.py -v
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import mongomock  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.share_tokens import hash_token, issue_token, verify_token  # noqa: E402
from app.repositories.responder_repository import MongoResponderRepository  # noqa: E402
from app.repositories.share_session_repository import ShareSessionRepository  # noqa: E402

TEST_SETTINGS = Settings(
    SHARE_SECRET_KEY="test-secret-key-for-share-tokens",
    SHARE_INVITE_TTL_SECONDS=900,
    SHARE_SESSION_MAX_DURATION_SECONDS=7200,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_responder_store(monkeypatch) -> MongoResponderRepository:
    import app.repositories.responder_repository as repo_module

    db = mongomock.MongoClient()["sentinel_x_test"]
    store = MongoResponderRepository(db)
    monkeypatch.setattr(repo_module, "_repository", store)
    yield store
    monkeypatch.setattr(repo_module, "_repository", None)


@pytest.fixture()
def tmp_share_repo(monkeypatch) -> ShareSessionRepository:
    import app.repositories.share_session_repository as share_repo_module

    db = mongomock.MongoClient()["sentinel_x_test"]
    repo = ShareSessionRepository(db)
    monkeypatch.setattr(share_repo_module, "_repository", repo)
    yield repo
    monkeypatch.setattr(share_repo_module, "_repository", None)


@pytest.fixture()
def tmp_sms_store(tmp_path, monkeypatch):
    import app.core.sms_config_store as sms_store_module
    from app.core.sms_config_store import SmsConfigStore, SmsConfigValues

    store = SmsConfigStore(path=tmp_path / "sms.json", seed=SmsConfigValues())
    monkeypatch.setattr(sms_store_module, "_store", store)
    yield store
    monkeypatch.setattr(sms_store_module, "_store", None)


@pytest.fixture()
def tmp_dispatch_repo(monkeypatch):
    import app.repositories.dispatch_repository as dispatch_repo_module
    from app.repositories.dispatch_repository import DispatchRepository

    db = mongomock.MongoClient()["sentinel_x_test"]
    repo = DispatchRepository(db)
    monkeypatch.setattr(dispatch_repo_module, "_repository", repo)
    yield repo
    monkeypatch.setattr(dispatch_repo_module, "_repository", None)


@pytest.fixture()
def tmp_audit_repo(monkeypatch):
    import app.repositories.audit_repository as audit_repo_module
    from app.repositories.audit_repository import AuditRepository

    db = mongomock.MongoClient()["sentinel_x_test"]
    repo = AuditRepository(db)
    monkeypatch.setattr(audit_repo_module, "_repository", repo)
    yield repo
    monkeypatch.setattr(audit_repo_module, "_repository", None)


@pytest.fixture()
def tmp_settings(monkeypatch):
    """Points app.core.config.get_settings() (what the routes actually
    Depends() on) at TEST_SETTINGS, so SHARE_SECRET_KEY/TTLs are
    deterministic across the whole request path -- without this, the
    route layer and this test file could resolve two different random
    fallback keys and no token would ever verify."""
    import app.core.config as config_module

    monkeypatch.setattr(config_module, "_settings", TEST_SETTINGS)
    yield TEST_SETTINGS


@pytest.fixture()
def client(tmp_responder_store, tmp_share_repo, tmp_sms_store, tmp_dispatch_repo, tmp_audit_repo, tmp_settings):
    import app.main as main_module
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def _register(client, *, name="Officer Share", phone_number="+15551230000"):
    resp = client.post("/api/v1/responders", json={"name": name, "phone_number": phone_number})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_session(share_repo, responder_id, *, invite_ttl_seconds=900, settings=TEST_SETTINGS):
    """Direct repository call, bypassing the dispatch SMS flow -- used by
    tests that only care about the /v1/share/* endpoints themselves, not
    the SMS integration."""
    doc, token = share_repo.create(
        responder_id=responder_id,
        dispatch_id="job-test",
        invite_ttl_seconds=invite_ttl_seconds,
        token_factory=lambda sid, rid: issue_token(sid, rid, settings, ttl_seconds=invite_ttl_seconds),
    )
    return doc, token


# ---------------------------------------------------------------------------
# share_tokens.py (pure functions, no Mongo, no FastAPI)
# ---------------------------------------------------------------------------


def test_issue_and_verify_round_trip():
    token = issue_token("sess1", "resp1", TEST_SETTINGS)
    payload = verify_token(token, TEST_SETTINGS)
    assert payload is not None
    assert payload.session_id == "sess1"
    assert payload.responder_id == "resp1"


def test_verify_rejects_tampered_token():
    token = issue_token("sess1", "resp1", TEST_SETTINGS)
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    assert verify_token(tampered, TEST_SETTINGS) is None


def test_verify_rejects_expired_token():
    token = issue_token("sess1", "resp1", TEST_SETTINGS, ttl_seconds=-1)
    assert verify_token(token, TEST_SETTINGS) is None


def test_verify_rejects_malformed_token():
    assert verify_token("not-a-real-token", TEST_SETTINGS) is None
    assert verify_token("", TEST_SETTINGS) is None
    assert verify_token("abc.def.ghi", TEST_SETTINGS) is None


def test_verify_rejects_token_signed_with_different_key():
    other_settings = Settings(SHARE_SECRET_KEY="a-totally-different-key")
    token = issue_token("sess1", "resp1", other_settings)
    assert verify_token(token, TEST_SETTINGS) is None


def test_hash_token_is_deterministic_and_not_reversible_lookalike():
    token = issue_token("sess1", "resp1", TEST_SETTINGS)
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token


# ---------------------------------------------------------------------------
# share_session_repository.py (mongomock, no FastAPI)
# ---------------------------------------------------------------------------


def test_repo_create_starts_pending():
    db = mongomock.MongoClient()["t"]
    repo = ShareSessionRepository(db)
    doc, token = _create_session(repo, "r1")
    assert doc["status"] == "pending"
    assert doc["token_hash"] == hash_token(token)


def test_repo_mark_active_sets_active_until():
    db = mongomock.MongoClient()["t"]
    repo = ShareSessionRepository(db)
    doc, _ = _create_session(repo, "r1")
    activated = repo.mark_active(doc["session_id"], responder_id="r1", active_duration_seconds=7200)
    assert activated["status"] == "active"
    assert activated["active_until"] is not None


def test_repo_mark_active_idempotent():
    db = mongomock.MongoClient()["t"]
    repo = ShareSessionRepository(db)
    doc, _ = _create_session(repo, "r1")
    first = repo.mark_active(doc["session_id"], responder_id="r1", active_duration_seconds=7200)
    second = repo.mark_active(doc["session_id"], responder_id="r1", active_duration_seconds=7200)
    assert first["active_until"] == second["active_until"]  # not reset/extended


def test_repo_mark_active_rejects_wrong_responder():
    db = mongomock.MongoClient()["t"]
    repo = ShareSessionRepository(db)
    doc, _ = _create_session(repo, "r1")
    result = repo.mark_active(doc["session_id"], responder_id="SOMEONE_ELSE", active_duration_seconds=7200)
    assert result is None


def test_repo_record_update_fails_when_not_active():
    db = mongomock.MongoClient()["t"]
    repo = ShareSessionRepository(db)
    doc, _ = _create_session(repo, "r1")  # still pending, never started
    ok = repo.record_update(doc["session_id"], latitude=1.0, longitude=2.0, accuracy_meters=5.0)
    assert ok is False


def test_repo_stop_is_idempotent_and_blocks_further_updates():
    db = mongomock.MongoClient()["t"]
    repo = ShareSessionRepository(db)
    doc, _ = _create_session(repo, "r1")
    repo.mark_active(doc["session_id"], responder_id="r1", active_duration_seconds=7200)
    assert repo.mark_stopped(doc["session_id"]) is True
    assert repo.mark_stopped(doc["session_id"]) is True  # idempotent
    ok = repo.record_update(doc["session_id"], latitude=1.0, longitude=2.0, accuracy_meters=5.0)
    assert ok is False


def test_repo_stop_on_nonexistent_session_returns_false():
    db = mongomock.MongoClient()["t"]
    repo = ShareSessionRepository(db)
    assert repo.mark_stopped("does-not-exist") is False


def test_repo_is_active_expires_timed_out_session():
    db = mongomock.MongoClient()["t"]
    repo = ShareSessionRepository(db)
    doc, _ = _create_session(repo, "r1")
    # active_duration_seconds=0 -> already expired the instant it's activated
    repo.mark_active(doc["session_id"], responder_id="r1", active_duration_seconds=0)
    time.sleep(0.05)
    assert repo.is_active(doc["session_id"]) is None
    assert repo.get(doc["session_id"])["status"] == "expired"


# ---------------------------------------------------------------------------
# /v1/share/* endpoints, full flow (FastAPI + mongomock)
# ---------------------------------------------------------------------------


def test_full_start_location_status_stop_flow(client, tmp_share_repo):
    responder = _register(client, name="Flow Officer")
    _doc, token = _create_session(tmp_share_repo, responder["id"])

    status_resp = client.get(f"/api/v1/share/{token}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "pending"

    start_resp = client.post(f"/api/v1/share/{token}/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["success"] is True

    loc_resp = client.post(
        f"/api/v1/share/{token}/location",
        json={"latitude": 16.7, "longitude": 74.2, "accuracy_meters": 5.0},
    )
    assert loc_resp.status_code == 200
    assert loc_resp.json()["success"] is True

    # Write-through confirmed on the EXISTING responder record/map data.
    responders_resp = client.get("/api/v1/responders")
    updated = next(r for r in responders_resp.json() if r["id"] == responder["id"])
    assert updated["latitude"] == 16.7
    assert updated["longitude"] == 74.2
    assert updated["live_state"] == "live"

    status_resp2 = client.get(f"/api/v1/share/{token}/status")
    assert status_resp2.json()["status"] == "active"
    assert status_resp2.json()["last_lat"] == 16.7

    stop_resp = client.post(f"/api/v1/share/{token}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["success"] is True

    # Further location updates after stop must be rejected.
    loc_resp2 = client.post(
        f"/api/v1/share/{token}/location",
        json={"latitude": 1.0, "longitude": 1.0},
    )
    assert loc_resp2.status_code == 403

    status_resp3 = client.get(f"/api/v1/share/{token}/status")
    assert status_resp3.json()["status"] == "stopped"


def test_share_page_served_as_html(client, tmp_share_repo):
    responder = _register(client, name="Page Officer")
    _doc, token = _create_session(tmp_share_repo, responder["id"])

    resp = client.get(f"/api/v1/share/{token}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Start Sharing" in resp.text
    assert token in resp.text  # embedded for the page's own JS to call back with


def test_invalid_token_rejected_everywhere(client):
    bad = "not.a.real.token"
    assert client.get(f"/api/v1/share/{bad}/status").status_code == 403
    assert client.post(f"/api/v1/share/{bad}/start").status_code == 403
    assert client.post(f"/api/v1/share/{bad}/location", json={"latitude": 1, "longitude": 1}).status_code == 403
    assert client.post(f"/api/v1/share/{bad}/stop").status_code == 403


def test_tampered_token_rejected(client, tmp_share_repo):
    responder = _register(client, name="Tamper Officer")
    _doc, token = _create_session(tmp_share_repo, responder["id"])
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]

    resp = client.post(f"/api/v1/share/{tampered}/start")
    assert resp.status_code == 403


def test_expired_invite_token_rejected_at_start(client, tmp_share_repo):
    responder = _register(client, name="Expired Officer")
    _doc, token = _create_session(tmp_share_repo, responder["id"], invite_ttl_seconds=-1)

    resp = client.post(f"/api/v1/share/{token}/start")
    assert resp.status_code == 403


def test_location_rejected_before_start(client, tmp_share_repo):
    """A valid, unexpired token that has never called /start must still be
    rejected by /location -- opening the link does not itself start
    sharing (explicit consent requirement)."""
    responder = _register(client, name="No Start Officer")
    _doc, token = _create_session(tmp_share_repo, responder["id"])

    resp = client.post(
        f"/api/v1/share/{token}/location",
        json={"latitude": 1.0, "longitude": 1.0},
    )
    assert resp.status_code == 403


def test_out_of_range_coordinates_rejected(client, tmp_share_repo):
    responder = _register(client, name="Range Officer")
    _doc, token = _create_session(tmp_share_repo, responder["id"])
    client.post(f"/api/v1/share/{token}/start")

    resp = client.post(f"/api/v1/share/{token}/location", json={"latitude": 999.0, "longitude": 1.0})
    assert resp.status_code == 422

    resp2 = client.post(f"/api/v1/share/{token}/location", json={"latitude": 1.0, "longitude": -999.0})
    assert resp2.status_code == 422


def test_stop_is_safe_even_without_ever_starting(client, tmp_share_repo):
    responder = _register(client, name="Direct Stop Officer")
    _doc, token = _create_session(tmp_share_repo, responder["id"])

    resp = client.post(f"/api/v1/share/{token}/stop")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_second_responder_cannot_use_first_responders_session_token(client, tmp_share_repo):
    """A token's session is bound to one specific responder_id -- another
    responder's own, otherwise-valid session cannot be hijacked by mixing
    identifiers (defense-in-depth; in practice tokens are opaque and this
    mainly guards against a future bug reusing session_ids)."""
    r1 = _register(client, name="Officer One")
    r2 = _register(client, name="Officer Two")
    doc1, _token1 = _create_session(tmp_share_repo, r1["id"])

    # Forge a token for r1's session_id but claiming to be r2.
    forged = issue_token(doc1["session_id"], r2["id"], TEST_SETTINGS)
    resp = client.post(f"/api/v1/share/{forged}/start")
    assert resp.status_code == 403


def test_rate_limit_triggers_on_rapid_abuse(client, tmp_share_repo):
    responder = _register(client, name="Flood Officer")
    _doc, token = _create_session(tmp_share_repo, responder["id"])

    statuses = [client.get(f"/api/v1/share/{token}/status").status_code for _ in range(30)]
    assert 429 in statuses, "expected the rate limiter to kick in under rapid repeated requests"


# ---------------------------------------------------------------------------
# SMS integration: dispatch/send includes a share link
# ---------------------------------------------------------------------------


def test_dispatch_send_sms_includes_incident_location_not_share_link(client, tmp_sms_store, monkeypatch):
    """The responder's own location is already tracked continuously from
    their duty-session GPS stream, so dispatch/send no longer mints a share
    session or asks them to share their location -- it appends a short
    Google Maps link to the INCIDENT's coordinates instead."""
    import http.server

    import app.core.config as config_module

    captured = {}

    class _Capture(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            captured["body"] = body.decode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Capture)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # PUBLIC_BASE_URL must still be set for other share features (duty
        # sessions etc.) -- irrelevant to this test but kept for parity with
        # a realistic configured deployment.
        settings_with_url = Settings(
            SHARE_SECRET_KEY=TEST_SETTINGS.SHARE_SECRET_KEY,
            SHARE_INVITE_TTL_SECONDS=TEST_SETTINGS.SHARE_INVITE_TTL_SECONDS,
            SHARE_SESSION_MAX_DURATION_SECONDS=TEST_SETTINGS.SHARE_SESSION_MAX_DURATION_SECONDS,
            PUBLIC_BASE_URL="https://example-tunnel.ngrok-free.app",
        )
        monkeypatch.setattr(config_module, "_settings", settings_with_url)

        tmp_sms_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="pw")
        created = _register(client, name="Linked Officer", phone_number="+15550008888")
        client.post(
            f"/api/v1/responders/{created['id']}/location",
            json={"latitude": 16.7, "longitude": 74.2},
        )

        resp = client.post(
            "/api/v1/dispatch/send",
            json={
                "responder_id": created["id"],
                "incident_type": "Test",
                "job_id": "job-link",
                "latitude": 16.4044521,
                "longitude": 74.3790313,
            },
        )
        assert resp.json()["success"] is True
        assert "maps.google.com/?q=16.4044521,74.3790313" in captured["body"]
        assert "/api/v1/share/" not in captured["body"]
        assert "Start Sharing" not in captured["body"]
        assert "Share your live location" not in captured["body"]
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_dispatch_send_sms_omits_location_line_when_coordinates_missing(client, tmp_sms_store):
    """Fail-open: an older client that hasn't been updated to send
    latitude/longitude yet still gets its incident SMS sent, just without
    the location link -- a missing link must never block the SMS."""
    import http.server

    captured = {}

    class _Capture(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            captured["body"] = body.decode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Capture)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        tmp_sms_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="pw")
        created = _register(client, name="No Coords Officer", phone_number="+15550009999")
        client.post(
            f"/api/v1/responders/{created['id']}/location",
            json={"latitude": 16.7, "longitude": 74.2},
        )

        resp = client.post(
            "/api/v1/dispatch/send",
            json={"responder_id": created["id"], "incident_type": "Test", "job_id": "job-nolink"},
        )
        assert resp.json()["success"] is True
        assert "maps.google.com" not in captured["body"]
        assert "Incident location:" not in captured["body"]
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_dispatch_send_without_public_base_url_omits_link(client, tmp_sms_store, monkeypatch):
    """PUBLIC_BASE_URL unset -- dispatch must still succeed (never block the
    real incident SMS), just without a share link appended. Explicitly
    overridden to "" rather than relying on the ambient Settings default,
    since a developer's local .env may legitimately have a real
    PUBLIC_BASE_URL configured (e.g. for manual ngrok testing)."""
    import http.server

    import app.core.config as config_module

    settings_without_url = Settings(
        SHARE_SECRET_KEY=TEST_SETTINGS.SHARE_SECRET_KEY,
        SHARE_INVITE_TTL_SECONDS=TEST_SETTINGS.SHARE_INVITE_TTL_SECONDS,
        SHARE_SESSION_MAX_DURATION_SECONDS=TEST_SETTINGS.SHARE_SESSION_MAX_DURATION_SECONDS,
        PUBLIC_BASE_URL="",
    )
    monkeypatch.setattr(config_module, "_settings", settings_without_url)

    captured = {}

    class _Capture(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            captured["body"] = self.rfile.read(length).decode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Capture)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        tmp_sms_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="pw")
        created = _register(client, name="No Link Officer", phone_number="+15550006666")
        client.post(
            f"/api/v1/responders/{created['id']}/location",
            json={"latitude": 16.7, "longitude": 74.2},
        )

        resp = client.post(
            "/api/v1/dispatch/send",
            json={"responder_id": created["id"], "incident_type": "Test", "job_id": "job-nolink"},
        )
        assert resp.json()["success"] is True
        assert "http" not in captured["body"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
