"""Tests for GET /v1/incidents/latest/summary -- the AI Incident Assistant's
latest-incident endpoint. Follows the same mongomock + monkeypatched-
singleton convention as test_dispatch.py/test_share.py.

Run from backend/: pytest tests/test_incidents_latest_summary.py -v
"""

from __future__ import annotations

import sys
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
    # app/api/routes/analysis.py's own module-level singleton -- the new
    # latest-summary route looks up the linked job via that module's
    # get_job_repository(), so this is the singleton that must be swapped
    # for the route to see a job created by the test.
    import app.api.routes.analysis as analysis_routes_module
    from app.repositories.mongo_job_repository import MongoJobRepository

    db = mongomock.MongoClient()["sentinel_x_test"]
    repo = MongoJobRepository(db)
    monkeypatch.setattr(analysis_routes_module, "_job_repository", repo)
    yield repo
    monkeypatch.setattr(analysis_routes_module, "_job_repository", None)


@pytest.fixture()
def client(tmp_incident_repo, tmp_job_repo):
    import app.main as main_module
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def _seed_incident(repo, **overrides) -> dict:
    job = AnalysisResult(
        job_id=overrides.pop("job_id", "job-1"),
        status=AnalysisStatus.COMPLETED,
        filename="clip.mp4",
        anomaly_detected=True,
        anomaly_probability=overrides.pop("anomaly_probability", 0.9),
        likely_action=overrides.pop("likely_action", "Fence Breach"),
        action_confidence=overrides.pop("action_confidence", 0.8),
    )
    return repo.create_from_job(job)


def test_no_incidents_returns_null_not_error(client):
    resp = client.get("/api/v1/incidents/latest/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"incident": None, "summary": None}


def test_latest_incident_with_linked_job_returns_full_summary(client, tmp_incident_repo, tmp_job_repo):
    job = AnalysisResult(
        job_id="job-linked",
        status=AnalysisStatus.COMPLETED,
        filename="clip.mp4",
        anomaly_detected=True,
        anomaly_probability=0.95,
        likely_action="Loitering",
        action_confidence=0.77,
    )
    tmp_job_repo.create(job)
    tmp_incident_repo.create_from_job(job)

    resp = client.get("/api/v1/incidents/latest/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident"]["job_id"] == "job-linked"
    assert body["summary"]["ai_detected"]["likely_action"] == "Loitering"
    assert body["summary"]["ai_detected"]["anomaly_probability"] == 0.95
    assert "Severity/priority is not tracked by this system." in body["summary"]["limitations"]


def test_incident_with_unresolvable_job_still_returns_incident(client, tmp_incident_repo):
    # Incident references a job_id that was never created in tmp_job_repo --
    # the summary must still degrade gracefully, not fail the request.
    job = AnalysisResult(
        job_id="job-missing",
        status=AnalysisStatus.COMPLETED,
        filename="clip.mp4",
        anomaly_detected=True,
        anomaly_probability=0.5,
        likely_action="Unknown",
        action_confidence=0.5,
    )
    tmp_incident_repo.create_from_job(job)  # NOT persisted to tmp_job_repo

    resp = client.get("/api/v1/incidents/latest/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident"] is not None
    assert body["summary"] is not None
    assert body["summary"]["location"]["available"] is False
    assert "Linked analysis job could not be loaded; evidence and location details are unavailable." in body["summary"]["limitations"]


def test_most_recently_created_incident_is_returned(client, tmp_incident_repo, tmp_job_repo):
    older = AnalysisResult(job_id="job-older", status=AnalysisStatus.COMPLETED, filename="a.mp4", anomaly_detected=True)
    newer = AnalysisResult(job_id="job-newer", status=AnalysisStatus.COMPLETED, filename="b.mp4", anomaly_detected=True)
    tmp_job_repo.create(older)
    tmp_job_repo.create(newer)
    tmp_incident_repo.create_from_job(older)
    tmp_incident_repo.create_from_job(newer)

    resp = client.get("/api/v1/incidents/latest/summary")
    body = resp.json()
    assert body["incident"]["job_id"] == "job-newer"


def test_existing_list_incidents_endpoint_unaffected(client, tmp_incident_repo, tmp_job_repo):
    """Regression: adding /latest/summary must not change GET /v1/incidents
    (list) or its route-matching -- /{incident_id} must still work for a
    real incident_id, and /latest/summary must not be swallowed by the
    /{incident_id} path parameter."""
    job = AnalysisResult(job_id="job-reg", status=AnalysisStatus.COMPLETED, filename="c.mp4", anomaly_detected=True)
    tmp_job_repo.create(job)
    created = tmp_incident_repo.create_from_job(job)

    list_resp = client.get("/api/v1/incidents")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/api/v1/incidents/{created['incident_id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["incident_id"] == created["incident_id"]

    summary_resp = client.get("/api/v1/incidents/latest/summary")
    assert summary_resp.status_code == 200
    assert summary_resp.json()["incident"]["incident_id"] == created["incident_id"]
