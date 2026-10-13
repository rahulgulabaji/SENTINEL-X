"""Pydantic schemas for the isolated SMS notification API.

Mirrors the shape/conventions of app/schemas/yolo.py and analysis.py. Kept
separate from those modules since this feature is intentionally isolated
from the inference pipeline (see app/services/sms_gateway.py).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TestSmsRequest(BaseModel):
    recipient: str = Field(..., description="Destination phone number, e.g. '+15551234567'.")


class SmsResponse(BaseModel):
    success: bool
    message: str
    error: str | None = None


class SendDutyLinkResponse(BaseModel):
    success: bool
    message: str
    recipient: str | None = Field(default=None, description="Masked/raw phone the link was sent to -- None if sending failed before a number was resolved.")
    duty_url: str | None = Field(default=None, description="The actual duty-page URL that was sent, built from PUBLIC_BASE_URL. None if PUBLIC_BASE_URL is not configured.")
    error: str | None = None


SmsConnectionState = Literal["disabled", "not_configured", "connection_failed", "authentication_failed", "connected"]
"""Structured connection state for the Settings UI -- lets the frontend
switch on a fixed enum instead of parsing free-text `error` strings.

- "disabled": SMS_GATEWAY_ENABLED is false.
- "not_configured": enabled, but the gateway URL is not set.
- "connection_failed": enabled + configured, but the gateway could not be
  reached (timeout, connection refused, DNS failure, etc).
- "authentication_failed": the gateway was reached but rejected the
  request's credentials (HTTP 401/403).
- "connected": the gateway was reached and did not reject credentials.
"""


class SmsGatewayStatus(BaseModel):
    enabled: bool
    configured: bool
    connectivity_checked: bool = Field(
        description="True iff an actual network reachability check was performed for this response."
    )
    connected: bool | None = Field(
        default=None,
        description="Result of the reachability check. null when not checked (disabled/not configured).",
    )
    connection_state: SmsConnectionState = Field(
        description="Structured state for UI branching -- see SmsConnectionState."
    )


class SmsConfigGetResponse(BaseModel):
    """Current SMS gateway configuration. The password itself is never
    included -- only whether one is currently stored."""

    enabled: bool
    url: str
    username: str
    password_configured: bool = Field(
        description="True iff a non-empty password is currently stored. The password value itself is never returned."
    )


class SmsConfigUpdateRequest(BaseModel):
    enabled: bool
    url: str = Field(default="", description="Base URL of the Android SMS gateway, e.g. 'http://192.168.1.50:8080'.")
    username: str = Field(default="")
    password: str | None = Field(
        default=None,
        description="New password. Omit or send an empty string to leave the previously saved password unchanged.",
    )


class SmsConfigUpdateResponse(BaseModel):
    enabled: bool
    url: str
    username: str
    password_configured: bool


class SmsTestConnectionResponse(BaseModel):
    success: bool
    message: str
    error: str | None = None
    connection_state: SmsConnectionState = Field(
        description="Structured state for UI branching -- see SmsConnectionState."
    )
