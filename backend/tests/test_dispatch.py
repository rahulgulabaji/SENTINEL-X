"""Tests for the responder registry and incident dispatch API.

No real SMS is ever sent by these tests. Dispatch's /send endpoint is only
exercised against SmsGatewayService.send_sms() with a deliberately
unreachable/unconfigured gateway, same convention as test_notifications.py.

No mocking of ResponderStore/SmsGatewayService internals -- real objects,
real (local, closed-port) network calls where needed, same philosophy as
the rest of this test suite.

Run from backend/: pytest tests/test_dispatch.py -v
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

from app.core.dispatch_config import DispatchIdempotencyGuard, classify_location_liveness  # noqa: E402
from app.core.geo import haversine_km  # noqa: E402
from app.repositories.responder_repository import MongoResponderRepository  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_responder_store(monkeypatch) -> MongoResponderRepository:
    # Mechanical update for the MongoDB persistence migration: the routes
    # now read from app.repositories.responder_repository's singleton
    # instead of app.core.responder_store's, so that's the singleton this
    # fixture swaps -- same shape as before (a fresh, isolated instance per
    # test, reset to None on teardown), just pointed at a mongomock database
    # instead of a tmp_path directory. No test bodies/assertions below this
    # fixture change at all.
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
def tmp_dispatch_repo(monkeypatch):
    # Same mechanical swap as tmp_responder_store: dispatch.py's send_dispatch
    # now writes through app.repositories.dispatch_repository's singleton.
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
def client(tmp_responder_store, tmp_sms_store, tmp_dispatch_repo, tmp_audit_repo):
    import app.main as main_module
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def _register(client, *, id=None, name="Officer A", phone_number="+15551234567", role="patrol", status="available"):
    payload = {"name": name, "phone_number": phone_number, "role": role, "status": status}
    if id is not None:
        payload["id"] = id
    resp = client.post("/api/v1/responders", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _set_location(client, responder_id, lat, lng, accuracy=5.0):
    resp = client.post(
        f"/api/v1/responders/{responder_id}/location",
        json={"latitude": lat, "longitude": lng, "accuracy_meters": accuracy},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Haversine distance (pure function)
# ---------------------------------------------------------------------------


def test_haversine_same_point_is_zero():
    assert haversine_km(16.7, 74.2, 16.7, 74.2) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance_kolkata_delhi():
    # Delhi (28.6139, 77.2090) to Mumbai (19.0760, 72.8777) -- real-world
    # great-circle distance is ~1150-1160 km, nowhere near a naive
    # lat/lon-subtraction answer (~9.6 "degrees" of nonsense).
    d = haversine_km(28.6139, 77.2090, 19.0760, 72.8777)
    assert 1100 < d < 1200


def test_haversine_is_not_naive_subtraction():
    # At high latitude, 1 degree of longitude is much shorter than at the
    # equator -- a naive sqrt(dlat^2 + dlon^2) treats them as equal, a real
    # Haversine does not. Confirms this isn't a flat-plane approximation.
    d_equator = haversine_km(0.0, 0.0, 0.0, 1.0)
    d_high_lat = haversine_km(80.0, 0.0, 80.0, 1.0)
    assert d_high_lat < d_equator * 0.5


# ---------------------------------------------------------------------------
# Live/stale/offline classification
# ---------------------------------------------------------------------------


def test_classify_offline_when_never_seen():
    assert classify_location_liveness(None) == "offline"


def test_classify_live_when_recent():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    assert classify_location_liveness(now.isoformat(), now=now) == "live"


def test_classify_stale_when_old():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    old = now - timedelta(seconds=120)
    assert classify_location_liveness(old.isoformat(), now=now) == "stale"


# ---------------------------------------------------------------------------
# Idempotency guard
# ---------------------------------------------------------------------------


def test_idempotency_guard_blocks_rapid_duplicate():
    guard = DispatchIdempotencyGuard(window_seconds=5.0)
    assert guard.check_and_mark("r1:job1") is True
    assert guard.check_and_mark("r1:job1") is False


def test_idempotency_guard_allows_different_keys():
    guard = DispatchIdempotencyGuard(window_seconds=5.0)
    assert guard.check_and_mark("r1:job1") is True
    assert guard.check_and_mark("r2:job1") is True


def test_idempotency_guard_expires_after_window():
    guard = DispatchIdempotencyGuard(window_seconds=0.2)
    assert guard.check_and_mark("r1:job1") is True
    time.sleep(0.3)
    assert guard.check_and_mark("r1:job1") is True


# ---------------------------------------------------------------------------
# Responder CRUD (1, 2, 3)
# ---------------------------------------------------------------------------


def test_register_responder(client):
    body = _register(client, name="Officer Rao", phone_number="+919876543210", role="Patrol Officer")
    assert body["name"] == "Officer Rao"
    assert body["phone_number"] == "+919876543210"
    assert body["status"] == "available"
    assert body["live_state"] == "offline"  # no location reported yet


def test_register_responder_stamps_created_and_updated_at(client):
    body = _register(client, name="Officer Timestamp")
    assert body["created_at"], "created_at must be stamped on registration"
    assert body["updated_at"], "updated_at must be stamped on registration"
    assert body["created_at"] == body["updated_at"]  # identical at creation time


def test_update_responder_bumps_updated_at_not_created_at(client):
    import time

    created = _register(client, name="Officer Bump")
    time.sleep(0.05)
    resp = client.put(f"/api/v1/responders/{created['id']}", json={"status": "busy"})
    updated = resp.json()
    assert updated["created_at"] == created["created_at"]  # unchanged
    assert updated["updated_at"] != created["updated_at"]  # bumped
    assert updated["updated_at"] > created["updated_at"]


def test_location_update_bumps_updated_at(client):
    import time

    created = _register(client, name="Officer GPS Bump")
    time.sleep(0.05)
    _set_location(client, created["id"], 16.70, 74.20)
    resp = client.get(f"/api/v1/responders")
    body = next(r for r in resp.json() if r["id"] == created["id"])
    assert body["updated_at"] != created["updated_at"]
    assert body["created_at"] == created["created_at"]


def test_register_responder_accepts_phone_alias(client):
    # The real frontend sends `phone`, not `phone_number`.
    resp = client.post("/api/v1/responders", json={"name": "Officer B", "phone": "+15559999999", "unit": "K9"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["phone_number"] == "+15559999999"


def test_update_responder(client):
    created = _register(client)
    resp = client.put(f"/api/v1/responders/{created['id']}", json={"status": "busy", "role": "Supervisor"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "busy"
    assert body["role"] == "Supervisor"
    assert body["name"] == created["name"]  # untouched field preserved


def test_update_unknown_responder_404(client):
    resp = client.put("/api/v1/responders/does-not-exist", json={"status": "busy"})
    assert resp.status_code == 404


def test_delete_responder(client):
    created = _register(client)
    resp = client.delete(f"/api/v1/responders/{created['id']}")
    assert resp.status_code == 200

    resp2 = client.get("/api/v1/responders")
    assert resp2.json() == []


def test_delete_unknown_responder_404(client):
    resp = client.delete("/api/v1/responders/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GPS update (4, 5)
# ---------------------------------------------------------------------------


def test_update_gps(client):
    created = _register(client)
    body = _set_location(client, created["id"], 16.7, 74.2, accuracy=12.5)
    assert body["latitude"] == 16.7
    assert body["longitude"] == 74.2
    assert body["accuracy_meters"] == 12.5
    assert body["live_state"] == "live"


def test_update_gps_unknown_responder_404(client):
    resp = client.post("/api/v1/responders/nope/location", json={"latitude": 1.0, "longitude": 1.0})
    assert resp.status_code == 404


def test_invalid_latitude_rejected(client):
    created = _register(client)
    resp = client.post(
        f"/api/v1/responders/{created['id']}/location",
        json={"latitude": 999.0, "longitude": 74.2},
    )
    assert resp.status_code == 422


def test_invalid_longitude_rejected(client):
    created = _register(client)
    resp = client.post(
        f"/api/v1/responders/{created['id']}/location",
        json={"latitude": 16.7, "longitude": -999.0},
    )
    assert resp.status_code == 422


def test_zero_accuracy_rejected(client):
    created = _register(client)
    resp = client.post(
        f"/api/v1/responders/{created['id']}/location",
        json={"latitude": 16.7, "longitude": 74.2, "accuracy_meters": 0},
    )
    assert resp.status_code == 422


def test_negative_accuracy_rejected(client):
    created = _register(client)
    resp = client.post(
        f"/api/v1/responders/{created['id']}/location",
        json={"latitude": 16.7, "longitude": 74.2, "accuracy_meters": -5.0},
    )
    assert resp.status_code == 422


def test_omitted_accuracy_still_accepted(client):
    # None/omitted accuracy means "not reported" -- distinct from 0, and
    # must remain valid.
    created = _register(client)
    resp = client.post(
        f"/api/v1/responders/{created['id']}/location",
        json={"latitude": 16.7, "longitude": 74.2},
    )
    assert resp.status_code == 200
    assert resp.json()["accuracy_meters"] is None


def test_location_update_accepts_lat_lng_alias(client):
    # The real frontend sends both latitude/longitude AND lat/lng in the
    # same payload -- confirm lat/lng alone is also accepted.
    created = _register(client)
    resp = client.post(
        f"/api/v1/responders/{created['id']}/location",
        json={"lat": 16.7, "lng": 74.2, "accuracy": 8.0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["latitude"] == 16.7
    assert body["accuracy_meters"] == 8.0


# ---------------------------------------------------------------------------
# Nearby search: live/stale/offline filtering + Haversine ordering (6-10)
# ---------------------------------------------------------------------------


def test_zero_responders_returns_empty_list(client):
    resp = client.get("/api/v1/dispatch/nearby", params={"latitude": 16.7, "longitude": 74.2, "radius_km": 50})
    assert resp.status_code == 200
    assert resp.json()["responders"] == []


def test_live_responder_returned_in_nearby(client):
    created = _register(client, name="Near Officer")
    _set_location(client, created["id"], 16.70, 74.20)

    resp = client.get("/api/v1/dispatch/nearby", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["responders"]) == 1
    assert body["responders"][0]["id"] == created["id"]
    assert body["responders"][0]["distance_km"] == pytest.approx(0.0, abs=0.01)


def test_stale_responder_excluded_from_nearby(client, tmp_responder_store):
    from datetime import datetime, timedelta, timezone

    created = _register(client, name="Stale Officer")
    # Directly set a stale last_seen_at via the store (bypassing the
    # server-stamped-now update_location, which would always be live).
    from app.core.responder_store import ResponderLocation

    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    stale_location = ResponderLocation(latitude=16.70, longitude=74.20, accuracy_meters=5.0, last_seen_at=stale_time)
    # Direct backing-store write, bypassing the server-stamped-now
    # update_location() -- same technique as before the MongoDB migration,
    # mechanically adapted: write straight into the underlying mongomock
    # collection the fixture wraps, instead of a dict assignment.
    tmp_responder_store._responders.update_one(
        {"id": created["id"]}, {"$set": {"location": stale_location.to_dict()}}
    )

    resp = client.get("/api/v1/dispatch/nearby", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 50})
    assert resp.json()["responders"] == []


def test_offline_responder_excluded_from_nearby(client):
    # Registered but never reported a location at all.
    _register(client, name="Never Reported")
    resp = client.get("/api/v1/dispatch/nearby", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 50})
    assert resp.json()["responders"] == []


def test_nearby_sorted_nearest_first(client):
    far = _register(client, name="Far Officer")
    near = _register(client, name="Near Officer")
    _set_location(client, far["id"], 17.50, 75.00)  # farther from the query point
    _set_location(client, near["id"], 16.71, 74.21)  # closer

    resp = client.get("/api/v1/dispatch/nearby", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 200})
    body = resp.json()
    assert [r["id"] for r in body["responders"]] == [near["id"], far["id"]]
    assert body["responders"][0]["distance_km"] < body["responders"][1]["distance_km"]


def test_nearby_respects_radius(client):
    created = _register(client, name="Distant Officer")
    _set_location(client, created["id"], 20.0, 80.0)  # far outside a small radius

    resp = client.get("/api/v1/dispatch/nearby", params={"latitude": 16.70, "longitude": 74.20, "radius_km": 1})
    assert resp.json()["responders"] == []


def test_nearby_accepts_lat_lng_query_aliases(client):
    # The real frontend queries with ?lat=..&lng=.., not latitude/longitude.
    created = _register(client, name="Officer")
    _set_location(client, created["id"], 16.70, 74.20)

    resp = client.get("/api/v1/dispatch/nearby", params={"lat": 16.70, "lng": 74.20, "radius_km": 5})
    assert resp.status_code == 200
    assert len(resp.json()["responders"]) == 1


def test_nearby_missing_coordinates_400(client):
    resp = client.get("/api/v1/dispatch/nearby")
    assert resp.status_code == 400


def test_nearby_response_includes_incident_location(client):
    resp = client.get(
        "/api/v1/dispatch/nearby",
        params={"latitude": 16.70, "longitude": 74.20, "radius_km": 5, "location_label": "Main Gate Camera"},
    )
    body = resp.json()
    assert body["incident_location"] == {
        "latitude": 16.70,
        "longitude": 74.20,
        "location_label": "Main Gate Camera",
    }


# ---------------------------------------------------------------------------
# Dispatch preview: never sends SMS (11)
# ---------------------------------------------------------------------------


def test_preview_does_not_send_sms(client, tmp_sms_store):
    tmp_sms_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    created = _register(client, name="Preview Officer", phone_number="+15550001111")
    _set_location(client, created["id"], 16.70, 74.20)

    resp = client.post(
        "/api/v1/dispatch/preview",
        json={
            "responder_id": created["id"],
            "incident_type": "Fence Breach",
            "confidence": 0.93,
            "location": "Main Gate",
            "evidence_window": "12.0s - 18.0s",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "Fence Breach" in body["message"]
    assert "93.0%" in body["message"]
    assert "11" in body["recipient"]  # masked, last 2 digits visible
    assert body["recipient"] != "+15550001111"  # never the raw number


def test_preview_accepts_structured_fields(client, tmp_sms_store):
    """The additive structured fields (incident_id/incident_timestamp/
    action_confidence/location_label/evidence_start_seconds/
    evidence_end_seconds) must be usable instead of the free-text fields,
    and must take priority when both are supplied."""
    tmp_sms_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    created = _register(client, name="Structured Preview Officer", phone_number="+15550007777")
    _set_location(client, created["id"], 16.70, 74.20)

    resp = client.post(
        "/api/v1/dispatch/preview",
        json={
            "responder_id": created["id"],
            "incident_id": "INC-001",
            "incident_type": "Loitering",
            "incident_timestamp": "2025-01-01T00:00:00+00:00",
            "anomaly_probability": 0.88,
            "likely_action": "Loitering",
            "action_confidence": 0.75,
            "location_label": "North Gate Camera",
            "latitude": 16.70,
            "longitude": 74.20,
            "evidence_start_seconds": 12.5,
            "evidence_end_seconds": 18.25,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "North Gate Camera" in body["message"]  # location_label preferred
    assert "75.0%" in body["message"]  # action_confidence used as confidence fallback
    assert "12.50s" in body["message"] and "18.25s" in body["message"]  # structured evidence window


def test_preview_structured_fields_override_free_text_when_both_present(client, tmp_sms_store):
    tmp_sms_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    created = _register(client, name="Override Officer")
    _set_location(client, created["id"], 16.70, 74.20)

    resp = client.post(
        "/api/v1/dispatch/preview",
        json={
            "responder_id": created["id"],
            "location": "Old Free-Text Location",
            "location_label": "New Structured Location",
            "evidence_window": "1.0s - 2.0s",
            "evidence_start_seconds": 10.0,
            "evidence_end_seconds": 20.0,
        },
    )
    body = resp.json()
    assert "New Structured Location" in body["message"]
    assert "Old Free-Text Location" not in body["message"]
    assert "10.00s" in body["message"]
    assert "1.0s - 2.0s" not in body["message"]


def test_preview_unknown_responder_404(client):
    resp = client.post("/api/v1/dispatch/preview", json={"responder_id": "nope"})
    assert resp.status_code == 404


def test_preview_stale_responder_reports_not_live(client, tmp_responder_store):
    from datetime import datetime, timedelta, timezone

    from app.core.responder_store import ResponderLocation

    created = _register(client, name="Stale Preview Officer")
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    stale_location = ResponderLocation(latitude=1.0, longitude=1.0, last_seen_at=stale_time)
    tmp_responder_store._responders.update_one(
        {"id": created["id"]}, {"$set": {"location": stale_location.to_dict()}}
    )

    resp = client.post("/api/v1/dispatch/preview", json={"responder_id": created["id"]})
    body = resp.json()
    assert body["success"] is False
    assert "not currently live" in body["error"]


# ---------------------------------------------------------------------------
# Dispatch send: calls existing SMS gateway, truthful results (12, 13, 14)
# ---------------------------------------------------------------------------


def test_send_calls_existing_sms_gateway_unreachable(client, tmp_sms_store):
    # Deliberately unreachable gateway (closed local port) -- proves send()
    # really calls through to SmsGatewayService.send_sms(), not a stub.
    tmp_sms_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    created = _register(client, name="Send Officer", phone_number="+15550002222")
    _set_location(client, created["id"], 16.70, 74.20)

    resp = client.post(
        "/api/v1/dispatch/send",
        json={"responder_id": created["id"], "incident_type": "Loitering", "confidence": 0.8, "job_id": "job-abc"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]  # truthful failure, not a fabricated success


def test_send_fails_truthfully_when_gateway_not_configured(client, tmp_sms_store):
    tmp_sms_store.update(enabled=False, url="", username="", password="")
    created = _register(client, name="Send Officer 2")
    _set_location(client, created["id"], 16.70, 74.20)

    resp = client.post("/api/v1/dispatch/send", json={"responder_id": created["id"]})
    body = resp.json()
    assert body["success"] is False
    assert body["error"]


def test_send_succeeds_against_fake_gateway(client, tmp_sms_store):
    """A tiny stdlib HTTP server that always returns 200 for POST /message --
    proves a successful send really round-trips through SmsGatewayService."""
    import http.server

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
        tmp_sms_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="pw")
        created = _register(client, name="Live Send Officer", phone_number="+15550003333")
        _set_location(client, created["id"], 16.70, 74.20)

        resp = client.post(
            "/api/v1/dispatch/send",
            json={"responder_id": created["id"], "incident_type": "Test", "job_id": "job-xyz"},
        )
        body = resp.json()
        assert body["success"] is True
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_stale_responder_cannot_be_dispatched(client, tmp_responder_store, tmp_sms_store):
    from datetime import datetime, timedelta, timezone

    from app.core.responder_store import ResponderLocation

    tmp_sms_store.update(enabled=True, url="http://127.0.0.1:1", username="u", password="pw")
    created = _register(client, name="Stale Send Officer")
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    stale_location = ResponderLocation(latitude=1.0, longitude=1.0, last_seen_at=stale_time)
    tmp_responder_store._responders.update_one(
        {"id": created["id"]}, {"$set": {"location": stale_location.to_dict()}}
    )

    resp = client.post("/api/v1/dispatch/send", json={"responder_id": created["id"]})
    body = resp.json()
    assert body["success"] is False
    assert "not currently live" in body["error"]


def test_offline_responder_cannot_be_dispatched(client):
    created = _register(client, name="Never-located Officer")  # never reported GPS
    resp = client.post("/api/v1/dispatch/send", json={"responder_id": created["id"]})
    body = resp.json()
    assert body["success"] is False
    assert "not currently live" in body["error"]


def test_send_unknown_responder_404(client):
    resp = client.post("/api/v1/dispatch/send", json={"responder_id": "nope"})
    assert resp.status_code == 404


def test_send_rebuilds_message_ignoring_client_supplied_message(client, tmp_sms_store):
    """Security property: a client-supplied `message`/`recipient` must be
    ignored -- the backend always rebuilds the SMS body and always uses the
    responder's own stored phone number."""
    import http.server

    captured = {}

    class _Capture(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            captured["body"] = body.decode("utf-8")
            captured["auth"] = self.headers.get("Authorization")
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
        created = _register(client, name="Real Officer", phone_number="+15550009999")
        _set_location(client, created["id"], 16.70, 74.20)

        resp = client.post(
            "/api/v1/dispatch/send",
            json={
                "responder_id": created["id"],
                "recipient": "+10000000000",  # attempted tamper -- must be ignored
                "message": "ATTACKER CONTROLLED TEXT",  # attempted tamper -- must be ignored
                "incident_type": "Real Incident",
                "job_id": "job-real",
            },
        )
        assert resp.json()["success"] is True
        assert "+15550009999" in captured["body"]  # real stored number used
        assert "+10000000000" not in captured["body"]
        assert "ATTACKER CONTROLLED TEXT" not in captured["body"]
        assert "Real Incident" in captured["body"]
        assert "wrong" not in (captured.get("auth") or "")  # sanity: no password leak into capture
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_double_click_dispatch_is_deduplicated(client, tmp_sms_store):
    import http.server

    call_count = {"n": 0}

    class _CountingOk(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            call_count["n"] += 1
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _CountingOk)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        tmp_sms_store.update(enabled=True, url=f"http://127.0.0.1:{port}", username="u", password="pw")
        created = _register(client, name="Double Click Officer", phone_number="+15550004444")
        _set_location(client, created["id"], 16.70, 74.20)

        payload = {"responder_id": created["id"], "job_id": "job-double-click"}
        first = client.post("/api/v1/dispatch/send", json=payload)
        second = client.post("/api/v1/dispatch/send", json=payload)

        assert first.json()["success"] is True
        assert first.json()["deduplicated"] is False
        assert second.json()["success"] is True
        assert second.json()["deduplicated"] is True
        assert call_count["n"] == 1  # only ONE real HTTP call reached the gateway
    finally:
        server.shutdown()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# No automatic SMS from anomaly processing (15)
# ---------------------------------------------------------------------------


def test_analysis_service_module_has_no_sms_dependency():
    """Static guard: app.services.analysis_service must not import
    anything from the SMS/dispatch modules -- there is no code path by
    which completing an analysis job can itself trigger an SMS."""
    import app.services.analysis_service as analysis_service

    source = Path(analysis_service.__file__).read_text(encoding="utf-8")
    assert "sms_gateway" not in source
    assert "dispatch" not in source
    assert "responder" not in source


def test_job_executor_module_has_no_sms_dependency():
    import app.services.job_executor as job_executor

    source = Path(job_executor.__file__).read_text(encoding="utf-8")
    assert "sms_gateway" not in source
    assert "dispatch" not in source


# ---------------------------------------------------------------------------
# Regression: existing SMS endpoints still work (shared store with dispatch)
# ---------------------------------------------------------------------------


def test_existing_notifications_endpoints_unaffected(client, tmp_sms_store):
    resp = client.get("/api/v1/notifications/sms/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["configured"] is False


def test_existing_health_endpoint_unaffected(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
