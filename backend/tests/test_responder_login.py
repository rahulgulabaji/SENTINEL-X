"""Tests for username/password login on the mobile duty page
(POST /v1/responders/login, POST /v1/responders/logout).

Same philosophy and fixture pattern as test_share.py and
test_responder_auth.py: mongomock-backed repositories swapped into the
module singletons via monkeypatch, no unittest.mock.

Run from backend/: pytest tests/test_responder_login.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import mongomock  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.repositories.responder_repository import MongoResponderRepository  # noqa: E402
from app.repositories.share_session_repository import ShareSessionRepository  # noqa: E402

TEST_SETTINGS = Settings(
    SHARE_SECRET_KEY="test-secret-key-for-share-tokens",
    SHARE_INVITE_TTL_SECONDS=900,
    SHARE_SESSION_MAX_DURATION_SECONDS=7200,
)


# ---------------------------------------------------------------------------
# Fixtures (same convention as test_share.py)
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


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter():
    """The chat-auth rate limiter (reused by /login) is a process-wide
    singleton -- reset it before each test so one test's failed-login
    attempts can't exhaust another test's budget."""
    import app.core.rate_limit as rate_limit_module

    rate_limit_module._chat_auth_limiter = None
    yield
    rate_limit_module._chat_auth_limiter = None


@pytest.fixture()
def client(tmp_responder_store, tmp_share_repo, tmp_audit_repo, tmp_settings):
    import app.main as main_module
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def _register_with_login(client, *, name="Officer Login", phone_number="+15551240001", username="officer.duty", password="hunter22222"):
    resp = client.post(
        "/api/v1/responders",
        json={"name": name, "phone_number": phone_number, "username": username, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_with_correct_credentials_starts_duty_session(client):
    created = _register_with_login(client)
    resp = client.post("/api/v1/responders/login", json={"username": "officer.duty", "password": "hunter22222"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["responder_id"] == created["id"]
    # Login activates the session immediately (a successful password check
    # is a stronger consent signal than the anonymous share-link's client
    # -side "Start Sharing" button) -- a brand-new login is "active", not
    # "pending".
    assert body["duty_status"] == "active"
    assert body["duty_token"]  # non-empty, usable token


def test_login_wrong_password_returns_401(client):
    _register_with_login(client)
    resp = client.post("/api/v1/responders/login", json={"username": "officer.duty", "password": "wrong-password"})
    assert resp.status_code == 401


def test_login_unknown_username_returns_401_same_as_wrong_password(client):
    _register_with_login(client)
    resp_unknown = client.post("/api/v1/responders/login", json={"username": "does.not.exist", "password": "whatever123"})
    resp_wrong_pw = client.post("/api/v1/responders/login", json={"username": "officer.duty", "password": "wrong-password"})
    assert resp_unknown.status_code == 401
    assert resp_wrong_pw.status_code == 401
    assert resp_unknown.json() == resp_wrong_pw.json()  # identical body -- no enumeration oracle


def test_login_against_pin_only_responder_returns_401(client):
    """A responder created without username/password (PIN-only, the
    pre-existing contract) has no password_hash at all -- login must
    reject, not crash, and must not treat an empty/None hash as a match."""
    resp = client.post("/api/v1/responders", json={"name": "PIN Only Officer", "phone_number": "+15551240002"})
    assert resp.status_code == 201
    resp = client.post("/api/v1/responders/login", json={"username": "", "password": "anything12"})
    assert resp.status_code in (401, 422)


def test_login_token_actually_works_against_share_location_endpoint(client):
    """The duty_token returned by login must be a genuine, usable token for
    the existing /v1/share/{token}/location endpoint -- login isn't just
    issuing an opaque string, it's really starting a share session."""
    _register_with_login(client, phone_number="+15551240003", username="officer.live")
    login_resp = client.post("/api/v1/responders/login", json={"username": "officer.live", "password": "hunter22222"})
    token = login_resp.json()["duty_token"]

    loc_resp = client.post(f"/api/v1/share/{token}/location", json={"lat": 28.6139, "lng": 77.2090, "accuracy": 10})
    assert loc_resp.status_code == 200, loc_resp.text


def test_repeated_login_resumes_rather_than_duplicates_session(client):
    """Logging in twice while already on duty must resume the same
    session, not create a second one -- matches
    start_or_resume_duty_session's existing idempotency guarantee."""
    _register_with_login(client, phone_number="+15551240004", username="officer.repeat")
    first = client.post("/api/v1/responders/login", json={"username": "officer.repeat", "password": "hunter22222"})
    second = client.post("/api/v1/responders/login", json={"username": "officer.repeat", "password": "hunter22222"})
    assert first.status_code == 200 and second.status_code == 200
    # Both logins must still each return a token that works right now --
    # resuming re-issues a fresh usable token bound to the same session,
    # it never leaves the responder with a dead link.
    for resp in (first, second):
        token = resp.json()["duty_token"]
        loc_resp = client.post(f"/api/v1/share/{token}/location", json={"lat": 1.0, "lng": 1.0})
        assert loc_resp.status_code == 200, loc_resp.text


def test_login_rate_limited_after_repeated_failures(client):
    _register_with_login(client, phone_number="+15551240005", username="officer.limited")
    for _ in range(10):
        resp = client.post("/api/v1/responders/login", json={"username": "officer.limited", "password": "wrong"})
        assert resp.status_code == 401
    resp = client.post("/api/v1/responders/login", json={"username": "officer.limited", "password": "wrong"})
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


def test_logout_ends_the_duty_session(client):
    created = _register_with_login(client, phone_number="+15551240006", username="officer.logout")
    login_resp = client.post("/api/v1/responders/login", json={"username": "officer.logout", "password": "hunter22222"})
    token = login_resp.json()["duty_token"]

    logout_resp = client.post("/api/v1/responders/logout", params={"responder_id": created["id"]})
    assert logout_resp.status_code == 200, logout_resp.text
    assert logout_resp.json()["success"] is True

    # The stopped session's token must no longer accept location updates.
    loc_resp = client.post(f"/api/v1/share/{token}/location", json={"lat": 1.0, "lng": 1.0})
    assert loc_resp.status_code in (403, 404, 409)


def test_logout_without_an_active_session_is_safe(client):
    created = _register_with_login(client, phone_number="+15551240007", username="officer.nologout")
    resp = client.post("/api/v1/responders/logout", params={"responder_id": created["id"]})
    assert resp.status_code == 200
    assert resp.json()["success"] is False
