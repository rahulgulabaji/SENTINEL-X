"""SMS notification API routes -- isolated gateway test/status endpoints.

Mirrors app/api/routes/yolo.py's structure (Depends()-based service wiring,
same router-registration convention in main.py). Deliberately knows nothing
about analysis jobs or inference: this is Step 1 of the notification system
(see app/services/sms_gateway.py docstring) -- a standalone way to validate
the Android SMS gateway is reachable and correctly configured. It is NOT
triggered by analysis results.
"""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.sms_config_store import SmsConfigStore, get_sms_config_store
from app.repositories.audit_repository import AuditRepository, get_audit_repository
from app.schemas.notifications import (
    SmsConfigGetResponse,
    SmsConfigUpdateRequest,
    SmsConfigUpdateResponse,
    SmsConnectionState,
    SmsGatewayStatus,
    SmsResponse,
    SmsTestConnectionResponse,
    TestSmsRequest,
)
from app.services.sms_gateway import SmsGatewayService, SmsResult, get_sms_gateway_service

router = APIRouter(prefix="/v1/notifications", tags=["Notifications"])


def _connection_state(enabled: bool, configured: bool, result: SmsResult | None) -> SmsConnectionState:
    """Maps the service's existing (enabled, configured, SmsResult) outputs
    onto the structured SmsConnectionState enum -- computed here, not inside
    sms_gateway.py, so SmsResult/SmsGatewayService stay untouched and this
    stays presentation-layer logic for the API contract.

    `result` is None when no connectivity check was performed at all
    (disabled/not configured) -- mirrors the existing
    `connectivity_checked`/`connected=None` convention.
    """
    if not enabled:
        return "disabled"
    if not configured:
        return "not_configured"
    assert result is not None  # enabled+configured always triggers a real check
    # Checked before `result.success`: SmsGatewayService.check_connectivity()
    # deliberately reports success=True for a reachable-but-auth-rejected
    # gateway (HTTPError caught before URLError -- see sms_gateway.py), with
    # "HTTP 401"/"HTTP 403" only appearing in `error` for that specific case.
    # So this marker must be checked first, or a 401/403 would incorrectly
    # fall into the "connected" branch below instead of "authentication_failed".
    error_text = (result.error or "").upper()
    if "HTTP 401" in error_text or "HTTP 403" in error_text:
        return "authentication_failed"
    if result.success:
        return "connected"
    return "connection_failed"


def _get_audit_repository() -> AuditRepository:
    return get_audit_repository()


def _get_config_store() -> SmsConfigStore:
    # No settings arg here: that would rebuild (and re-seed/reload) a brand
    # new SmsConfigStore on every single request, which is both wasteful and
    # unsafe (each instance would have its own separate lock). Settings are
    # only consulted *inside* get_sms_config_store() the one time it lazily
    # builds the real singleton, mirroring get_sms_gateway_service() exactly.
    return get_sms_config_store()


def _get_service(
    settings: Settings = Depends(get_settings),
    store: SmsConfigStore = Depends(_get_config_store),
) -> SmsGatewayService:
    """Builds a SmsGatewayService reflecting whatever SMS config is
    currently stored (UI-edited values if any exist, otherwise whatever
    .env seeded on first run) -- read fresh on every request, so a PUT to
    /sms/config takes effect immediately with no restart needed.

    sms_gateway.py itself is not modified: dataclasses.replace() builds a
    Settings-shaped object with only the four SMS_GATEWAY_* fields
    overridden, then the existing explicit-settings branch of
    get_sms_gateway_service() (unchanged) builds a fresh service from it.
    """
    values = store.get()
    effective_settings = dataclasses.replace(
        settings,
        SMS_GATEWAY_ENABLED=values.enabled,
        SMS_GATEWAY_URL=values.url,
        SMS_GATEWAY_USERNAME=values.username,
        SMS_GATEWAY_PASSWORD=values.password,
    )
    return get_sms_gateway_service(effective_settings)


@router.post("/test-sms", response_model=SmsResponse)
def send_test_sms(
    request: TestSmsRequest,
    service: SmsGatewayService = Depends(_get_service),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> SmsResponse:
    """Sends exactly one SMS to `request.recipient` via the Android gateway.

    Exists only to validate the gateway end-to-end. Never raises -- a
    disabled/misconfigured gateway or an unreachable phone comes back as
    {"success": false, "error": "..."} with HTTP 200, not a 5xx, since this
    is an expected/normal outcome for this endpoint, not a server error.
    """
    result = service.send_sms(request.recipient, "SENTINEL-X test notification.")
    # Records only that a test-SMS ATTEMPT was made and its actual outcome --
    # never claims delivery, and the recipient number itself is not logged
    # (not a secret, but unnecessary PII for an audit trail entry whose
    # purpose is "was the gateway reachable", not "who was contacted").
    audit_repo.log(
        "sms_test_sent" if result.success else "sms_test_failed",
        module="notifications",
        resource_type="sms_test",
        outcome="success" if result.success else "failure",
        summary="Test SMS attempt via SMS gateway." if result.success else "Test SMS attempt failed.",
        error_category=None if result.success else "sms_gateway_error",
    )
    return SmsResponse(**result.to_dict())


@router.get("/sms/status", response_model=SmsGatewayStatus)
def sms_gateway_status(
    service: SmsGatewayService = Depends(_get_service),
) -> SmsGatewayStatus:
    """Read-only configuration/connectivity report. Never includes
    credentials, phone numbers, or the gateway URL. Only performs an actual
    connectivity check (and reports `connected`) when the gateway is enabled
    and minimally configured -- otherwise `connected` stays null rather than
    claiming a state that was never verified.
    """
    enabled = service.is_enabled()
    configured = service.is_configured()

    if not configured:
        return SmsGatewayStatus(
            enabled=enabled,
            configured=configured,
            connectivity_checked=False,
            connected=None,
            connection_state=_connection_state(enabled, configured, None),
        )

    result = service.check_connectivity()
    return SmsGatewayStatus(
        enabled=enabled,
        configured=configured,
        connectivity_checked=True,
        connected=result.success,
        connection_state=_connection_state(enabled, configured, result),
    )


@router.get("/sms/config", response_model=SmsConfigGetResponse)
def get_sms_config(store: SmsConfigStore = Depends(_get_config_store)) -> SmsConfigGetResponse:
    """Current SMS gateway configuration, for the management dashboard.
    Never returns the password itself -- only whether one is set."""
    values = store.get()
    return SmsConfigGetResponse(
        enabled=values.enabled,
        url=values.url,
        username=values.username,
        password_configured=bool(values.password),
    )


@router.put("/sms/config", response_model=SmsConfigUpdateResponse)
def update_sms_config(
    request: SmsConfigUpdateRequest,
    store: SmsConfigStore = Depends(_get_config_store),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> SmsConfigUpdateResponse:
    """Updates SMS gateway configuration. Takes effect immediately for all
    subsequent requests (no restart needed) -- see _get_service() above.

    `password` is optional: omitting it (or sending an empty string) leaves
    the previously saved password unchanged, so the UI never has to display
    or resubmit the real password just to edit the URL/username/enabled
    flag.
    """
    values = store.update(
        enabled=request.enabled,
        url=request.url,
        username=request.username,
        password=request.password or None,
    )
    # "configuration_changed" matches the event_type test_mongodb.py already
    # asserts the repository layer supports -- this is the first real caller
    # of it. Never logs the password itself or whether one was supplied;
    # only the non-secret fields and whether a password is now configured.
    audit_repo.log(
        "configuration_changed",
        module="notifications",
        resource_type="sms_config",
        summary="SMS gateway configuration updated.",
        details={
            "enabled": values.enabled,
            "url": values.url,
            "username": values.username,
            "password_configured": bool(values.password),
        },
    )
    return SmsConfigUpdateResponse(
        enabled=values.enabled,
        url=values.url,
        username=values.username,
        password_configured=bool(values.password),
    )


@router.post("/sms/test-connection", response_model=SmsTestConnectionResponse)
def test_sms_connection(service: SmsGatewayService = Depends(_get_service)) -> SmsTestConnectionResponse:
    """Reachability probe only -- never sends an SMS. Lets the dashboard
    validate a saved configuration immediately. Delegates entirely to
    SmsGatewayService.check_connectivity(); duplicates no gateway logic.
    """
    enabled = service.is_enabled()
    configured = service.is_configured()
    result = service.check_connectivity()
    return SmsTestConnectionResponse(
        **result.to_dict(),
        connection_state=_connection_state(enabled, configured, result),
    )
