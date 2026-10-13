"""Incident dispatch API routes: nearby responder search, SMS preview, and
explicit SMS send.

This is a separate operational layer that CONSUMES an already-completed
analysis result plus live responder locations -- it does not run
inference, does not modify Stage1/Stage2/I3D/YOLO/timeline code, and is
never called automatically by the analysis pipeline. The only way an
incident SMS is ever sent is an explicit POST /dispatch/send request
triggered by an operator action in the UI.

Reuses the EXISTING SmsGatewayService / SmsConfigStore wiring exactly as
notifications.py already does -- this module does not duplicate gateway
logic or add a second SMS implementation. The small `_get_sms_service()`
helper below is intentionally a copy of notifications.py's `_get_service()`
(not an import of it): notifications.py is explicitly off-limits to modify
for this feature, and importing a module-private `_get_service` from
another route module would be a worse coupling than duplicating ~10 lines
of dependency-wiring glue.
"""

from __future__ import annotations

import dataclasses
import logging
import re
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.core.dispatch_config import LIVE, classify_location_liveness, get_dispatch_idempotency_guard
from app.core.geo import haversine_km
from app.core.responder_store import Responder
from app.core.sms_config_store import SmsConfigStore, get_sms_config_store
from app.repositories.audit_repository import AuditRepository, get_audit_repository
from app.repositories.dispatch_repository import DispatchRepository, get_dispatch_repository
from app.repositories.mongo_job_repository import MongoDBUnavailableError
from app.repositories.responder_repository import MongoResponderRepository, get_mongo_responder_repository
from app.repositories.share_session_repository import ShareSessionRepository, get_share_session_repository
from app.schemas.dispatch import (
    DispatchPreviewRequest,
    DispatchPreviewResponse,
    DispatchSendRequest,
    DispatchSendResponse,
    EligibleResponderItem,
    EligibleResponse,
    IncidentLocation,
    ResolveMapsLinkRequest,
    ResolveMapsLinkResponse,
    NearbyResponderItem,
    NearbyResponse,
)
from app.services.sms_gateway import SmsGatewayService, get_sms_gateway_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dispatch", tags=["Dispatch"])


def _get_responder_store() -> MongoResponderRepository:
    return get_mongo_responder_repository()


def _get_dispatch_repository() -> DispatchRepository:
    return get_dispatch_repository()


def _get_audit_repository() -> AuditRepository:
    return get_audit_repository()


def _get_sms_config_store() -> SmsConfigStore:
    return get_sms_config_store()


def _get_share_repo() -> ShareSessionRepository:
    return get_share_session_repository()


def _get_sms_service(
    settings: Settings = Depends(get_settings),
    sms_store: SmsConfigStore = Depends(_get_sms_config_store),
) -> SmsGatewayService:
    """Builds a SmsGatewayService reflecting whatever SMS config is
    currently stored -- identical pattern to
    app/api/routes/notifications.py's _get_service(), duplicated rather
    than imported (see module docstring)."""
    values = sms_store.get()
    effective_settings = dataclasses.replace(
        settings,
        SMS_GATEWAY_ENABLED=values.enabled,
        SMS_GATEWAY_URL=values.url,
        SMS_GATEWAY_USERNAME=values.username,
        SMS_GATEWAY_PASSWORD=values.password,
    )
    return get_sms_gateway_service(effective_settings)


def _mask_phone(number: str) -> str:
    """Last 2 digits visible, everything else masked -- same convention as
    sms_gateway.py's own _mask_phone (not imported: that one is a private
    module-level function, this is a tiny, independent copy for API
    response masking rather than log-line masking)."""
    if not number:
        return ""
    if len(number) <= 2:
        return "*" * len(number)
    return "*" * (len(number) - 2) + number[-2:]


def _build_incident_message(
    *,
    incident_type: str,
    confidence: float | None,
    location: str | None,
    evidence_window: str | None,
    location_label: str | None = None,
    evidence_start_seconds: float | None = None,
    evidence_end_seconds: float | None = None,
) -> str:
    """Builds the canonical, concise incident SMS body server-side -- never
    trusts a client-supplied `message` (see DispatchSendRequest docstring).
    Confidence is accepted as a 0-1 fraction OR a 0-100 percentage (the
    real frontend sends raw action_confidence/anomaly_probability, both of
    which are 0-1 fractions, but this stays defensive either way).

    location_label/evidence_start_seconds/evidence_end_seconds are the
    additive structured fields (see DispatchPreviewRequest/
    DispatchSendRequest) -- preferred over the free-text location/
    evidence_window when supplied, since they're less ambiguous. Falls
    back to the free-text fields the real frontend already sends when the
    structured ones are absent, so no existing behavior changes."""
    if confidence is None:
        conf_str = "N/A"
    elif confidence <= 1:
        conf_str = f"{confidence * 100:.1f}%"
    else:
        conf_str = f"{confidence:.1f}%"

    location_str = location_label or location or "LOCATION NOT CONFIGURED"

    if evidence_start_seconds is not None and evidence_end_seconds is not None:
        evidence_str = f"{evidence_start_seconds:.2f}s–{evidence_end_seconds:.2f}s"
    else:
        evidence_str = evidence_window or "N/A"

    return (
        "SENTINEL-X INCIDENT ALERT\n\n"
        f"Type: {incident_type or 'Abnormal Activity'}\n"
        f"Confidence: {conf_str}\n\n"
        f"Location: {location_str}\n\n"
        f"Evidence: {evidence_str}\n\n"
        "Review SENTINEL-X for full incident details."
    )


def _append_incident_location_link(
    message: str,
    *,
    latitude: float | None,
    longitude: float | None,
) -> str:
    """Appends a short Google Maps link to the INCIDENT's own coordinates.

    Deliberately NOT the responder's location: the responder's own
    position is already tracked continuously from their duty-session GPS
    stream (see app/services/duty_session_service.py), so asking them to
    additionally "share" it for this one incident was redundant. A plain
    "maps.google.com/?q=lat,lng" link is short enough on its own (one SMS
    segment) that no link-shortener/redirect service is needed.

    Missing coordinates (e.g. an older client that hasn't been updated to
    send them yet) degrades to appending nothing, same fail-open behavior
    the share-link helper this replaces used to have -- a missing link
    must never block the incident SMS itself from being sent.
    """
    if latitude is None or longitude is None:
        return message
    link = f"https://maps.google.com/?q={latitude},{longitude}"
    return f"{message}\n\nIncident location: {link}"


def _dispatchable_responders(store: MongoResponderRepository) -> list[Responder]:
    """Live responders only -- stale/offline excluded. Status is NOT
    filtered here (an 'offline'-status-but-GPS-live responder is still
    geographically relevant to show; dispatch/send below is what actually
    enforces the live-location + non-offline-status gate before sending)."""
    out = []
    for r in store.list_all():
        if r.location.latitude is None or r.location.longitude is None:
            continue
        if classify_location_liveness(r.location.last_seen_at) != LIVE:
            continue
        out.append(r)
    return out


def _eligible_responders(
    store: MongoResponderRepository,
    share_repo: ShareSessionRepository,
) -> list[tuple[Responder, bool, bool, str | None]]:
    """Every responder with known GPS coordinates, annotated with on_duty /
    eligible / ineligible_reason -- used only by GET /dispatch/eligible.
    Deliberately separate from _dispatchable_responders() (used by
    GET /dispatch/nearby): that function's contract and its one existing
    caller must not change. "On duty" is cross-referenced from
    share_sessions, not from responder.status -- see
    app/repositories/share_session_repository.py's module docstring; these
    are two independent concepts in this codebase today.

    Returns a list of (responder, on_duty, eligible, ineligible_reason)
    tuples for every responder with coordinates -- including ineligible
    ones, so the caller can still compute distance/radius filtering before
    deciding what to expose; callers that only want eligible responders
    should filter on the `eligible` element themselves.
    """
    on_duty_ids = {doc["responder_id"] for doc in share_repo.list_active_duty_sessions()}
    out: list[tuple[Responder, bool, bool, str | None]] = []
    for r in store.list_all():
        if r.location.latitude is None or r.location.longitude is None:
            continue
        on_duty = r.id in on_duty_ids
        live_state = classify_location_liveness(r.location.last_seen_at)
        reasons: list[str] = []
        if not on_duty:
            reasons.append("Not on duty")
        if live_state != LIVE:
            reasons.append("Location stale" if live_state == "stale" else "Location offline")
        if not r.phone_number:
            reasons.append("No phone number on file")
        eligible = not reasons
        out.append((r, on_duty, eligible, "; ".join(reasons) if reasons else None))
    return out


@router.get("/nearby", response_model=NearbyResponse)
def nearby_responders(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=10.0, gt=0),
    limit: int | None = Query(default=None, gt=0),
    location_label: str = Query(default=""),
    store: MongoResponderRepository = Depends(_get_responder_store),
) -> NearbyResponse:
    """Finds live responders within `radius_km` of the incident coordinates,
    nearest first, using Haversine great-circle distance.

    Accepts BOTH `latitude`/`longitude` (the task spec's documented names)
    and `lat`/`lng` (what the real, already-written frontend actually
    sends -- confirmed in frontend/src/services/api.js
    getNearbyResponders()) as query params. `latitude`/`longitude` win if
    both are somehow supplied.

    Zero registered/live responders returns {"responders": []}, never
    fabricated data.
    """
    eff_lat = latitude if latitude is not None else lat
    eff_lng = longitude if longitude is not None else lng
    if eff_lat is None or eff_lng is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Incident coordinates are required: provide latitude & longitude (or lat & lng).",
        )

    try:
        candidates = _dispatchable_responders(store)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The responder database is temporarily unavailable. This does not affect video "
            "analysis or detection -- only responder/dispatch lookups are affected.",
        )
    scored: list[tuple[float, Responder]] = []
    for r in candidates:
        distance = haversine_km(eff_lat, eff_lng, r.location.latitude, r.location.longitude)
        if distance <= radius_km:
            scored.append((distance, r))

    scored.sort(key=lambda pair: pair[0])
    if limit is not None:
        scored = scored[:limit]

    items = [
        NearbyResponderItem(
            id=r.id,
            name=r.name,
            role=r.role,
            status=r.status,
            distance_km=round(distance, 3),
            last_seen_at=r.location.last_seen_at,
            phone_number=r.phone_number,
            live_state=classify_location_liveness(r.location.last_seen_at),
        )
        for distance, r in scored
    ]

    return NearbyResponse(
        incident_location=IncidentLocation(latitude=eff_lat, longitude=eff_lng, location_label=location_label),
        responders=items,
    )


@router.get("/eligible", response_model=EligibleResponse)
def eligible_responders(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=10.0, gt=0),
    limit: int | None = Query(default=None, gt=0),
    location_label: str = Query(default=""),
    store: MongoResponderRepository = Depends(_get_responder_store),
    share_repo: ShareSessionRepository = Depends(_get_share_repo),
) -> EligibleResponse:
    """Powers the AI Incident Assistant's "Forward Incident" responder
    picker: nearby responders annotated with real on-duty status and a
    server-computed eligibility verdict (on_duty AND live GPS AND has a
    phone number), nearest-eligible first.

    Deliberately a NEW, separate endpoint from GET /dispatch/nearby --
    that endpoint's existing contract and its one existing caller (the
    manual "FIND NEARBY RESPONDERS" dispatch-modal flow) are completely
    unaffected by this addition. Same dual latitude/longitude-or-lat/lng
    query convention as /nearby.

    Zero eligible responders returns {"responders": [], "eligible_count": 0}
    -- never substituted with the full responder roster, which carries no
    eligibility information.
    """
    eff_lat = latitude if latitude is not None else lat
    eff_lng = longitude if longitude is not None else lng
    if eff_lat is None or eff_lng is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Incident coordinates are required: provide latitude & longitude (or lat & lng).",
        )

    try:
        candidates = _eligible_responders(store, share_repo)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The responder database is temporarily unavailable. This does not affect video "
            "analysis or detection -- only responder/dispatch lookups are affected.",
        )

    scored: list[tuple[float, Responder, bool, bool, str | None]] = []
    for r, on_duty, eligible, reason in candidates:
        distance = haversine_km(eff_lat, eff_lng, r.location.latitude, r.location.longitude)
        if distance <= radius_km:
            scored.append((distance, r, on_duty, eligible, reason))

    scored.sort(key=lambda tup: tup[0])
    if limit is not None:
        scored = scored[:limit]

    items = [
        EligibleResponderItem(
            id=r.id,
            name=r.name,
            role=r.role,
            unit=r.unit,
            distance_km=round(distance, 3),
            last_seen_at=r.location.last_seen_at,
            phone_number=r.phone_number,
            live_state=classify_location_liveness(r.location.last_seen_at),
            on_duty=on_duty,
            eligible=eligible,
            ineligible_reason=reason,
        )
        for distance, r, on_duty, eligible, reason in scored
    ]

    return EligibleResponse(
        incident_location=IncidentLocation(latitude=eff_lat, longitude=eff_lng, location_label=location_label),
        responders=items,
        eligible_count=sum(1 for item in items if item.eligible),
    )


@router.post("/preview", response_model=DispatchPreviewResponse)
def preview_dispatch(
    request: DispatchPreviewRequest,
    responder_store: MongoResponderRepository = Depends(_get_responder_store),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> DispatchPreviewResponse:
    """Builds the exact SMS text the operator would be sending, without
    sending anything. Validates the responder exists and is currently
    dispatchable (live GPS, non-offline status).

    Deliberately never writes to the dispatches collection -- that's what
    keeps preview and send unambiguously distinguishable (see
    app/repositories/dispatch_repository.py's module docstring). Only an
    audit-log entry is recorded, same as any other operator action."""
    try:
        responder = responder_store.get(request.responder_id)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The responder database is temporarily unavailable; dispatch preview cannot proceed.",
        )
    if responder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown responder_id: {request.responder_id}")

    live_state = classify_location_liveness(responder.location.last_seen_at)
    if live_state != LIVE:
        return DispatchPreviewResponse(
            success=False,
            recipient=_mask_phone(responder.phone_number),
            responder_name=responder.name,
            distance_km=None,
            message="",
            preview_text="",
            error=f"Responder '{responder.name}' is not currently live (status: {live_state}).",
        )

    message = _build_incident_message(
        incident_type=request.incident_type,
        confidence=request.confidence if request.confidence is not None else request.action_confidence,
        location=request.location,
        evidence_window=request.evidence_window,
        location_label=request.location_label,
        evidence_start_seconds=request.evidence_start_seconds,
        evidence_end_seconds=request.evidence_end_seconds,
    )
    audit_repo.log(
        "dispatch_preview",
        details={"responder_id": request.responder_id, "job_id": request.job_id},
    )
    return DispatchPreviewResponse(
        success=True,
        recipient=_mask_phone(responder.phone_number),
        responder_name=responder.name,
        distance_km=None,
        message=message,
        preview_text=message,
    )


@router.post("/send", response_model=DispatchSendResponse)
def send_dispatch(
    request: DispatchSendRequest,
    settings: Settings = Depends(get_settings),
    responder_store: MongoResponderRepository = Depends(_get_responder_store),
    sms_service: SmsGatewayService = Depends(_get_sms_service),
    dispatch_repo: DispatchRepository = Depends(_get_dispatch_repository),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> DispatchSendResponse:
    """The ONLY endpoint that sends an incident SMS. Explicit operator
    action only -- never called automatically by anomaly detection,
    polling, the timeline, page load, or a responder location update.

    1. Validates the responder exists.
    2. Verifies the responder is currently live (not stale/offline). A
       responder's OWN location is already tracked continuously from their
       duty-session GPS stream (see app/services/duty_session_service.py)
       -- the operator does not need them to additionally "share" it for
       a specific incident, which is why this no longer mints a share
       session or asks the responder to do anything.
    3. Builds the incident message server-side (ignores any client-supplied
       `message`/`recipient` -- see DispatchSendRequest docstring),
       including a short Google Maps link to the INCIDENT's location (not
       the responder's), so the message stays short enough for a single
       SMS segment.
    4. Sends through the EXISTING SmsGatewayService.send_sms() -- no second
       SMS implementation.
    5. Returns a truthful result: never claims success unless the gateway
       call itself succeeded.

    Double-click protection: a short-lived idempotency guard keyed on
    (responder_id, idempotency_key or job_id) suppresses a near-instant
    repeat request from sending a second real SMS; the repeat gets back
    deduplicated=True with the same success/message as the original.
    """
    try:
        responder = responder_store.get(request.responder_id)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The responder database is temporarily unavailable; dispatch send cannot proceed. No SMS was sent.",
        )
    if responder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown responder_id: {request.responder_id}")

    live_state = classify_location_liveness(responder.location.last_seen_at)
    if live_state != LIVE:
        return DispatchSendResponse(
            success=False,
            message="SMS not sent.",
            error=f"Responder '{responder.name}' is not currently live (status: {live_state}); dispatch refused.",
        )

    if not responder.phone_number:
        return DispatchSendResponse(
            success=False,
            message="SMS not sent.",
            error=f"Responder '{responder.name}' has no phone number on file.",
        )

    idempotency_key = request.idempotency_key or request.job_id or ""
    guard_key = f"{request.responder_id}:{idempotency_key}"
    guard = get_dispatch_idempotency_guard()
    is_new = guard.check_and_mark(guard_key) if idempotency_key else True

    if not is_new:
        # A near-duplicate request within the guard window -- report the
        # same outcome shape without sending a second real SMS, and
        # deliberately without creating a second share session either (that
        # would silently invalidate/duplicate the link the responder may
        # already be looking at from the first, real send).
        return DispatchSendResponse(success=True, message="SMS already dispatched.", deduplicated=True)

    message = _build_incident_message(
        incident_type=request.incident_type,
        confidence=request.confidence if request.confidence is not None else request.action_confidence,
        location=request.location,
        evidence_window=request.evidence_window,
        location_label=request.location_label,
        evidence_start_seconds=request.evidence_start_seconds,
        evidence_end_seconds=request.evidence_end_seconds,
    )
    # Append a short Google Maps link to the INCIDENT's own coordinates --
    # not a "share your location" ask, since the responder's location is
    # already tracked continuously from their duty-session GPS stream (see
    # app/services/duty_session_service.py). A plain "?q=lat,lng" link is
    # short enough on its own that no separate link-shortener is needed.
    message = _append_incident_location_link(message, latitude=request.latitude, longitude=request.longitude)

    result = sms_service.send_sms(responder.phone_number, message)

    # Persist the send attempt -- never the SMS gateway password, which
    # SmsResult structurally cannot carry (success/message/error only; see
    # app/services/sms_gateway.py). No incident entity is wired through this
    # request today, so job_id (if supplied) stands in as the incident
    # reference -- additive persistence only, the response shape below is
    # unchanged either way.
    dispatch_repo.record_send(
        incident_id=request.job_id,
        responder_id=request.responder_id,
        message=message,
        success=result.success,
        error=result.error,
    )
    audit_repo.log(
        "dispatch_sent" if result.success else "dispatch_failed",
        actor="operator",
        module="dispatch",
        resource_type="responder",
        resource_id=request.responder_id,
        outcome="success" if result.success else "failure",
        summary=(
            f"Dispatched {responder.name or request.responder_id} to "
            f"{request.incident_type or 'incident'}"
            if result.success
            else f"Dispatch to {responder.name or request.responder_id} failed: {result.error or 'unknown error'}"
        ),
        details={
            "responder_id": request.responder_id,
            "responder_name": responder.name,
            "responder_phone": responder.phone_number,
            "job_id": request.job_id,
            "incident_id": request.incident_id,
            "incident_type": request.incident_type,
            "confidence": request.confidence if request.confidence is not None else request.action_confidence,
            # Real incident location used to build the SMS maps link above --
            # this is what lets the LIVE GPS map later look up "where was this
            # responder dispatched to" from the audit log, since there is no
            # separate persistent assignment record (see send_dispatch
            # docstring point 3 and dispatch_repo.record_send above).
            "incident_latitude": request.latitude,
            "incident_longitude": request.longitude,
            "incident_location_label": request.location_label,
            "message": message,
        },
    )

    return DispatchSendResponse(success=result.success, message=result.message, error=result.error)


# Matches the "@lat,lng,zoom" segment Google Maps embeds in both full and
# resolved-shortlink URLs, e.g. ".../@16.4044521,74.3790313,17z/...".
_MAPS_COORDS_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")
# Fallback: a bare "?q=lat,lng" or "q=lat,lng" query param, used by the
# simple maps.google.com/?q=... link format this same feature generates
# for the incident-location SMS link above.
_MAPS_QUERY_RE = re.compile(r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)")


@router.post("/resolve-maps-link", response_model=ResolveMapsLinkResponse)
def resolve_maps_link(request: ResolveMapsLinkRequest) -> ResolveMapsLinkResponse:
    """Resolves a Google Maps link (full or shortened maps.app.goo.gl) to
    latitude/longitude, for the "set incident location" settings control in
    the UI (an operator pastes a link instead of typing raw coordinates).

    A shortened link's final destination can only be read by actually
    following the redirect -- browser JS cannot do this across origins --
    so this always happens server-side. Never raises on a bad/unreachable
    link; returns success=False with an error message instead, since this
    is an operator-convenience lookup, not a precondition for anything.
    """
    url = request.url.strip()
    if not url:
        return ResolveMapsLinkResponse(success=False, error="No link provided.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"

    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return ResolveMapsLinkResponse(success=False, error="That doesn't look like a valid URL.")

    allowed_hosts = {"maps.app.goo.gl", "goo.gl", "maps.google.com", "google.com", "www.google.com"}
    if parsed.hostname not in allowed_hosts:
        return ResolveMapsLinkResponse(
            success=False,
            error="Only Google Maps links (maps.app.goo.gl or google.com/maps) are supported.",
        )

    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as http_client:
            resp = http_client.get(url)
        final_url = str(resp.url)
    except httpx.HTTPError as exc:
        logger.warning("Failed to resolve Maps link %r: %s", url, exc)
        return ResolveMapsLinkResponse(success=False, error="Could not reach that link. Check it and try again.")

    match = _MAPS_COORDS_RE.search(final_url) or _MAPS_QUERY_RE.search(final_url)
    if not match:
        return ResolveMapsLinkResponse(
            success=False,
            error="Couldn't find coordinates in that link. Try sharing a pinned location from Google Maps.",
        )

    latitude, longitude = float(match.group(1)), float(match.group(2))

    label = None
    place_match = re.search(r"/maps/place/([^/@]+)", final_url)
    if place_match:
        label = urllib.parse.unquote(place_match.group(1)).replace("+", " ")

    return ResolveMapsLinkResponse(success=True, latitude=latitude, longitude=longitude, label=label)
