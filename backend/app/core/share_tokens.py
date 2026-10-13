"""Signed, revocable tokens for the voluntary live-location-sharing feature.

Deliberately stdlib-only (hmac + secrets), not itsdangerous/pyjwt -- this
project has no signing dependency installed today, and the token shape
needed here is small enough that hand-rolling it keeps the dependency list
unchanged. hmac.compare_digest is used for constant-time signature
comparison, same mitigation a signing library would apply internally.

A token proves two things, nothing more: "this session_id/responder_id pair
was really issued by this server" and "it was issued recently enough to
still be a valid *invitation*". It is NOT, by itself, proof that sharing
should currently be accepted -- that also requires checking the session's
live status/active_until in share_sessions (see
app/repositories/share_session_repository.py). A verified-but-expired or
verified-but-stopped token must still be rejected by the caller.

The raw token is never persisted anywhere (only its sha256 hash is stored,
in share_session_repository.py) and never logged.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets as _secrets
import time
from dataclasses import dataclass

from app.core.config import Settings

# Per-process fallback signing key, used only when SHARE_SECRET_KEY is unset.
# Generated once at import time -- see _resolve_secret_key's docstring for
# why a random fallback is dev-only, never production-safe.
_RANDOM_FALLBACK_KEY = _secrets.token_bytes(32)


@dataclass(frozen=True)
class TokenPayload:
    session_id: str
    responder_id: str
    exp: int  # unix timestamp -- invitation expiry, NOT active-session expiry


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _resolve_secret_key(settings: Settings) -> bytes:
    """Returns the signing key as bytes. Falls back to a per-process random
    key (logged once as a warning by the caller's startup path, not here --
    this module stays side-effect-free/pure) if SHARE_SECRET_KEY is unset,
    so dev still works without a .env entry. A random fallback means tokens
    issued before a restart stop verifying after one -- acceptable for a
    dev-mode fallback, never acceptable as the production default, which is
    why .env.example documents setting this explicitly.
    """
    if settings.SHARE_SECRET_KEY:
        return settings.SHARE_SECRET_KEY.encode("utf-8")
    return _RANDOM_FALLBACK_KEY


def issue_token(session_id: str, responder_id: str, settings: Settings, *, ttl_seconds: int | None = None) -> str:
    """Builds a signed token for a newly-created share session.

    ttl_seconds overrides settings.SHARE_INVITE_TTL_SECONDS -- used by tests
    to construct deliberately-already-expired tokens without sleeping.
    """
    ttl = ttl_seconds if ttl_seconds is not None else settings.SHARE_INVITE_TTL_SECONDS
    payload = {
        "sid": session_id,
        "rid": responder_id,
        "exp": int(time.time()) + int(ttl),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(_resolve_secret_key(settings), payload_bytes, hashlib.sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


def verify_token(token: str, settings: Settings) -> TokenPayload | None:
    """Verifies signature and invitation expiry only. Returns None on ANY
    failure (malformed, bad signature, expired) -- callers must map every
    failure to the same generic 403 response, never distinguishing which
    check failed, to avoid giving an attacker an oracle.

    Does NOT check share_sessions state (stopped/already-active/etc) --
    that is the repository's job, checked separately by the route.
    """
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload_bytes = _b64url_decode(encoded_payload)
        signature = _b64url_decode(encoded_signature)
    except (ValueError, binascii.Error):  # malformed token -> reject
        return None

    expected_signature = hmac.new(_resolve_secret_key(settings), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(payload_bytes)
        session_id = str(payload["sid"])
        responder_id = str(payload["rid"])
        exp = int(payload["exp"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None

    if time.time() >= exp:
        return None

    return TokenPayload(session_id=session_id, responder_id=responder_id, exp=exp)


def hash_token(token: str) -> str:
    """sha256 hex digest -- what gets stored in Mongo. The raw token itself
    is never persisted, matching this project's existing "never store the
    password field" convention (see app/repositories/dispatch_repository.py).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
