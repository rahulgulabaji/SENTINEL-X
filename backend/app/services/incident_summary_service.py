"""Deterministic, non-LLM incident summary builder.

Produces a structured summary -- not one opaque string -- so a caller (API
route, frontend) can render "AI-detected" (model-produced) fields visually
distinct from "verified facts" (operational record fields) without parsing
free text. This keeps the AI Incident Assistant's summary honest: every
field here is either copied straight from a real incident/job document or
is explicitly None, never interpolated or guessed.

Deliberately a pure function with no I/O, no FastAPI/Pydantic dependency --
same philosophy as app/core/geo.py. This is "lightweight/deterministic" by
design (per the AI Incident Assistant task): a future Grok-backed rewrite
can replace this module's internals while returning the exact same shape,
so no caller needs to change.

The incidents collection (see app/repositories/incident_repository.py) has
no location/type/severity/priority field -- not on the incident, not on the
linked analysis job. This module never invents one:
- "type" is derived from likely_action (falls back to a generic phrase).
- "severity"/"priority" has no backing field anywhere in this system and is
  never bucketed from anomaly_probability -- `limitations` always says so
  explicitly instead.
- "location" comes only from the linked job's own location/camera_location
  fields, if present.
"""

from __future__ import annotations

from typing import Any

_SEVERITY_LIMITATION = "Severity/priority is not tracked by this system."
_NO_JOB_LIMITATION = "Linked analysis job could not be loaded; evidence and location details are unavailable."
_NO_LOCATION_LIMITATION = "Location data is not available for this incident."


def _build_headline(incident: dict[str, Any]) -> str:
    likely_action = incident.get("likely_action")
    created_at = incident.get("created_at")
    action_text = likely_action if likely_action else "Unclassified activity"
    if created_at:
        return f"{action_text} detected at {created_at}."
    return f"{action_text} detected."


def _extract_location(job: dict[str, Any] | None) -> dict[str, Any]:
    if job is None:
        return {"label": None, "latitude": None, "longitude": None, "available": False}
    label = job.get("location") or job.get("camera_location")
    latitude = job.get("latitude")
    longitude = job.get("longitude")
    available = bool(label) or (latitude is not None and longitude is not None)
    return {"label": label, "latitude": latitude, "longitude": longitude, "available": available}


def _extract_evidence(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if job is None:
        return None
    temporal_evidence = job.get("temporal_evidence")
    if not temporal_evidence or not temporal_evidence.get("available"):
        return {"available": False, "window_start_seconds": None, "window_end_seconds": None}
    windows = temporal_evidence.get("windows") or []
    if not windows:
        return {"available": False, "window_start_seconds": None, "window_end_seconds": None}
    start = min(w.get("start_time_seconds") for w in windows if w.get("start_time_seconds") is not None)
    end = max(w.get("end_time_seconds") for w in windows if w.get("end_time_seconds") is not None)
    return {"available": True, "window_start_seconds": start, "window_end_seconds": end}


def build_incident_summary(incident: dict[str, Any], job: dict[str, Any] | None) -> dict[str, Any]:
    """Builds a structured summary from a real incident document and its
    (optionally None) linked analysis job document.

    incident: a raw dict as returned by IncidentRepository (incident_id,
      job_id, status, anomaly_probability, likely_action, action_confidence,
      created_at, updated_at).
    job: a raw dict matching AnalysisResult's fields for incident['job_id'],
      or None if the job could not be fetched (database unavailable, job
      not found, or incident has no job_id). Never raises on a missing or
      partial job -- degrades gracefully with explicit limitations instead.

    AI-detected fields (ai_detected) are preferred from the job when
    present (the job is the authoritative, richer record), falling back to
    the incident's own snapshot values only when the job is unavailable --
    the incident's anomaly_probability/action_confidence are real values
    captured at creation time, not fabricated.
    """
    ai_detected = {
        "likely_action": (job.get("likely_action") if job else None) or incident.get("likely_action"),
        "anomaly_probability": (job.get("anomaly_probability") if job else None)
        if job is not None
        else incident.get("anomaly_probability"),
        "action_confidence": (job.get("action_confidence") if job else None)
        if job is not None
        else incident.get("action_confidence"),
        "action_candidates": job.get("action_candidates") if job else None,
    }
    # When a job IS present but a specific field is absent on it, still
    # fall back to the incident's own snapshot rather than reporting None
    # for a value we actually have.
    if job is not None:
        if ai_detected["anomaly_probability"] is None:
            ai_detected["anomaly_probability"] = incident.get("anomaly_probability")
        if ai_detected["action_confidence"] is None:
            ai_detected["action_confidence"] = incident.get("action_confidence")

    verified_facts = {
        "incident_id": incident.get("incident_id"),
        "status": incident.get("status"),
        "created_at": incident.get("created_at"),
        "job_id": incident.get("job_id"),
    }

    limitations: list[str] = [_SEVERITY_LIMITATION]
    if job is None:
        limitations.append(_NO_JOB_LIMITATION)

    location = _extract_location(job)
    if not location["available"]:
        limitations.append(_NO_LOCATION_LIMITATION)

    return {
        "incident_id": incident.get("incident_id"),
        "status": incident.get("status"),
        "created_at": incident.get("created_at"),
        "job_id": incident.get("job_id"),
        "headline": _build_headline(incident),
        "ai_detected": ai_detected,
        "verified_facts": verified_facts,
        "evidence": _extract_evidence(job),
        "location": location,
        "model_info": job.get("model_info") if job else None,
        "limitations": limitations,
    }
