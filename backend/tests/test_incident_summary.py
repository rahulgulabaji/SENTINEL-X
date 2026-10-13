"""Tests for app.services.incident_summary_service.build_incident_summary --
a pure function, no mongomock/FastAPI needed here.

Run from backend/: pytest tests/test_incident_summary.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.incident_summary_service import build_incident_summary  # noqa: E402


def _incident(**overrides) -> dict:
    base = {
        "incident_id": "inc-1",
        "job_id": "job-1",
        "status": "open",
        "anomaly_probability": 0.91,
        "likely_action": "Fence Breach",
        "action_confidence": 0.82,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _job(**overrides) -> dict:
    base = {
        "job_id": "job-1",
        "status": "completed",
        "filename": "clip.mp4",
        "anomaly_detected": True,
        "anomaly_probability": 0.93,
        "likely_action": "Fence Breach",
        "action_confidence": 0.85,
        "action_candidates": [{"class_name": "Fence Breach", "probability": 0.85}],
        "model_info": {"stage1_name": "s1", "stage2_name": "s2", "i3d_backbone": "rgb"},
        "temporal_evidence": {
            "available": True,
            "window_duration_seconds": 2.0,
            "windows": [
                {
                    "window_index": 0,
                    "start_time_seconds": 10.0,
                    "end_time_seconds": 12.0,
                    "stage1_attention": 0.5,
                    "stage1_attention_normalized": 0.5,
                },
                {
                    "window_index": 1,
                    "start_time_seconds": 12.0,
                    "end_time_seconds": 14.0,
                    "stage1_attention": 0.9,
                    "stage1_attention_normalized": 0.9,
                },
            ],
        },
        "location": "Main Gate Camera",
        "latitude": 16.70,
        "longitude": 74.20,
    }
    base.update(overrides)
    return base


def test_job_none_degrades_gracefully_without_fabricating():
    summary = build_incident_summary(_incident(), job=None)
    assert summary["evidence"] is None
    assert summary["location"] == {"label": None, "latitude": None, "longitude": None, "available": False}
    assert summary["model_info"] is None
    assert "Linked analysis job could not be loaded; evidence and location details are unavailable." in summary["limitations"]


def test_severity_limitation_always_present_regardless_of_input():
    summary_no_job = build_incident_summary(_incident(), job=None)
    summary_with_job = build_incident_summary(_incident(), job=_job())
    assert "Severity/priority is not tracked by this system." in summary_no_job["limitations"]
    assert "Severity/priority is not tracked by this system." in summary_with_job["limitations"]


def test_full_incident_and_job_populates_ai_detected_from_job():
    summary = build_incident_summary(_incident(), job=_job())
    assert summary["ai_detected"]["likely_action"] == "Fence Breach"
    assert summary["ai_detected"]["anomaly_probability"] == 0.93  # from job, not incident's 0.91
    assert summary["ai_detected"]["action_confidence"] == 0.85
    assert summary["ai_detected"]["action_candidates"] == [{"class_name": "Fence Breach", "probability": 0.85}]


def test_verified_facts_always_from_incident_not_job():
    summary = build_incident_summary(_incident(), job=_job())
    assert summary["verified_facts"] == {
        "incident_id": "inc-1",
        "status": "open",
        "created_at": "2025-01-01T00:00:00+00:00",
        "job_id": "job-1",
    }


def test_evidence_extracted_from_job_temporal_windows():
    summary = build_incident_summary(_incident(), job=_job())
    assert summary["evidence"] == {
        "available": True,
        "window_start_seconds": 10.0,
        "window_end_seconds": 14.0,
    }


def test_location_extracted_from_job_when_present():
    summary = build_incident_summary(_incident(), job=_job())
    assert summary["location"] == {
        "label": "Main Gate Camera",
        "latitude": 16.70,
        "longitude": 74.20,
        "available": True,
    }
    assert "Location data is not available for this incident." not in summary["limitations"]


def test_location_unavailable_limitation_when_job_has_no_location():
    job = _job(location=None, latitude=None, longitude=None)
    summary = build_incident_summary(_incident(), job=job)
    assert summary["location"]["available"] is False
    assert "Location data is not available for this incident." in summary["limitations"]


def test_headline_falls_back_when_likely_action_missing():
    summary = build_incident_summary(_incident(likely_action=None), job=None)
    assert summary["headline"].startswith("Unclassified activity detected")


def test_headline_includes_action_and_timestamp():
    summary = build_incident_summary(_incident(), job=None)
    assert "Fence Breach" in summary["headline"]
    assert "2025-01-01T00:00:00+00:00" in summary["headline"]


def test_never_fabricates_a_numeric_fallback():
    """Regression guard: no field is ever filled with a hardcoded/invented
    placeholder value (e.g. 0.572) when the real source data is absent."""
    incident = _incident(anomaly_probability=None, action_confidence=None, likely_action=None)
    summary = build_incident_summary(incident, job=None)
    assert summary["ai_detected"]["anomaly_probability"] is None
    assert summary["ai_detected"]["action_confidence"] is None
    assert summary["ai_detected"]["likely_action"] is None


def test_job_present_but_missing_fields_falls_back_to_incident_snapshot():
    job = _job(anomaly_probability=None, action_confidence=None)
    summary = build_incident_summary(_incident(), job=job)
    # Job has no value for these -- falls back to the incident's own real
    # snapshot values rather than reporting None when a real value exists.
    assert summary["ai_detected"]["anomaly_probability"] == 0.91
    assert summary["ai_detected"]["action_confidence"] == 0.82


def test_does_not_raise_on_minimal_incident():
    minimal = {
        "incident_id": "inc-2",
        "job_id": None,
        "status": "open",
        "anomaly_probability": None,
        "likely_action": None,
        "action_confidence": None,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    }
    summary = build_incident_summary(minimal, job=None)
    assert summary["incident_id"] == "inc-2"
    assert summary["job_id"] is None
