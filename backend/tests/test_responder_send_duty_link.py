"""Tests for POST /v1/responders/{id}/send-duty-link.

Verifies the real message (officer name + actual duty-page URL) is what
gets sent through the SMS gateway -- the bug this endpoint fixes is the
frontend's previous fallback onto POST /v1/notifications/test-sms, which
always sent a hardcoded "SENTINEL-X test notification." body regardless of
what message the caller intended.

Same fixture conventions as test_dispatch.py / test_share.py: mongomock
-backed repositories, a tiny stdlib HTTP server standing in for the SMS
gateway, no unittest.mock.

Run from backend/: pytest tests/test_responder_send_duty_link.py -v
"""

from __future__ import annotations

import http.server
import sys
import threading
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import mongomock  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.repositories.responder_repository import MongoResponderRepository  # noqa: E402

TEST_SETTINGS = Settings(PUBLIC_BASE_URL="https://field.sentinel-x.example")


@pytest.fixture()
def tmp_responder_store(monkeypatch) -> MongoResponderRepository:
    import app.repositories.responder_repository as repo_module

    db = mongomock.MongoClient()["sentinel_x_test"]
    store = MongoResponderRepository(db)
    monkeypatch.setattr(repo_module, "_repository", store)
    yield store
    monkeypatch.setattr(repo_module, "_repository", None)


@pytest.fixture()
def tmp_sms_store(tmp_path, monkeypatch):
    import app.core.sms_config_store as sms_store_module
    from app.core.sms_config_store import SmsConfigStore, SmsConfigValues

    store = SmsConfigStore(path=tmp_path / "sms.json", seed=SmsConfigValues())
    monkeypatch.setattr(sms_store_module, "_store", store)
    yield store
    monkeypatch.setattr(sms_store_module, "_store", None)


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
    import app.core.config as config_module

    monkeypatch.setattr(config_module, "_settings", TEST_SETTINGS)
    yield TEST_SETTINGS


@pytest.fixture()
def client(tmp_responder_store, tmp_sms_store, tmp_audit_repo, tmp_settings):
    import app.main as main_module
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def _register(client, *, name="Officer Link", phone_number="+15559990001"):
    resp = client.post("/api/v1/responders", json={"name": name, "phone_number": phone_number})
    assert resp.status_code == 201, resp.text
    return resp.json()


class _CapturingHandler(http.server.BaseHTTPRequestHandler):
    """Always returns 200, and stashes the raw POST body on the class so
    the test can inspect exactly what message text was actually sent."""

    captured_body: bytes | None = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _CapturingHandler.captured_body = self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):  # noqa: ANN002
        pass


def test_send_duty_link_sends_real_message_not_generic_test_notification(client, tmp_sms_store):
    _CapturingHandler.captured_body = None
    server = http.server.HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        tmp_sms_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="pw")
        created = _register(client, name="Officer Duty Link", phone_number="+15559990002")

        resp = client.post(f"/api/v1/responders/{created['id']}/send-duty-link")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["duty_url"] == f"https://field.sentinel-x.example/responder/duty/{created['id']}"

        # The actual bug this fixes: the message sent to the gateway must
        # be the real duty-link text, never the hardcoded
        # "SENTINEL-X test notification." string the old test-sms fallback
        # always sent regardless of what the caller intended.
        assert _CapturingHandler.captured_body is not None
        sent_payload = _CapturingHandler.captured_body.decode("utf-8", errors="replace")
        assert "test notification" not in sent_payload.lower()
        assert "Officer Duty Link" in sent_payload
        assert created["id"] in sent_payload
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_send_duty_link_unknown_responder_returns_404(client):
    resp = client.post("/api/v1/responders/does-not-exist/send-duty-link")
    assert resp.status_code == 404


def test_send_duty_link_without_phone_number_returns_400(client):
    resp = client.post("/api/v1/responders", json={"name": "No Phone Officer"})
    assert resp.status_code == 201
    created = resp.json()

    resp = client.post(f"/api/v1/responders/{created['id']}/send-duty-link")
    assert resp.status_code == 400
    assert "phone number" in resp.text.lower()


def test_send_duty_link_without_public_base_url_returns_503(client, tmp_sms_store, monkeypatch):
    import app.core.config as config_module

    no_base_url_settings = Settings(PUBLIC_BASE_URL="")
    monkeypatch.setattr(config_module, "_settings", no_base_url_settings)
    tmp_sms_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")

    created = _register(client)
    resp = client.post(f"/api/v1/responders/{created['id']}/send-duty-link")
    assert resp.status_code == 503


def test_send_duty_link_reports_gateway_failure_truthfully(client, tmp_sms_store):
    # Deliberately unreachable gateway (closed local port).
    tmp_sms_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    created = _register(client, name="Unreachable Gateway Officer", phone_number="+15559990003")

    resp = client.post(f"/api/v1/responders/{created['id']}/send-duty-link")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]  # truthful failure, not a fabricated success
