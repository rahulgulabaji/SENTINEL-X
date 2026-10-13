"""Pydantic schemas for the responder registry + live location API.

Mirrors the shape/conventions of app/schemas/notifications.py and yolo.py.
Field aliases exist specifically because the real, already-written frontend
(frontend/src/App.jsx + services/api.js) sends/expects certain alternate
names -- confirmed by reading that code, not assumed:

- Registration (handleRegisterResponder) sends `phone` (not `phone_number`)
  and an extra `unit` field, plus a client-generated `id` and `status`
  sent as the literal string "AVAILABLE".
- Location updates (updateResponderLocation) send BOTH `latitude`/
  `longitude` and `lat`/`lng` in the same payload, plus `accuracy` (not
  `accuracy_meters`).
- getNearbyResponders() queries with `lat`/`lng` query params, not
  `latitude`/`longitude`.

Response field names stay canonical (phone_number, accuracy_meters,
latitude, longitude) -- the frontend's own display code already falls back
across both naming styles (e.g. `resp.phone || resp.phone_number`), so
canonical names are a safe response contract that doesn't need aliasing.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class ResponderCreateRequest(BaseModel):
    id: str | None = Field(default=None, description="Optional client-supplied id; a uuid4 is generated if omitted.")
    name: str = Field(..., min_length=1)
    phone_number: str = Field(default="", validation_alias=AliasChoices("phone_number", "phone"))
    role: str = Field(default="")
    unit: str = Field(default="")
    status: str = Field(default="available")
    # Optional, not required: a responder can still be registered without
    # duty-page login (e.g. PIN-only, or an older/scripted caller that
    # predates this field) -- matches this schema's own existing
    # backward-compatibility convention for every other field added after
    # the original registration flow. When both are omitted, no username/
    # password_hash is stored and that responder simply can't use
    # POST /v1/responders/login (PIN auth, if ever wired up, is unaffected).
    username: str | None = Field(default=None, min_length=3, description="Login username for the mobile duty page. Must be unique. Omit to register a PIN-only responder.")
    password: str | None = Field(default=None, min_length=8, description="Login password for the mobile duty page. Hashed immediately, never persisted raw. Required if username is given.")

    model_config = {"populate_by_name": True}


class ResponderUpdateRequest(BaseModel):
    """All fields optional -- a partial update. None/omitted means
    "leave unchanged", matching ResponderStore.update()'s semantics."""

    name: str | None = None
    phone_number: str | None = Field(default=None, validation_alias=AliasChoices("phone_number", "phone"))
    role: str | None = None
    unit: str | None = None
    status: str | None = None

    model_config = {"populate_by_name": True}


class ResponderLocationResponse(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    accuracy_meters: float | None = None
    last_seen_at: str | None = None
    live_state: str = Field(description="One of 'live', 'stale', 'offline' -- see app/core/dispatch_config.py.")


class ResponderResponse(BaseModel):
    id: str
    name: str
    phone_number: str
    role: str
    unit: str
    status: str
    latitude: float | None = None
    longitude: float | None = None
    accuracy_meters: float | None = None
    last_seen_at: str | None = None
    live_state: str = Field(description="One of 'live', 'stale', 'offline'.")
    created_at: str = Field(default="", description="ISO 8601 UTC, server-stamped at registration.")
    updated_at: str = Field(default="", description="ISO 8601 UTC, server-stamped on every metadata/location change.")
    username: str | None = Field(default=None, description="Login username. None for a legacy PIN-only responder.")


class ResponderCreateResponse(ResponderResponse):
    """Identical to ResponderResponse, plus the raw PIN and raw password --
    both returned ONLY here, exactly once, at creation time (see
    app/core/responder_auth.py). Never included in ResponderResponse
    (GET/PUT/list), so neither credential is ever re-exposed after this one
    response."""

    pin: str = Field(description="Raw 6-digit PIN for chat/duty-session auth. Shown once -- not recoverable later, only reissuable.")
    password: str | None = Field(default=None, description="Raw login password, echoed back once so the operator can hand it to the officer. None if no username/password was given at creation (PIN-only responder). Not recoverable later.")


class ResponderPinReissueResponse(BaseModel):
    id: str
    pin: str = Field(description="New raw 6-digit PIN. The previous PIN stops working immediately.")


class ResponderLoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ResponderLoginResponse(BaseModel):
    responder_id: str
    name: str
    role: str
    unit: str
    duty_token: str = Field(description="Signed share-session token. Used for /v1/share/{token}/location and /stop. Not persisted server-side -- only its hash is stored.")
    duty_status: str = Field(description="'pending' or 'active' -- the duty session's current state after this login.")


class UpdateLocationRequest(BaseModel):
    latitude: float = Field(..., validation_alias=AliasChoices("latitude", "lat"), ge=-90, le=90)
    longitude: float = Field(..., validation_alias=AliasChoices("longitude", "lng", "lon"), ge=-180, le=180)
    # gt=0 (not ge=0): accuracy is a radius in meters -- 0 or negative is not
    # a physically meaningful GPS accuracy value. None (omitted) is still
    # allowed -- "accuracy not reported" is different from "zero accuracy".
    accuracy_meters: float | None = Field(
        default=None, validation_alias=AliasChoices("accuracy_meters", "accuracy"), gt=0
    )

    model_config = {"populate_by_name": True}
