"""Duty-shift orchestration: a responder "joins" (starts their shift) by
creating/resuming a share_sessions row tagged session_kind="duty" (see
app/repositories/share_session_repository.py), tracks location through the
existing, unmodified /v1/share/{token} flow, and "ends" their shift by
stopping that same session.

This is the shared logic behind both the chat intent handlers
(app/services/chat_intent_handlers.py, Phase 4) and, for Phase 1, directly
testable on its own without any chat/Grok involvement. Kept at the
services/ layer, not inlined into a route, matching this codebase's
existing services/ vs. routes/ separation (analysis_service.py,
sms_gateway.py already live here).

A duty session is deliberately just a tagged share_sessions row, not a new
collection -- the existing pending -> active -> stopped/expired state
machine, the existing signed-token security model, and the existing
/start /location /stop endpoints are exactly what a duty shift needs. The
only new concept is `session_kind`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.share_tokens import issue_token
from app.repositories.share_session_repository import (
    SESSION_KIND_DUTY,
    STATUS_PENDING,
    ShareSessionRepository,
)


@dataclass(frozen=True)
class DutyJoinResult:
    """What JOIN_JOB actually did, used to build a truthful chat reply --
    never a success message not backed by this.

    share_url is None when `resumed=True`: the raw token is never stored
    (only its sha256 hash, see share_tokens.hash_token), so a session
    created on an earlier call genuinely cannot be turned back into a
    usable link here. Callers must say "you're already tracked" for a
    resumed session, not fabricate a link that would 404."""

    responder_id: str
    session_id: str
    share_url: str | None
    resumed: bool  # True if an existing pending/active session was reused
    status: str  # the resumed/created session's current state ("pending" | "active")


@dataclass(frozen=True)
class DutyEndResult:
    responder_id: str
    session_id: str | None  # None if there was nothing to stop
    stopped: bool


@dataclass(frozen=True)
class DutyStatus:
    responder_id: str
    has_duty_session: bool
    status: str | None  # "pending" | "active" | None (no duty session at all)
    share_url: str | None


def start_or_resume_duty_session(
    responder_id: str,
    *,
    settings: Settings,
    share_repo: ShareSessionRepository,
) -> DutyJoinResult:
    """Idempotent: a responder who sends "join" twice gets back the same
    session/link, not a second one -- checked by querying for an existing
    non-stopped/non-expired duty session first. Resuming (not duplicating)
    on repeat JOIN_JOB messages is deliberate per the approved plan."""
    existing = share_repo.get_active_duty_session_for_responder(responder_id)
    if existing is not None:
        return DutyJoinResult(
            responder_id=responder_id,
            session_id=existing["session_id"],
            share_url=None,
            resumed=True,
            status=existing["status"],
        )

    _doc, token = share_repo.create(
        responder_id=responder_id,
        dispatch_id=None,
        invite_ttl_seconds=settings.SHARE_INVITE_TTL_SECONDS,
        token_factory=lambda session_id, rid: issue_token(session_id, rid, settings),
        session_kind=SESSION_KIND_DUTY,
    )
    return DutyJoinResult(
        responder_id=responder_id,
        session_id=_doc["session_id"],
        share_url=_build_share_url_from_token(settings, token),
        resumed=False,
        status=STATUS_PENDING,
    )


def end_duty_session(
    responder_id: str,
    *,
    share_repo: ShareSessionRepository,
) -> DutyEndResult:
    """Stops the responder's current duty session via the existing,
    unmodified mark_stopped() -- which already leaves last_lat/last_lng/
    last_update_at untouched (only `status` changes), so the last known
    position and the session's own record remain inspectable afterward.
    Does NOT touch any incident's status -- ending duty is independent of
    resolving an incident (see the approved plan's "duty-end reassignment
    flag" section, wired in once incident_repository.py gains the needed
    methods in a later phase)."""
    existing = share_repo.get_active_duty_session_for_responder(responder_id)
    if existing is None:
        return DutyEndResult(responder_id=responder_id, session_id=None, stopped=False)
    stopped = share_repo.mark_stopped(existing["session_id"])
    return DutyEndResult(responder_id=responder_id, session_id=existing["session_id"], stopped=stopped)


def get_duty_status(
    responder_id: str,
    *,
    settings: Settings,
    share_repo: ShareSessionRepository,
) -> DutyStatus:
    existing = share_repo.get_active_duty_session_for_responder(responder_id)
    if existing is None:
        return DutyStatus(responder_id=responder_id, has_duty_session=False, status=None, share_url=None)
    # share_url is always None for an *existing* session: the raw token is
    # never stored (only its sha256 hash -- see share_tokens.hash_token),
    # so there is no real link to reconstruct here. A status reply must
    # describe the session's actual state truthfully, never fabricate a
    # link that would 404. The link is only ever available once, at the
    # moment start_or_resume_duty_session() first creates the session.
    return DutyStatus(
        responder_id=responder_id,
        has_duty_session=True,
        status=existing["status"],
        share_url=None,
    )


def _build_share_url_from_token(settings: Settings, token: str) -> str:
    # Must match the real mounted path -- app/main.py registers
    # share.router under prefix "/api" on top of the router's own
    # "/v1/share" prefix (app/api/routes/share.py), giving
    # "/api/v1/share/{token}". app/api/routes/dispatch.py's own share-link
    # construction already uses this exact path; this helper previously
    # omitted "/api" and would have produced a 404 link.
    base = settings.PUBLIC_BASE_URL or ""
    return f"{base}/api/v1/share/{token}" if base else ""
