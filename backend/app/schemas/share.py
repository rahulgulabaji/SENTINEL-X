"""Pydantic schemas for the voluntary live-location-sharing (share-link) API.

Mirrors the alias/validation conventions of app/schemas/responders.py's
UpdateLocationRequest exactly, since this is the same physical data (a
browser geolocation fix) arriving through a different, token-authenticated
route rather than the authenticated-operator-app route.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field


class ShareLocationUpdateRequest(BaseModel):
    latitude: float = Field(..., validation_alias=AliasChoices("latitude", "lat"), ge=-90, le=90)
    longitude: float = Field(..., validation_alias=AliasChoices("longitude", "lng", "lon"), ge=-180, le=180)
    accuracy_meters: float | None = Field(
        default=None, validation_alias=AliasChoices("accuracy_meters", "accuracy"), gt=0
    )

    model_config = {"populate_by_name": True}


class ShareLocationUpdateResponse(BaseModel):
    success: bool
    error: str | None = None


class ShareSessionStatusResponse(BaseModel):
    """Deliberately excludes the responder's phone number -- the share page
    is reached by the responder's own phone, so there's no reason to echo
    it back, and doing so would be an unnecessary exposure if the link were
    ever opened by someone other than the intended responder."""

    status: str = Field(description="One of 'pending', 'active', 'stopped', 'expired'.")
    responder_name: str
    last_update_at: str | None = None
    last_lat: float | None = None
    last_lng: float | None = None


class ShareStartResponse(BaseModel):
    success: bool
    status: str | None = None
    error: str | None = None


class ShareStopResponse(BaseModel):
    success: bool
