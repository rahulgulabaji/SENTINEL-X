"""Pydantic schemas for the AI Incident Assistant's latest-incident-summary
endpoint. Kept separate from app/schemas/analysis.py: this is a UI-facing
projection built by app/services/incident_summary_service.py, not a stored
entity -- IncidentResponse remains the canonical incident shape."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.analysis import IncidentResponse


class AiDetectedFields(BaseModel):
    """Model-produced fields only -- never a verified/operational fact.
    Any field is None when its source data was unavailable; never
    interpolated or guessed."""

    likely_action: str | None = None
    anomaly_probability: float | None = None
    action_confidence: float | None = None
    action_candidates: list[dict] | None = None


class VerifiedFacts(BaseModel):
    """Operational record fields -- not a model inference."""

    incident_id: str | None = None
    status: str | None = None
    created_at: str | None = None
    job_id: str | None = None


class EvidenceSummary(BaseModel):
    available: bool = False
    window_start_seconds: float | None = None
    window_end_seconds: float | None = None


class LocationSummary(BaseModel):
    label: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    available: bool = False


class IncidentSummary(BaseModel):
    incident_id: str | None = None
    status: str | None = None
    created_at: str | None = None
    job_id: str | None = None
    headline: str
    ai_detected: AiDetectedFields
    verified_facts: VerifiedFacts
    evidence: EvidenceSummary | None = None
    location: LocationSummary
    model_info: dict | None = None
    limitations: list[str] = Field(default_factory=list)


class LatestIncidentSummaryResponse(BaseModel):
    """`incident`/`summary` are both None when no incident exists yet --
    a normal, honest empty state, not an error."""

    incident: IncidentResponse | None = None
    summary: IncidentSummary | None = None


class LatestIncidentAiSummaryResponse(BaseModel):
    """Powers the AI COPILOT tab -- see
    app/services/grok_summary_service.py. `ai_summary_source` is "grok" only
    when `ai_summary_text` actually came from a live xAI call; "fallback"
    means it's a deterministic, non-LLM summary built from `summary`'s own
    fields (Grok disabled/unconfigured, or the live call failed) --
    `ai_summary_error` then carries the real reason. All four
    `ai_summary_*`/`incident`/`summary` fields are None together when no
    incident exists yet -- a normal, honest empty state, not an error.
    Never carries the xAI API key or any raw incident/job document."""

    incident: IncidentResponse | None = None
    summary: IncidentSummary | None = None
    ai_summary_text: str | None = None
    ai_summary_source: str | None = None
    ai_summary_error: str | None = None
