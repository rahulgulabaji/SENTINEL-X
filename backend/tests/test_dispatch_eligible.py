"""Tests for GET /v1/dispatch/eligible -- the AI Incident Assistant's
eligible-responder picker. Confirms eligibility = on_duty AND live GPS AND
has a phone number, and that GET /v1/dispatch/nearby's existing behavior is
completely unaffected by this addition.

Run from backend/: pytest tests/test_dispatch_eligible.py -v
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import mongomock  # noqa: E402

from app.repositories.responder_repository import MongoResponderRepository  # noqa: E402
from app.repositories.share_session_repository import (  # noqa: E402
    SESSION_KIND_DUTY,
    STATUS_ACTIVE,
    ShareSessionRepository,
)


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
def client(tmp_responder_store, tmp_share_repo, tmp_sms_store, tmp_dispatch_repo, tmp_audit_repo):
    import app.main as main_module
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def _register(client, *, name="Officer A", phone_number="+15551234567", role="patrol"):
    resp = client.post("/api/v1/responders", json={"name": name, "phone_number": phone_number, "role": role})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _set_location(client, responder_id, lat, lng):
    resp = client.post(
        f"/api/v1/responders/{responder_id}/location",
        json={"latitude": lat, "longitude": lng},
    )
    assert resp.status_code == 200, resp.text


def _put_on_duty(share_repo: ShareSessionRepository, responder_id: str) -> None:
    """Creates a genuinely ACTIVE duty session for a responder, bypassing
    the chat/join flow (not built in this feature) -- a direct repository
    write, same technique test_dispatch.py uses for stale-location setup."""
    session_doc, _token = share_repo.create(
        responder_id=responder_id,
        dispatch_id=None,
        invite_ttl_seconds=3600,
        token_factory=lambda session_id, rid: "irrelevant-token",
        session_kind=SESSION_KIND_DUTY,
    )
    share_repo._collection.update_one(
        {"session_id": session_doc["session_id"]},
        {
            "$set": {
                "status": STATUS_ACTIVE,
                "active_until": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
            }
        },
    )


def test_zero_responders_returns_empty_eligible_list(client):
    resp = client.get("/api/v1/dispatch/eligible", params={"latitude": 16.7, "longitude": 74.2, "radius_km": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["responders"] == []
    assert body["eligible_count"] == 0


def test_live_with_phone_but_not_on_duty_is_excluded(client, tmp_responder_store):
    created = _register(client, name="Not On Duty")
    _set_location(client, created["id"], 16.70, 74.20)

    resp = client.get("/api/v1/dispatch/eligible", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 50})
    body = resp.json()
    assert body["eligible_count"] == 0
    item = next(r for r in body["responders"] if r["id"] == created["id"])
    assert item["eligible"] is False
    assert item["on_duty"] is False
    assert "Not on duty" in item["ineligible_reason"]


def test_on_duty_live_with_phone_within_radius_is_eligible(client, tmp_share_repo):
    created = _register(client, name="Eligible Officer", phone_number="+15559990000")
    _set_location(client, created["id"], 16.70, 74.20)
    _put_on_duty(tmp_share_repo, created["id"])

    resp = client.get("/api/v1/dispatch/eligible", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 50})
    body = resp.json()
    assert body["eligible_count"] == 1
    item = body["responders"][0]
    assert item["id"] == created["id"]
    assert item["eligible"] is True
    assert item["on_duty"] is True
    assert item["ineligible_reason"] is None


def test_on_duty_but_stale_gps_is_excluded(client, tmp_responder_store, tmp_share_repo):
    from app.core.responder_store import ResponderLocation

    created = _register(client, name="Stale Duty Officer")
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    stale_location = ResponderLocation(latitude=16.70, longitude=74.20, last_seen_at=stale_time)
    tmp_responder_store._responders.update_one(
        {"id": created["id"]}, {"$set": {"location": stale_location.to_dict()}}
    )
    _put_on_duty(tmp_share_repo, created["id"])

    resp = client.get("/api/v1/dispatch/eligible", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 50})
    body = resp.json()
    assert body["eligible_count"] == 0
    item = next(r for r in body["responders"] if r["id"] == created["id"])
    assert item["eligible"] is False
    assert "stale" in item["ineligible_reason"].lower()


def test_on_duty_live_but_no_phone_is_excluded(client, tmp_share_repo):
    created = _register(client, name="No Phone Officer", phone_number="")
    _set_location(client, created["id"], 16.70, 74.20)
    _put_on_duty(tmp_share_repo, created["id"])

    resp = client.get("/api/v1/dispatch/eligible", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 50})
    body = resp.json()
    assert body["eligible_count"] == 0
    item = next(r for r in body["responders"] if r["id"] == created["id"])
    assert item["eligible"] is False
    assert "No phone number on file" in item["ineligible_reason"]


def test_eligible_responder_outside_radius_excluded_entirely(client, tmp_share_repo):
    created = _register(client, name="Far Eligible Officer", phone_number="+15558887777")
    _set_location(client, created["id"], 20.0, 80.0)  # far away
    _put_on_duty(tmp_share_repo, created["id"])

    resp = client.get("/api/v1/dispatch/eligible", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 1})
    body = resp.json()
    assert body["responders"] == []
    assert body["eligible_count"] == 0


def test_eligible_missing_coordinates_400(client):
    resp = client.get("/api/v1/dispatch/eligible")
    assert resp.status_code == 400


def test_nearby_endpoint_unaffected_by_eligible_addition(client, tmp_share_repo):
    """Regression: GET /dispatch/nearby must still return a responder who
    is live but NOT on duty -- /nearby has no duty-status concept, and
    adding /eligible must not change that."""
    created = _register(client, name="Live Not On Duty")
    _set_location(client, created["id"], 16.70, 74.20)
    # Deliberately NOT put on duty.

    resp = client.get("/api/v1/dispatch/nearby", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["responders"]) == 1
    assert body["responders"][0]["id"] == created["id"]
    # /nearby's schema has no on_duty/eligible fields at all.
    assert "on_duty" not in body["responders"][0]
    assert "eligible" not in body["responders"][0]


def test_dispatch_send_audit_log_includes_incident_id(client, tmp_audit_repo):
    """Regression/feature check for the one approved existing-code touch:
    send_dispatch()'s audit log now carries incident_id alongside
    responder_id/job_id."""
    import http.server
    import threading

    class _AlwaysOk(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
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
        import app.core.sms_config_store as sms_store_module

        sms_store_module.get_sms_config_store().update(
            enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="pw"
        )
        created = _register(client, name="Audit Officer", phone_number="+15550001234")
        _set_location(client, created["id"], 16.70, 74.20)

        resp = client.post(
            "/api/v1/dispatch/send",
            json={
                "responder_id": created["id"],
                "incident_id": "inc-audit-123",
                "job_id": "job-audit-123",
                "incident_type": "Test",
            },
        )
        assert resp.json()["success"] is True

        entries = tmp_audit_repo.list(event_type="dispatch_sent", limit=10)
        assert any(e.get("details", {}).get("incident_id") == "inc-audit-123" for e in entries)
    finally:
        server.shutdown()
        thread.join(timeout=5)
