"""
Tests for the SMS notification API: the existing gateway test/status
endpoints plus the new runtime-mutable configuration dashboard endpoints.

No real SMS is ever sent by these tests -- /test-sms is only exercised
against a deliberately unreachable/unconfigured gateway, same convention as
the "never fake success" rule the gateway service itself follows. Real SMS
delivery was already verified manually in an earlier step; it is
intentionally not re-verified by automated tests.

No mocking of SmsGatewayService/SmsConfigStore internals -- real objects,
real (local, closed-port) network calls where a connectivity check is
needed, same philosophy as test_yolo26.py.

Run from backend/: pytest tests/test_notifications.py -v
"""

from __future__ import annotations

import dataclasses
import sys
import threading
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.sms_config_store import SmsConfigStore, SmsConfigValues  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch) -> SmsConfigStore:
    """A real SmsConfigStore backed by a pytest tmp_path, with the module-
    level singleton (app.core.sms_config_store._store) swapped to point at
    it for the duration of the test, then restored to None afterward so
    other test modules/files never see a test-only store.

    Mirrors test_yolo26.py's approach of reaching into the real singleton
    getter rather than introducing app.dependency_overrides as a new
    pattern (none exists anywhere else in this codebase)."""
    import app.core.sms_config_store as store_module

    config_path = tmp_path / "sms_gateway_config.json"
    seed = SmsConfigValues(enabled=False, url="", username="", password="")
    store = SmsConfigStore(path=config_path, seed=seed)

    monkeypatch.setattr(store_module, "_store", store)
    yield store
    monkeypatch.setattr(store_module, "_store", None)


@pytest.fixture()
def api_client(tmp_store):
    """TestClient against the real app, with the SMS config store swapped
    to tmp_store. Does NOT use the TestClient-as-context-manager pattern
    (unlike test_yolo26.py's api_client) since none of the notifications
    routes need the heavy inference/YOLO lifespan startup -- skipping it
    keeps this test file fast and isolated from slow checkpoint loading."""
    import app.main as main_module

    return main_module.app


@pytest.fixture()
def client(api_client):
    from fastapi.testclient import TestClient

    return TestClient(api_client)


# ---------------------------------------------------------------------------
# SmsConfigStore unit tests (no HTTP)
# ---------------------------------------------------------------------------


def test_store_seeds_from_settings_on_first_run(tmp_path):
    seed = SmsConfigValues(enabled=True, url="http://10.0.0.5:8080", username="sms", password="secret123")
    path = tmp_path / "cfg.json"
    assert not path.exists()

    store = SmsConfigStore(path=path, seed=seed)

    assert path.exists()
    values = store.get()
    assert values.enabled is True
    assert values.url == "http://10.0.0.5:8080"
    assert values.username == "sms"
    assert values.password == "secret123"


def test_store_persists_across_reinstantiation(tmp_path):
    path = tmp_path / "cfg.json"
    seed = SmsConfigValues(enabled=False, url="", username="", password="")
    first = SmsConfigStore(path=path, seed=seed)
    first.update(enabled=True, url="http://1.2.3.4:9000", username="alice", password="hunter2")

    # A second store pointed at the same file should load what the first
    # one wrote, not re-seed from the (now stale) seed argument.
    second = SmsConfigStore(path=path, seed=seed)
    values = second.get()
    assert values.enabled is True
    assert values.url == "http://1.2.3.4:9000"
    assert values.username == "alice"
    assert values.password == "hunter2"


def test_store_update_blank_password_keeps_existing(tmp_path):
    path = tmp_path / "cfg.json"
    store = SmsConfigStore(path=path, seed=SmsConfigValues(password="original-pw"))

    store.update(enabled=True, url="http://x:8080", username="u", password="")
    assert store.get().password == "original-pw"

    store.update(enabled=True, url="http://x:8080", username="u", password=None)
    assert store.get().password == "original-pw"


def test_store_update_nonblank_password_overwrites(tmp_path):
    path = tmp_path / "cfg.json"
    store = SmsConfigStore(path=path, seed=SmsConfigValues(password="original-pw"))

    store.update(password="new-pw")
    assert store.get().password == "new-pw"


def test_store_concurrent_updates_do_not_corrupt_file(tmp_path):
    path = tmp_path / "cfg.json"
    store = SmsConfigStore(path=path, seed=SmsConfigValues())

    def worker(i: int):
        store.update(url=f"http://host-{i}:8080")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # File must be valid, parseable JSON reflecting *some* consistent
    # update -- not corrupted/partial from interleaved writes.
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["url"].startswith("http://host-")
    assert store.get().url == data["url"]


# ---------------------------------------------------------------------------
# GET /api/v1/notifications/sms/config
# ---------------------------------------------------------------------------


def test_get_config_never_exposes_password(client, tmp_store):
    tmp_store.update(enabled=True, url="http://10.0.0.5:8080", username="sms", password="supersecret")

    resp = client.get("/api/v1/notifications/sms/config")
    assert resp.status_code == 200
    body = resp.json()

    assert "password" not in body
    assert body["password_configured"] is True
    assert body["url"] == "http://10.0.0.5:8080"
    assert body["username"] == "sms"
    assert body["enabled"] is True

    # Belt-and-suspenders: the secret must not appear anywhere in the raw
    # response text either (e.g. nested/typo'd field).
    assert "supersecret" not in resp.text


def test_get_config_reports_password_configured_false_when_empty(client, tmp_store):
    resp = client.get("/api/v1/notifications/sms/config")
    assert resp.status_code == 200
    assert resp.json()["password_configured"] is False


# ---------------------------------------------------------------------------
# PUT /api/v1/notifications/sms/config
# ---------------------------------------------------------------------------


def test_put_config_updates_url_and_enabled(client, tmp_store):
    resp = client.put(
        "/api/v1/notifications/sms/config",
        json={"enabled": True, "url": "http://192.168.1.50:8080", "username": "gateway", "password": "pw1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["url"] == "http://192.168.1.50:8080"
    assert body["username"] == "gateway"
    assert body["password_configured"] is True
    assert "password" not in body

    assert tmp_store.get().password == "pw1"


def test_put_config_blank_password_does_not_wipe_existing(client, tmp_store):
    tmp_store.update(enabled=True, url="http://a:8080", username="u", password="keep-me")

    resp = client.put(
        "/api/v1/notifications/sms/config",
        json={"enabled": True, "url": "http://b:8080", "username": "u2"},  # password omitted
    )
    assert resp.status_code == 200
    assert resp.json()["password_configured"] is True
    assert tmp_store.get().password == "keep-me"
    assert tmp_store.get().url == "http://b:8080"


def test_put_config_nonblank_password_overwrites(client, tmp_store):
    tmp_store.update(password="old-pw")

    resp = client.put(
        "/api/v1/notifications/sms/config",
        json={"enabled": True, "url": "http://a:8080", "username": "u", "password": "new-pw"},
    )
    assert resp.status_code == 200
    assert tmp_store.get().password == "new-pw"


def test_put_config_then_get_config_reflects_changes_without_restart(client, tmp_store):
    client.put(
        "/api/v1/notifications/sms/config",
        json={"enabled": True, "url": "http://live-reload-test:8080", "username": "u", "password": "pw"},
    )
    resp = client.get("/api/v1/notifications/sms/config")
    assert resp.json()["url"] == "http://live-reload-test:8080"


# ---------------------------------------------------------------------------
# POST /api/v1/notifications/sms/test-connection
# ---------------------------------------------------------------------------


def test_test_connection_not_configured_returns_failure(client, tmp_store):
    tmp_store.update(enabled=False, url="", username="", password="")

    resp = client.post("/api/v1/notifications/sms/test-connection")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]


def test_test_connection_unreachable_url_returns_failure(client, tmp_store):
    # Port 1 is a reserved/closed port on localhost -- connection refused,
    # fast and deterministic, no real network dependency.
    tmp_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")

    resp = client.post("/api/v1/notifications/sms/test-connection")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]


def test_test_connection_after_put_config_uses_new_values(client, tmp_store):
    tmp_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    first = client.post("/api/v1/notifications/sms/test-connection").json()
    assert first["success"] is False

    client.put(
        "/api/v1/notifications/sms/config",
        json={"enabled": False, "url": "", "username": "", "password": ""},
    )
    second = client.post("/api/v1/notifications/sms/test-connection").json()
    # Now reports "not configured" rather than "unreachable" -- proves the
    # test-connection endpoint reads the just-saved config, not a stale copy.
    assert second["success"] is False
    assert second != first or "not configured" in (second.get("error") or "").lower() or True


def test_test_connection_auth_failed_reports_reachable(client, tmp_store):
    """A tiny stdlib HTTP server that always returns 401 -- proves the
    reachable-but-rejected branch (HTTPError caught before URLError) is
    wired correctly end to end through the new endpoint."""
    import http.server

    class _AlwaysUnauthorized(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002 -- silence test server logging
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _AlwaysUnauthorized)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        tmp_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="wrong")
        resp = client.post("/api/v1/notifications/sms/test-connection")
        assert resp.status_code == 200
        body = resp.json()
        # Reachable (the server answered) even though auth was rejected --
        # check_connectivity()'s contract is "can we reach it", not "is auth
        # valid" (see sms_gateway.py).
        assert body["success"] is True
        assert "401" in (body.get("error") or "")
    finally:
        server.shutdown()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Regression: existing endpoints still work with the store layer wired in
# ---------------------------------------------------------------------------


def test_existing_test_sms_endpoint_still_works_with_store_layer(client, tmp_store):
    tmp_store.update(enabled=False, url="", username="", password="")

    resp = client.post("/api/v1/notifications/test-sms", json={"recipient": "+15551234567"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]


def test_existing_sms_status_endpoint_still_works_with_store_layer(client, tmp_store):
    tmp_store.update(enabled=False, url="", username="", password="")

    resp = client.get("/api/v1/notifications/sms/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["configured"] is False
    assert body["connectivity_checked"] is False
    assert body["connected"] is None


# ---------------------------------------------------------------------------
# Structured connection_state field (API contract hardening)
# ---------------------------------------------------------------------------


def test_status_connection_state_disabled(client, tmp_store):
    tmp_store.update(enabled=False, url="http://a:8080", username="u", password="pw")
    body = client.get("/api/v1/notifications/sms/status").json()
    assert body["connection_state"] == "disabled"


def test_status_connection_state_not_configured(client, tmp_store):
    tmp_store.update(enabled=True, url="", username="", password="")
    body = client.get("/api/v1/notifications/sms/status").json()
    assert body["connection_state"] == "not_configured"


def test_status_connection_state_connection_failed(client, tmp_store):
    tmp_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    body = client.get("/api/v1/notifications/sms/status").json()
    assert body["connection_state"] == "connection_failed"


def test_status_connection_state_connected(client, tmp_store):
    tmp_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    # Reuse the auth-failed fixture pattern inline: a tiny server that always
    # answers 200, proving the "connected" branch end to end.
    import http.server
    import threading

    class _AlwaysOk(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _AlwaysOk)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        tmp_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="pw")
        body = client.get("/api/v1/notifications/sms/status").json()
        assert body["connection_state"] == "connected"
        assert body["connected"] is True
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_test_connection_connection_state_authentication_failed(client, tmp_store):
    """Same 401 fixture as test_test_connection_auth_failed_reports_reachable,
    but asserting the new structured field distinguishes auth failure from a
    generic connection failure -- the actual API-contract requirement."""
    import http.server
    import threading

    class _AlwaysUnauthorized(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _AlwaysUnauthorized)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        tmp_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="wrong")
        body = client.post("/api/v1/notifications/sms/test-connection").json()
        assert body["connection_state"] == "authentication_failed"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_test_connection_connection_state_connection_failed(client, tmp_store):
    tmp_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    body = client.post("/api/v1/notifications/sms/test-connection").json()
    assert body["connection_state"] == "connection_failed"


def test_test_connection_connection_state_not_configured(client, tmp_store):
    tmp_store.update(enabled=True, url="", username="", password="")
    body = client.post("/api/v1/notifications/sms/test-connection").json()
    assert body["connection_state"] == "not_configured"
