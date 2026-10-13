"""Responder registry + live GPS location API routes.

Mirrors app/api/routes/notifications.py's structure (Depends()-based store
wiring, same router-registration convention in main.py). Knows nothing
about anomaly inference, YOLO, or the analysis pipeline -- this is a
standalone operational registry that app/api/routes/dispatch.py queries.

No fake/demo responders are ever created by this module. GET /responders
with zero registered responders returns [], not fabricated data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

import dataclasses

from app.core.config import Settings, get_settings
from app.core.dispatch_config import classify_location_liveness
from app.core.rate_limit import get_chat_auth_rate_limiter
from app.core.responder_auth import generate_pin, hash_password, hash_pin, verify_password
from app.core.responder_store import Responder, VALID_STATUSES, normalize_status
from app.core.share_tokens import issue_token
from app.core.sms_config_store import SmsConfigStore, get_sms_config_store
from app.repositories.audit_repository import AuditRepository, get_audit_repository
from app.repositories.mongo_job_repository import MongoDBUnavailableError
from app.repositories.responder_repository import MongoResponderRepository, get_mongo_responder_repository
from app.repositories.share_session_repository import ShareSessionRepository, get_share_session_repository
from app.schemas.notifications import SendDutyLinkResponse
from app.schemas.responders import (
    ResponderCreateRequest,
    ResponderCreateResponse,
    ResponderLocationResponse,
    ResponderLoginRequest,
    ResponderLoginResponse,
    ResponderPinReissueResponse,
    ResponderResponse,
    ResponderUpdateRequest,
    UpdateLocationRequest,
)
from app.services.duty_session_service import end_duty_session, start_or_resume_duty_session
from app.services.sms_gateway import SmsGatewayService, get_sms_gateway_service

router = APIRouter(prefix="/v1/responders", tags=["Responders"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_store() -> MongoResponderRepository:
    # No db arg here, same reasoning as notifications.py's
    # _get_config_store(): calling get_mongo_responder_repository(db) on
    # every request would rebuild a brand new repository each time rather
    # than reuse the process-wide MongoClient. The database handle is only
    # consulted *inside* get_mongo_responder_repository() the one time it
    # lazily builds the real singleton.
    return get_mongo_responder_repository()


def _get_audit_repository() -> AuditRepository:
    return get_audit_repository()


def _get_sms_config_store() -> SmsConfigStore:
    return get_sms_config_store()


def _get_sms_service(
    settings: Settings = Depends(get_settings),
    store: SmsConfigStore = Depends(_get_sms_config_store),
) -> SmsGatewayService:
    """Same construction as app/api/routes/notifications.py's own
    _get_service(): read whatever SMS config is currently stored
    (UI-edited values if any exist, otherwise .env), build a fresh
    Settings-shaped object with only the SMS_GATEWAY_* fields overridden,
    and hand that to get_sms_gateway_service(). Duplicated here rather than
    imported from notifications.py because that module's _get_service is a
    private route-local dependency, not a shared export -- same
    not-sharing-private-helpers-across-route-modules convention already
    followed elsewhere in this codebase."""
    values = store.get()
    effective_settings = dataclasses.replace(
        settings,
        SMS_GATEWAY_ENABLED=values.enabled,
        SMS_GATEWAY_URL=values.url,
        SMS_GATEWAY_USERNAME=values.username,
        SMS_GATEWAY_PASSWORD=values.password,
    )
    return get_sms_gateway_service(effective_settings)


def _to_response(responder: Responder) -> ResponderResponse:
    live_state = classify_location_liveness(responder.location.last_seen_at)
    return ResponderResponse(
        id=responder.id,
        name=responder.name,
        phone_number=responder.phone_number,
        role=responder.role,
        unit=responder.unit,
        status=responder.status,
        latitude=responder.location.latitude,
        longitude=responder.location.longitude,
        accuracy_meters=responder.location.accuracy_meters,
        last_seen_at=responder.location.last_seen_at,
        live_state=live_state,
        created_at=responder.created_at,
        updated_at=responder.updated_at,
        username=responder.username,
    )


_MONGO_UNAVAILABLE_DETAIL = (
    "The responder database is temporarily unavailable. This does not affect "
    "video analysis, YOLO detection, or the inference pipeline -- only "
    "responder registration, GPS tracking, and incident dispatch are affected."
)


@router.get("", response_model=list[ResponderResponse])
def list_responders(store: ResponderStore = Depends(_get_store)) -> list[ResponderResponse]:
    """Registered responders. Returns [] when none are registered -- never
    fabricated/demo data."""
    try:
        return [_to_response(r) for r in store.list_all()]
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)


@router.post("", response_model=ResponderCreateResponse, status_code=status.HTTP_201_CREATED)
def create_responder(
    request: ResponderCreateRequest,
    store: ResponderStore = Depends(_get_store),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> ResponderCreateResponse:
    if request.status and request.status.strip().lower() not in VALID_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid status '{request.status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}.",
        )
    # username/password are both optional (a responder can be PIN-only),
    # but a half-supplied pair is always a client error -- never silently
    # drop the one that was given.
    if bool(request.username) != bool(request.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Both username and password must be provided together.")

    username_hash_kwargs: dict = {}
    if request.username:
        # Pre-check for a duplicate username with a clear 400 before
        # attempting the insert -- the unique index (app/core/mongodb.py)
        # is the real enforcement (handles a race between two concurrent
        # creates), this is just a friendlier error message for the
        # common, non-racing case.
        try:
            existing = store.get_by_username(request.username)
        except MongoDBUnavailableError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
        if existing is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Username '{request.username}' is already taken.")
        username_hash_kwargs = {"username": request.username, "password_hash": hash_password(request.password)}

    # PIN and (if given) password are generated/hashed here, in the route
    # layer -- the repository stays a dumb persistence layer and never
    # sees either raw credential after this point (see
    # app/core/responder_auth.py).
    raw_pin = generate_pin()
    try:
        responder = store.create(
            id=request.id,
            name=request.name,
            phone_number=request.phone_number,
            role=request.role,
            unit=request.unit,
            status=normalize_status(request.status),
            pin_hash=hash_pin(raw_pin),
            pin_issued_at=_utcnow_iso(),
            **username_hash_kwargs,
        )
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    except Exception as exc:  # pragma: no cover - defensive: unique-index race
        if "duplicate key" in str(exc).lower():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Username '{request.username}' is already taken.")
        raise
    # Logged only after the real create() above has actually succeeded --
    # never claim a responder was registered if persistence failed. Neither
    # credential is ever included in the audit summary/details.
    audit_repo.log(
        "responder_created",
        module="responders",
        resource_type="responder",
        resource_id=responder.id,
        summary=f"Responder '{responder.name}' registered.",
    )
    base = _to_response(responder)
    return ResponderCreateResponse(**base.model_dump(), pin=raw_pin, password=request.password)


@router.post("/{responder_id}/send-duty-link", response_model=SendDutyLinkResponse)
def send_duty_link(
    responder_id: str,
    store: MongoResponderRepository = Depends(_get_store),
    sms_service: SmsGatewayService = Depends(_get_sms_service),
    settings: Settings = Depends(get_settings),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> SendDutyLinkResponse:
    """Sends the officer their real duty-page link by SMS -- the page they
    land on requires a username/password login before any duty controls or
    location sharing are available (see POST /v1/responders/login).

    This replaces the frontend's previous fallback of repurposing
    POST /v1/notifications/test-sms, which always sent a hardcoded
    "SENTINEL-X test notification." body and silently discarded whatever
    real message the caller tried to send -- the officer received a
    generic test SMS instead of their actual duty link. This endpoint
    builds and sends the real message directly, with no such mismatch
    possible since there's no second caller-supplied `message` field to
    ignore.
    """
    try:
        responder = store.get(responder_id)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if responder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown responder_id: {responder_id}")
    if not responder.phone_number:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Officer '{responder.name}' has no phone number on file.")
    if not settings.PUBLIC_BASE_URL:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "PUBLIC_BASE_URL is not configured on the server, so no reachable duty link can be sent.",
        )

    duty_url = f"{settings.PUBLIC_BASE_URL}/responder/duty/{responder_id}"
    message = (
        f"SENTINEL-X FIELD DUTY ACCESS\n"
        f"Officer: {responder.name}\n"
        f"Log in with your duty username/password to start sharing your location:\n"
        f"{duty_url}"
    )
    result = sms_service.send_sms(responder.phone_number, message)
    # Mirrors app/api/routes/notifications.py's own test-sms audit
    # convention: records only that an attempt was made and its actual
    # outcome, never the phone number itself.
    audit_repo.log(
        "duty_link_sent" if result.success else "duty_link_send_failed",
        module="responders",
        resource_type="responder",
        resource_id=responder_id,
        outcome="success" if result.success else "failure",
        summary=f"Duty link SMS to '{responder.name}' {'sent' if result.success else 'failed'}.",
        error_category=None if result.success else "sms_gateway_error",
    )
    if not result.success:
        return SendDutyLinkResponse(success=False, message=result.message, error=result.error, duty_url=duty_url)
    return SendDutyLinkResponse(
        success=True,
        message="DUTY LINK SENT",
        recipient=responder.phone_number,
        duty_url=duty_url,
    )


def _get_share_repo() -> ShareSessionRepository:
    return get_share_session_repository()


@router.post("/login", response_model=ResponderLoginResponse)
def login_responder(
    request: ResponderLoginRequest,
    store: MongoResponderRepository = Depends(_get_store),
    share_repo: ShareSessionRepository = Depends(_get_share_repo),
    settings: Settings = Depends(get_settings),
) -> ResponderLoginResponse:
    """Username/password login for the mobile duty page. On success, starts
    (or idempotently resumes) the responder's duty session via the
    existing duty_session_service and returns its signed token -- the
    duty page uses that token for every subsequent /v1/share/{token}/*
    call, same mechanism already used by the voluntary-location-sharing
    feature.

    Both "unknown username" and "wrong password" return the exact same 401
    with the same generic message -- never distinguishing which check
    failed, so a client can't enumerate valid usernames by observing which
    error comes back (same discipline as share_tokens.verify_token)."""
    limiter = get_chat_auth_rate_limiter()
    if not limiter.allow(request.username):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts. Try again later.")

    invalid_credentials = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password.")
    try:
        responder = store.get_by_username(request.username)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if responder is None or not responder.password_hash:
        raise invalid_credentials
    if not verify_password(request.password, responder.password_hash):
        raise invalid_credentials

    join_result = start_or_resume_duty_session(responder.id, settings=settings, share_repo=share_repo)
    # resumed=True means share_url is None (the raw token for an existing
    # session was never stored -- see DutyJoinResult's own docstring), so
    # the responder would be locked out of a session they're already in.
    # Re-issue a fresh token bound to the *same* session_id in that case by
    # minting a new signed token and re-hashing it onto the existing
    # session's token_hash -- login must always hand back a usable token.
    if join_result.resumed:
        fresh_token = issue_token(join_result.session_id, responder.id, settings)
        share_repo.reissue_token(join_result.session_id, new_token=fresh_token)
        duty_token = fresh_token
    else:
        # share_url is "{base}/v1/share/{token}" -- the raw token is the
        # last path segment.
        duty_token = (join_result.share_url or "").rsplit("/", 1)[-1]

    # A share session only accepts /location updates once it's "active"
    # (see app/api/routes/share.py's update_location -> is_active() check)
    # -- a brand-new session starts "pending" and normally only becomes
    # active when the responder presses "Start Sharing" in the browser and
    # calls POST /{token}/start. A successful username/password login is a
    # *stronger* consent signal than that anonymous click, so this route
    # activates the session itself rather than requiring a second
    # round-trip from the duty page. mark_active() is a safe no-op if the
    # session is already active (the resumed-session case).
    activated = share_repo.mark_active(
        join_result.session_id,
        responder_id=responder.id,
        active_duration_seconds=settings.SHARE_SESSION_MAX_DURATION_SECONDS,
    )
    duty_status = activated["status"] if activated is not None else join_result.status

    return ResponderLoginResponse(
        responder_id=responder.id,
        name=responder.name,
        role=responder.role,
        unit=responder.unit,
        duty_token=duty_token,
        duty_status=duty_status,
    )


@router.post("/logout")
def logout_responder(
    responder_id: str,
    share_repo: ShareSessionRepository = Depends(_get_share_repo),
) -> dict:
    """Ends the responder's duty session. Does not touch any incident's
    status -- ending duty is independent of resolving an incident (see
    app/services/duty_session_service.end_duty_session's own docstring)."""
    result = end_duty_session(responder_id, share_repo=share_repo)
    return {"success": result.stopped, "responder_id": responder_id}


@router.post("/{responder_id}/reissue-pin", response_model=ResponderPinReissueResponse)
def reissue_pin(
    responder_id: str,
    store: ResponderStore = Depends(_get_store),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> ResponderPinReissueResponse:
    """Operator-triggered: generates a fresh PIN, invalidates the old one
    immediately (the old hash is overwritten, not kept). Gives a suspected
    -leaked PIN a real recovery path without deleting/recreating the
    responder (which would also lose their location/duty history)."""
    raw_pin = generate_pin()
    try:
        updated = store.reissue_pin(responder_id, pin_hash=hash_pin(raw_pin), pin_issued_at=_utcnow_iso())
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown responder_id: {responder_id}")
    audit_repo.log(
        "responder_pin_reissued",
        module="responders",
        resource_type="responder",
        resource_id=responder_id,
        summary=f"PIN reissued for responder '{updated.name}'.",
    )
    return ResponderPinReissueResponse(id=updated.id, pin=raw_pin)


@router.put("/{responder_id}", response_model=ResponderResponse)
def update_responder(
    responder_id: str,
    request: ResponderUpdateRequest,
    store: ResponderStore = Depends(_get_store),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> ResponderResponse:
    if request.status and request.status.strip().lower() not in VALID_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid status '{request.status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}.",
        )
    try:
        updated = store.update(
            responder_id,
            name=request.name,
            phone_number=request.phone_number,
            role=request.role,
            unit=request.unit,
            status=request.status,
        )
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown responder_id: {responder_id}")
    audit_repo.log(
        "responder_updated",
        module="responders",
        resource_type="responder",
        resource_id=responder_id,
        summary=f"Responder '{updated.name}' updated.",
    )
    return _to_response(updated)


@router.delete("/{responder_id}", status_code=status.HTTP_200_OK)
def delete_responder(
    responder_id: str,
    store: ResponderStore = Depends(_get_store),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> dict:
    try:
        deleted = store.delete(responder_id)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown responder_id: {responder_id}")
    audit_repo.log(
        "responder_deleted",
        module="responders",
        resource_type="responder",
        resource_id=responder_id,
        summary=f"Responder {responder_id} deleted.",
    )
    return {"success": True, "id": responder_id}


@router.post("/{responder_id}/location", response_model=ResponderLocationResponse)
def update_location(
    responder_id: str,
    request: UpdateLocationRequest,
    store: ResponderStore = Depends(_get_store),
) -> ResponderLocationResponse:
    """Records a new GPS fix. last_seen_at is always stamped by the server
    (see ResponderStore.update_location) -- never trusted from the client,
    so clock skew or a replayed payload can't fake liveness."""
    try:
        updated = store.update_location(
            responder_id,
            latitude=request.latitude,
            longitude=request.longitude,
            accuracy_meters=request.accuracy_meters,
        )
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown responder_id: {responder_id}")
    return ResponderLocationResponse(
        latitude=updated.location.latitude,
        longitude=updated.location.longitude,
        accuracy_meters=updated.location.accuracy_meters,
        last_seen_at=updated.location.last_seen_at,
        live_state=classify_location_liveness(updated.location.last_seen_at),
    )


@router.get("/{responder_id}/location", response_model=ResponderLocationResponse)
def get_location(responder_id: str, store: ResponderStore = Depends(_get_store)) -> ResponderLocationResponse:
    try:
        responder = store.get(responder_id)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if responder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown responder_id: {responder_id}")
    return ResponderLocationResponse(
        latitude=responder.location.latitude,
        longitude=responder.location.longitude,
        accuracy_meters=responder.location.accuracy_meters,
        last_seen_at=responder.location.last_seen_at,
        live_state=classify_location_liveness(responder.location.last_seen_at),
    )
