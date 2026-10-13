"""Tests for the MongoDB persistence layer: connection module and every
repository, all exercised against mongomock -- no live Atlas/local MongoDB
server required to run this file or the rest of the suite.

mongomock.MongoClient() has the same constructor/collection/CRUD surface as
pymongo.MongoClient(), so the repository code under test here is the exact
same production code path (app/repositories/*.py, app/core/mongodb.py) --
only the underlying client class differs, injected via each repository's
`db=`/`client=` constructor parameter, same escape-hatch convention already
used by get_responder_store(settings=...)/get_sms_config_store().

Same no-conftest.py, path-injection boilerplate as the other three test
files in this directory.

Run from backend/: pytest tests/test_mongodb.py -v
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import mongomock
import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core import mongodb as mongodb_module  # noqa: E402
from app.repositories.audit_repository import AuditRepository  # noqa: E402
from app.repositories.detection_event_repository import DetectionEventRepository  # noqa: E402
from app.repositories.dispatch_repository import DispatchRepository  # noqa: E402
from app.repositories.incident_repository import IncidentRepository  # noqa: E402
from app.repositories.mongo_job_repository import MongoDBUnavailableError, MongoJobRepository  # noqa: E402
from app.repositories.responder_repository import MongoResponderRepository  # noqa: E402
from app.schemas.analysis import (  # noqa: E402
    AnalysisResult,
    AnalysisStatus,
    TemporalEvidence,
    TemporalWindowEvidence,
)


@pytest.fixture()
def mongo_db():
    """A fresh mongomock database per test -- same isolation guarantee a
    real tmp_path gives the JSON stores: no state leaks between tests."""
    client = mongomock.MongoClient()
    return client["sentinel_x_test"]


# ---------------------------------------------------------------------------
# Connection module
# ---------------------------------------------------------------------------


def test_ping_succeeds_against_reachable_database(mongo_db):
    assert mongodb_module.ping(mongo_db) is True


def test_ping_fails_truthfully_against_unreachable_database():
    import pymongo

    unreachable_client = pymongo.MongoClient(
        "mongodb://127.0.0.1:1/", serverSelectionTimeoutMS=200
    )
    unreachable_db = unreachable_client["sentinel_x_test"]
    assert mongodb_module.ping(unreachable_db) is False


def test_ensure_indexes_is_idempotent(mongo_db):
    mongodb_module.ensure_indexes(mongo_db)
    mongodb_module.ensure_indexes(mongo_db)  # must not raise on a second call
    index_names = set(mongo_db["responders"].index_information().keys())
    assert "responders_id_unique" in index_names


def test_mongo_client_construction_never_raises_when_unreachable():
    import dataclasses

    from app.core.config import get_settings

    bogus_settings = dataclasses.replace(get_settings(), MONGODB_URI="mongodb://127.0.0.1:1/")
    # Must not raise -- PyMongo connects lazily, construction itself never
    # touches the network.
    client = mongodb_module.get_mongo_client(settings=bogus_settings)
    assert client is not None
    client.close()


# ---------------------------------------------------------------------------
# Responder repository
# ---------------------------------------------------------------------------


def test_responder_create_and_get_round_trip(mongo_db):
    repo = MongoResponderRepository(mongo_db)
    created = repo.create(name="Officer Rao", phone_number="+919876543210", role="Patrol")
    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.name == "Officer Rao"
    assert fetched.phone_number == "+919876543210"
    assert fetched.created_at == created.created_at
    assert fetched.updated_at == created.created_at


def test_responder_list_all_returns_empty_when_none_registered(mongo_db):
    repo = MongoResponderRepository(mongo_db)
    assert repo.list_all() == []


def test_responder_update_bumps_updated_at_not_created_at(mongo_db):
    repo = MongoResponderRepository(mongo_db)
    created = repo.create(name="Officer Bump")
    updated = repo.update(created.id, status="busy")
    assert updated.created_at == created.created_at
    assert updated.updated_at != created.created_at


def test_responder_update_location_persists_embedded_and_history(mongo_db):
    repo = MongoResponderRepository(mongo_db)
    created = repo.create(name="Officer GPS")
    updated = repo.update_location(created.id, latitude=16.70, longitude=74.20, accuracy_meters=5.0)
    assert updated.location.latitude == 16.70
    assert updated.location.longitude == 74.20

    history = list(mongo_db["responder_locations"].find({"responder_id": created.id}))
    assert len(history) == 1
    # GeoJSON order is [longitude, latitude] -- NOT [latitude, longitude].
    assert history[0]["location"]["coordinates"] == [74.20, 16.70]
    assert history[0]["location"]["type"] == "Point"


def test_responder_delete(mongo_db):
    repo = MongoResponderRepository(mongo_db)
    created = repo.create(name="Officer Delete Me")
    assert repo.delete(created.id) is True
    assert repo.get(created.id) is None
    assert repo.delete(created.id) is False  # already gone


def test_responder_persistence_across_fresh_repository_instances(mongo_db):
    """Simulates a backend restart: a second, independent repository
    instance pointed at the same database must see data written by the
    first."""
    repo_a = MongoResponderRepository(mongo_db)
    created = repo_a.create(name="Officer Restart")
    repo_a.update_location(created.id, latitude=16.70, longitude=74.20, accuracy_meters=5.0)

    repo_b = MongoResponderRepository(mongo_db)  # fresh instance, same db
    fetched = repo_b.get(created.id)
    assert fetched is not None
    assert fetched.location.latitude == 16.70
    assert fetched.location.longitude == 74.20


def test_responder_malformed_document_is_skipped_not_crashing(mongo_db):
    mongo_db["responders"].insert_one({"id": "well-formed", "name": "Good Officer"})
    mongo_db["responders"].insert_one({"name": "Missing id field"})  # malformed -- no `id`
    repo = MongoResponderRepository(mongo_db)
    results = repo.list_all()
    assert len(results) == 1
    assert results[0].id == "well-formed"


# ---------------------------------------------------------------------------
# Job repository
# ---------------------------------------------------------------------------


def _make_job(job_id: str) -> AnalysisResult:
    return AnalysisResult(
        job_id=job_id,
        status=AnalysisStatus.QUEUED,
        filename="clip.mp4",
    )


def test_job_create_and_get_round_trip(mongo_db):
    repo = MongoJobRepository(mongo_db)
    job = _make_job("job-001")
    repo.create(job)
    fetched = repo.get("job-001")
    assert fetched is not None
    assert fetched.status == AnalysisStatus.QUEUED
    assert fetched.filename == "clip.mp4"


def test_job_update_round_trip(mongo_db):
    repo = MongoJobRepository(mongo_db)
    repo.create(_make_job("job-002"))
    updated = repo.update(
        "job-002",
        status=AnalysisStatus.COMPLETED,
        anomaly_detected=True,
        anomaly_probability=0.91,
    )
    assert updated.status == AnalysisStatus.COMPLETED
    assert updated.anomaly_detected is True
    assert updated.anomaly_probability == 0.91


def test_job_update_unknown_job_returns_none(mongo_db):
    repo = MongoJobRepository(mongo_db)
    assert repo.update("nope", status=AnalysisStatus.FAILED) is None


def test_job_persistence_across_fresh_repository_instances(mongo_db):
    repo_a = MongoJobRepository(mongo_db)
    repo_a.create(_make_job("job-003"))
    repo_b = MongoJobRepository(mongo_db)
    assert repo_b.get("job-003") is not None


# ---------------------------------------------------------------------------
# Incident + detection event repositories
# ---------------------------------------------------------------------------


def test_incident_created_from_completed_anomalous_job(mongo_db):
    job = _make_job("job-anomaly")
    job = job.model_copy(
        update={
            "anomaly_detected": True,
            "anomaly_probability": 0.87,
            "likely_action": "Loitering",
            "action_confidence": 0.75,
        }
    )
    repo = IncidentRepository(mongo_db)
    incident = repo.create_from_job(job)
    assert incident["status"] == "open"
    assert incident["job_id"] == "job-anomaly"
    fetched = repo.get(incident["incident_id"])
    assert fetched["anomaly_probability"] == 0.87


def test_incident_update_status(mongo_db):
    job = _make_job("job-anomaly-2").model_copy(update={"anomaly_detected": True})
    repo = IncidentRepository(mongo_db)
    incident = repo.create_from_job(job)
    updated = repo.update_status(incident["incident_id"], "dispatched")
    assert updated["status"] == "dispatched"


def test_detection_events_created_only_for_anomalous_jobs(mongo_db):
    clean_job = _make_job("job-clean").model_copy(update={"anomaly_detected": False})
    repo = DetectionEventRepository(mongo_db)
    assert repo.create_from_job(clean_job) == []


def test_detection_events_fan_out_from_temporal_windows(mongo_db):
    windows = [
        TemporalWindowEvidence(
            window_index=0, start_time_seconds=0.0, end_time_seconds=2.0,
            stage1_attention=0.5, stage1_attention_normalized=0.5,
        ),
        TemporalWindowEvidence(
            window_index=1, start_time_seconds=2.0, end_time_seconds=4.0,
            stage1_attention=0.9, stage1_attention_normalized=0.9,
        ),
    ]
    job = _make_job("job-windows").model_copy(
        update={
            "anomaly_detected": True,
            "likely_action": "Fighting",
            "action_confidence": 0.8,
            "temporal_evidence": TemporalEvidence(available=True, window_duration_seconds=2.0, windows=windows),
        }
    )
    repo = DetectionEventRepository(mongo_db)
    events = repo.create_from_job(job)
    assert len(events) == 2
    stored = repo.list_for_job("job-windows")
    assert len(stored) == 2
    assert {e["window_index"] for e in stored} == {0, 1}


# ---------------------------------------------------------------------------
# Dispatch repository -- send-only, never preview
# ---------------------------------------------------------------------------


def test_dispatch_record_send_success(mongo_db):
    repo = DispatchRepository(mongo_db)
    record = repo.record_send(
        incident_id="inc-1", responder_id="resp-1", message="Alert", success=True, error=None
    )
    assert record["status"] == "sent"
    assert record["sent_at"] is not None
    stored = repo.list_for_incident("inc-1")
    assert len(stored) == 1


def test_dispatch_record_send_failure_has_no_sent_at(mongo_db):
    repo = DispatchRepository(mongo_db)
    record = repo.record_send(
        incident_id="inc-2", responder_id="resp-2", message="Alert", success=False, error="gateway unreachable"
    )
    assert record["status"] == "failed"
    assert record["sent_at"] is None
    assert record["error"] == "gateway unreachable"


def test_dispatch_record_never_carries_a_password_field(mongo_db):
    repo = DispatchRepository(mongo_db)
    record = repo.record_send(
        incident_id="inc-3", responder_id="resp-3", message="Alert", success=True, error=None
    )
    assert "password" not in record
    assert "sms_gateway_password" not in {k.lower() for k in record}


# ---------------------------------------------------------------------------
# Audit repository -- never logs secrets
# ---------------------------------------------------------------------------


def test_audit_log_records_event(mongo_db):
    repo = AuditRepository(mongo_db)
    repo.log("responder_created", details={"responder_id": "resp-1"})
    stored = list(mongo_db["audit_logs"].find({"event_type": "responder_created"}))
    assert len(stored) == 1
    assert stored[0]["details"]["responder_id"] == "resp-1"


def test_audit_log_strips_password_like_keys(mongo_db):
    repo = AuditRepository(mongo_db)
    repo.log("configuration_changed", details={"url": "http://example.test", "password": "should-not-be-stored"})
    stored = list(mongo_db["audit_logs"].find({"event_type": "configuration_changed"}))
    assert "password" not in stored[0]["details"]
    assert stored[0]["details"]["url"] == "http://example.test"


# ---------------------------------------------------------------------------
# Idempotency / duplicate prevention (mirrors the migration script's
# upsert-by-id semantics)
# ---------------------------------------------------------------------------


def test_responder_upsert_by_id_does_not_duplicate_on_repeat_create(mongo_db):
    repo = MongoResponderRepository(mongo_db)
    repo.create(id="fixed-id", name="Officer Once")
    repo.create(id="fixed-id", name="Officer Once Again")  # same id, repeat "migration" run
    assert mongo_db["responders"].count_documents({"id": "fixed-id"}) == 1
    assert repo.get("fixed-id").name == "Officer Once Again"


def test_job_upsert_style_update_does_not_duplicate(mongo_db):
    repo = MongoJobRepository(mongo_db)
    repo.create(_make_job("job-dup"))
    repo.update("job-dup", status=AnalysisStatus.PROCESSING)
    repo.update("job-dup", status=AnalysisStatus.COMPLETED)
    assert mongo_db["analysis_jobs"].count_documents({"job_id": "job-dup"}) == 1


# ---------------------------------------------------------------------------
# Database-unavailable truthful error behavior
# ---------------------------------------------------------------------------


def test_job_repository_raises_truthful_error_when_database_unavailable():
    import pymongo

    unreachable_client = pymongo.MongoClient(
        "mongodb://127.0.0.1:1/", serverSelectionTimeoutMS=200
    )
    unreachable_db = unreachable_client["sentinel_x_test"]
    repo = MongoJobRepository(unreachable_db)
    with pytest.raises(MongoDBUnavailableError):
        repo.create(_make_job("job-unreachable"))


def test_responder_repository_raises_truthful_error_when_database_unavailable():
    import pymongo

    from app.repositories.responder_repository import MongoResponderRepository

    unreachable_client = pymongo.MongoClient(
        "mongodb://127.0.0.1:1/", serverSelectionTimeoutMS=200
    )
    unreachable_db = unreachable_client["sentinel_x_test"]
    repo = MongoResponderRepository(unreachable_db)
    with pytest.raises(MongoDBUnavailableError):
        repo.list_all()
