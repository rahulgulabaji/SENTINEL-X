"""Tests for per-responder PIN auth (app/core/responder_auth.py) and the
PIN issuance/reissue surface on app/api/routes/responders.py.

Same philosophy as test_share.py: mongomock-backed repositories swapped
into the module singletons via monkeypatch, no unittest.mock.

Run from backend/: pytest tests/test_responder_auth.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import mongomock  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.responder_auth import generate_pin, hash_password, hash_pin, verify_password, verify_pin  # noqa: E402
from app.repositories.responder_repository import MongoResponderRepository  # noqa: E402

TEST_SETTINGS = Settings()


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
def tmp_settings(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module, "_settings", TEST_SETTINGS)
    yield TEST_SETTINGS


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
def client(tmp_responder_store, tmp_audit_repo, tmp_settings):
    import app.main as main_module
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def _register(client, *, name="Officer Auth", phone_number="+15551230001"):
    resp = client.post("/api/v1/responders", json={"name": name, "phone_number": phone_number})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# responder_auth.py (pure functions, no Mongo, no FastAPI)
# ---------------------------------------------------------------------------


def test_generate_pin_is_six_digits():
    pin = generate_pin()
    assert len(pin) == 6
    assert pin.isdigit()


def test_generate_pin_is_random_across_calls():
    pins = {generate_pin() for _ in range(20)}
    # Astronomically unlikely to collide 20 times in a row if this were
    # broken (e.g. always returning the same value).
    assert len(pins) > 1


def test_hash_and_verify_round_trip():
    pin = generate_pin()
    pin_hash = hash_pin(pin)
    assert verify_pin(pin, pin_hash) is True


def test_verify_rejects_wrong_pin():
    pin = generate_pin()
    pin_hash = hash_pin(pin)
    wrong = "000000" if pin != "000000" else "111111"
    assert verify_pin(wrong, pin_hash) is False


def test_verify_rejects_malformed_hash():
    # Never raises -- a corrupted/missing hash is just a failed check.
    assert verify_pin("123456", "not-a-real-argon2-hash") is False


def test_hash_is_argon2id_not_plain_sha256():
    pin_hash = hash_pin("123456")
    assert pin_hash.startswith("$argon2id$")


def test_hash_includes_a_random_salt():
    # Same PIN, hashed twice, must produce two different hashes (because
    # of Argon2's own per-hash random salt) -- a bare sha256 would not.
    h1 = hash_pin("123456")
    h2 = hash_pin("123456")
    assert h1 != h2
    assert verify_pin("123456", h1) is True
    assert verify_pin("123456", h2) is True


# ---------------------------------------------------------------------------
# Route-level: PIN issuance at creation, reissue, never re-exposed later
# ---------------------------------------------------------------------------


def test_create_responder_returns_pin(client):
    body = _register(client)
    assert "pin" in body
    assert len(body["pin"]) == 6
    assert body["pin"].isdigit()


def test_get_responder_never_includes_pin(client):
    created = _register(client)
    resp = client.get("/api/v1/responders")
    assert resp.status_code == 200
    listed = next(r for r in resp.json() if r["id"] == created["id"])
    assert "pin" not in listed
    assert "pin_hash" not in listed


def test_two_responders_get_different_pins(client):
    first = _register(client, name="Officer A", phone_number="+15551230002")
    second = _register(client, name="Officer B", phone_number="+15551230003")
    assert first["pin"] != second["pin"]


def test_reissue_pin_changes_the_pin(client, tmp_responder_store):
    created = _register(client)
    old_pin = created["pin"]

    resp = client.post(f"/api/v1/responders/{created['id']}/reissue-pin")
    assert resp.status_code == 200, resp.text
    new_pin = resp.json()["pin"]

    assert new_pin != old_pin
    stored = tmp_responder_store.get(created["id"])
    assert verify_pin(new_pin, stored.pin_hash) is True
    assert verify_pin(old_pin, stored.pin_hash) is False


def test_reissue_pin_unknown_responder_returns_404(client):
    resp = client.post("/api/v1/responders/does-not-exist/reissue-pin")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# responder_auth.py password hashing (pure functions, mirrors PIN tests)
# ---------------------------------------------------------------------------


def test_password_hash_and_verify_round_trip():
    password = "correct-horse-battery"
    password_hash = hash_password(password)
    assert verify_password(password, password_hash) is True


def test_password_verify_rejects_wrong_password():
    password_hash = hash_password("correct-horse-battery")
    assert verify_password("wrong-password", password_hash) is False


def test_password_verify_rejects_malformed_hash():
    assert verify_password("whatever", "not-a-real-argon2-hash") is False


def test_password_hash_is_argon2id():
    password_hash = hash_password("correct-horse-battery")
    assert password_hash.startswith("$argon2id$")


# ---------------------------------------------------------------------------
# Route-level: username/password at creation, duplicate rejection, never
# re-exposed on GET/list
# ---------------------------------------------------------------------------


def _register_with_login(client, *, name="Officer Login", phone_number="+15551230009", username="officer.login", password="hunter22222"):
    resp = client.post(
        "/api/v1/responders",
        json={"name": name, "phone_number": phone_number, "username": username, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_responder_without_username_password_still_works(client):
    """username/password are optional -- a PIN-only responder registration
    (the pre-existing contract) must keep working unchanged."""
    body = _register(client)
    assert body.get("username") is None
    assert "password" not in body or body["password"] is None


def test_create_responder_with_username_password_echoes_password_once(client):
    body = _register_with_login(client)
    assert body["username"] == "officer.login"
    assert body["password"] == "hunter22222"


def test_get_responder_never_includes_password_or_hash(client):
    created = _register_with_login(client, name="Officer B", phone_number="+15551230010", username="officer.b")
    resp = client.get("/api/v1/responders")
    assert resp.status_code == 200
    listed = next(r for r in resp.json() if r["id"] == created["id"])
    assert "password" not in listed
    assert "password_hash" not in listed
    assert listed["username"] == "officer.b"


def test_create_responder_rejects_duplicate_username(client):
    _register_with_login(client, name="Officer C", phone_number="+15551230011", username="dupe.user")
    resp = client.post(
        "/api/v1/responders",
        json={"name": "Officer D", "phone_number": "+15551230012", "username": "dupe.user", "password": "anotherpass1"},
    )
    assert resp.status_code == 400
    assert "already taken" in resp.text.lower()


def test_create_responder_rejects_username_without_password(client):
    resp = client.post(
        "/api/v1/responders",
        json={"name": "Officer E", "phone_number": "+15551230013", "username": "half.supplied"},
    )
    assert resp.status_code == 400


def test_create_responder_rejects_password_without_username(client):
    resp = client.post(
        "/api/v1/responders",
        json={"name": "Officer F", "phone_number": "+15551230014", "password": "somepassword1"},
    )
    assert resp.status_code == 400
