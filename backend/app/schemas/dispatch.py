"""Pydantic schemas for the incident dispatch API.

Kept separate from app/schemas/analysis.py and notifications.py: dispatch is
a distinct operational layer that CONSUMES an already-completed analysis
result plus a selected responder -- it does not run inference and does not
belong inside the anomaly pipeline's own schemas.

Field names in NearbyResponderItem/DispatchPreviewRequest/DispatchSendRequest
are confirmed against the real, already-written frontend
(frontend/src/services/api.js: previewDispatch/sendDispatch/
getNearbyResponders) rather than assumed -- that code sends `confidence`
(a single collapsed number, not `action_confidence`), `location` (a
free-text label string, not separate lat/lon), `evidence_window` (a
pre-formatted string like "12.34s - 45.67s", not separate start/end
floats), and `job_id`. The backend accepts these exact names so the already
-existing frontend integration code works without modification, while
`DispatchIncidentPayload` (used internally and by any stricter caller)
keeps the fuller, more structured fields the task spec also asks for.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class IncidentLocation(BaseModel):
    """Real incident coordinates -- never invented by the backend. The
    caller (frontend, using the camera/site's configured location) must
    supply these."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    location_label: str = Field(default="")


class NearbyResponderItem(BaseModel):
    id: str
    name: str
    role: str
    status: str
    distance_km: float
    last_seen_at: str | None
    phone_number: str
    live_state: str = Field(description="One of 'live', 'stale', 'offline'.")


class NearbyResponse(BaseModel):
    incident_location: IncidentLocation
    responders: list[NearbyResponderItem] = Field(default_factory=list)


class EligibleResponderItem(BaseModel):
    """Like NearbyResponderItem, plus duty-status and a server-computed
    eligibility verdict -- used by GET /dispatch/eligible (the AI Incident
    Assistant's "Forward Incident" responder picker), kept as a separate
    schema rather than adding these fields to NearbyResponderItem so
    GET /dispatch/nearby's existing response contract and callers are
    completely unaffected."""

    id: str
    name: str
    role: str
    unit: str
    distance_km: float
    last_seen_at: str | None
    phone_number: str
    live_state: str = Field(description="One of 'live', 'stale', 'offline'.")
    on_duty: bool = Field(description="True iff the responder has an ACTIVE (not merely pending) duty session right now.")
    eligible: bool = Field(description="True iff on_duty AND live_state == 'live' AND phone_number is non-empty.")
    ineligible_reason: str | None = Field(
        default=None,
        description="Populated only when eligible is False -- e.g. 'Not on duty', 'Location stale', 'No phone number on file'.",
    )


class EligibleResponse(BaseModel):
    incident_location: IncidentLocation
    responders: list[EligibleResponderItem] = Field(default_factory=list)
    eligible_count: int = 0


class DispatchPreviewRequest(BaseModel):
    """Matches frontend/src/services/api.js previewDispatch() exactly.
    `location`/`evidence_window` are free-text, already-formatted strings
    from the frontend -- this endpoint does not reconstruct them from raw
    analysis fields, it trusts what the operator is actually looking at on
    screen (same text that will appear in the SMS).

    The fuller structured fields below (incident_id/incident_timestamp/
    anomaly_probability/likely_action/action_confidence/evidence_start_
    seconds/evidence_end_seconds/latitude/longitude) are ADDITIVE and all
    optional -- a stricter caller can supply these instead of the free-text
    fields, and _build_incident_message (dispatch.py) prefers them when
    present, falling back to the free-text fields otherwise. Nothing about
    the existing, already-working frontend contract is removed or changed."""

    responder_id: str
    incident_type: str = Field(default="Abnormal Activity")
    confidence: float | None = Field(default=None, ge=0, le=1)
    location: str | None = Field(default=None)
    evidence_window: str | None = Field(default=None)
    job_id: str | None = Field(default=None)

    # -- additive structured fields (all optional) --
    incident_id: str | None = Field(default=None)
    incident_timestamp: str | None = Field(default=None, description="ISO 8601 timestamp of the incident, if known.")
    anomaly_probability: float | None = Field(default=None, ge=0, le=1)
    likely_action: str | None = Field(default=None)
    action_confidence: float | None = Field(default=None, ge=0, le=1)
    location_label: str | None = Field(default=None)
    latitude: float | None = Field(default=None, ge=-90, le=90, description="Incident latitude, if known.")
    longitude: float | None = Field(default=None, ge=-180, le=180, description="Incident longitude, if known.")
    evidence_start_seconds: float | None = Field(default=None, ge=0)
    evidence_end_seconds: float | None = Field(default=None, ge=0)


class DispatchPreviewResponse(BaseModel):
    success: bool = True
    recipient: str = Field(description="Masked phone number for operator confirmation, e.g. '+91•••••••89'.")
    responder_name: str
    distance_km: float | None = None
    message: str
    preview_text: str = Field(description="Identical to `message` -- the real frontend reads either field name.")
    error: str | None = None


class DispatchSendRequest(BaseModel):
    """Matches frontend/src/services/api.js sendDispatch() exactly. `message`
    is accepted but NOT trusted as-is for the actual SMS body -- the backend
    rebuilds the canonical incident message server-side from the structured
    fields, so the real device-to-device text can't be tampered with by a
    stale/edited client payload. `recipient` likewise is accepted but
    ignored in favor of the responder's own stored phone_number, so a
    tampered/incorrect recipient in the request body can never redirect an
    incident alert to the wrong number."""

    responder_id: str
    recipient: str | None = Field(default=None, description="Accepted for frontend compatibility; ignored -- the responder's own stored phone number is always used.")
    message: str | None = Field(default=None, description="Accepted for frontend compatibility; ignored -- the SMS body is always rebuilt server-side from the structured fields below.")
    incident_type: str = Field(default="Abnormal Activity")
    confidence: float | None = Field(default=None, ge=0, le=1)
    location: str | None = Field(default=None)
    evidence_window: str | None = Field(default=None)
    job_id: str | None = Field(default=None)
    idempotency_key: str | None = Field(
        default=None,
        description="Optional client-supplied key (e.g. f'{job_id}:{responder_id}') to guard against accidental double-click dispatch. When omitted, (job_id, responder_id) is used instead.",
    )

    # -- additive structured fields (all optional); see DispatchPreviewRequest --
    incident_id: str | None = Field(default=None)
    incident_timestamp: str | None = Field(default=None)
    anomaly_probability: float | None = Field(default=None, ge=0, le=1)
    likely_action: str | None = Field(default=None)
    action_confidence: float | None = Field(default=None, ge=0, le=1)
    location_label: str | None = Field(default=None)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    evidence_start_seconds: float | None = Field(default=None, ge=0)
    evidence_end_seconds: float | None = Field(default=None, ge=0)


class DispatchSendResponse(BaseModel):
    success: bool
    message: str
    error: str | None = None
    deduplicated: bool = Field(
        default=False,
        description="True if this request was recognized as a repeat of a very recent send and the SMS was NOT sent again -- the response reflects the original send's outcome.",
    )


class ResolveMapsLinkRequest(BaseModel):
    """A Google Maps link pasted by an operator to set a video source's
    incident location (settings button in the UI, replacing manual lat/lng
    entry). Accepts both full maps.google.com URLs and shortened
    maps.app.goo.gl links -- the latter require following a redirect
    server-side, since browser JS cannot read a cross-origin redirect's
    final URL itself."""

    url: str = Field(..., min_length=1, max_length=2048)


class ResolveMapsLinkResponse(BaseModel):
    success: bool
    latitude: float | None = None
    longitude: float | None = None
    label: str | None = Field(default=None, description="Place name extracted from the URL, if present.")
    error: str | None = None
