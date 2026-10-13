"""Voluntary live-location-sharing API: a responder opens a signed, one-time
invitation link (sent via the existing SMS dispatch flow) and explicitly
opts in to sharing live GPS for a limited window.

Served entirely by this one router -- including the share page itself as
plain HTML/JS (GET /v1/share/{token}) -- so that tunneling only this
backend's port (not the separate React/Vite frontend) is enough to let a
responder's phone reach the whole flow over a single HTTPS origin. See the
share-link plan for why: free ngrok allows exactly one tunnel at a time.

Auth model (two independent clocks -- see share_tokens.py /
share_session_repository.py module docstrings for the full rationale):
- The signed token proves possession of a specific, server-issued invitation
  and is only checked for its own expiry at /start.
- Once /start succeeds, the SESSION (not the token) owns its own
  active_until clock, checked by /location and /status instead.
- /stop is always safe to call and is the one place a token's underlying
  session can be a terminal, non-reactivatable 'stopped' state.
Every failure path returns the same generic 403 message, deliberately not
distinguishing "token invalid" from "expired" from "wrong responder" from
"already stopped" -- avoiding an oracle that would help someone probe a
guessed/leaked token.

Rate limited (see app/core/rate_limit.py) keyed on token -- new attack
surface introduced specifically by this feature, not applied to any
pre-existing route.
"""

from __future__ import annotations

import html as html_module

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.core.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowRateLimiter, get_share_rate_limiter
from app.core.share_tokens import TokenPayload, verify_token
from app.repositories.mongo_job_repository import MongoDBUnavailableError
from app.repositories.responder_repository import MongoResponderRepository, get_mongo_responder_repository
from app.repositories.share_session_repository import (
    STATUS_ACTIVE,
    ShareSessionRepository,
    get_share_session_repository,
)
from app.schemas.share import (
    ShareLocationUpdateRequest,
    ShareLocationUpdateResponse,
    ShareSessionStatusResponse,
    ShareStartResponse,
    ShareStopResponse,
)

router = APIRouter(prefix="/v1/share", tags=["Share"])

_GENERIC_403 = "This sharing link is invalid, expired, or no longer active."


def _get_share_repo() -> ShareSessionRepository:
    return get_share_session_repository()


def _get_responder_repo() -> MongoResponderRepository:
    return get_mongo_responder_repository()


def _get_limiter() -> SlidingWindowRateLimiter:
    return get_share_rate_limiter()


def _enforce_rate_limit(limiter: SlidingWindowRateLimiter, token: str) -> None:
    if not limiter.allow(token):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please slow down.")


def _verify_or_403(token: str, settings: Settings) -> TokenPayload:
    payload = verify_token(token, settings)
    if payload is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _GENERIC_403)
    return payload


@router.get("/{token}", response_class=HTMLResponse)
def share_page(token: str) -> HTMLResponse:
    """The consent/status page itself, served as a small, self-contained
    HTML document with embedded JS -- no React/Vite build involved. The
    token is not validated here (that happens on every subsequent API
    call the page itself makes); this route only ever returns the same
    static shell regardless of token validity, so the page's own JS is
    responsible for showing "invalid/expired" state after calling
    /status. This keeps the one GET route trivially cacheable/stable and
    avoids leaking any validity signal via response-shape differences.
    """
    # html.escape as defense-in-depth even though `token` only ever reaches
    # the browser inside a JS string literal built via JSON, never raw HTML.
    safe_token = html_module.escape(token, quote=True)
    page = _SHARE_PAGE_TEMPLATE.replace("__TOKEN__", safe_token)
    return HTMLResponse(content=page)


@router.get("/{token}/status", response_model=ShareSessionStatusResponse)
def get_status(
    token: str,
    settings: Settings = Depends(get_settings),
    share_repo: ShareSessionRepository = Depends(_get_share_repo),
    responder_repo: MongoResponderRepository = Depends(_get_responder_repo),
    limiter: SlidingWindowRateLimiter = Depends(_get_limiter),
) -> ShareSessionStatusResponse:
    _enforce_rate_limit(limiter, token)
    payload = _verify_or_403(token, settings)
    try:
        session = share_repo.get(payload.session_id)
        responder = responder_repo.get(payload.responder_id)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sharing service is temporarily unavailable. Please try again shortly.",
        )
    if session is None or session.get("responder_id") != payload.responder_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _GENERIC_403)

    # A session can time out passively (no one calls /location for a
    # while) -- is_active() lazily flips a timed-out ACTIVE session to
    # EXPIRED so status always reflects truth rather than a stale "active".
    if session.get("status") == STATUS_ACTIVE:
        share_repo.is_active(payload.session_id)
        session = share_repo.get(payload.session_id)

    return ShareSessionStatusResponse(
        status=session["status"],
        responder_name=responder.name if responder else "Responder",
        last_update_at=session.get("last_update_at"),
        last_lat=session.get("last_lat"),
        last_lng=session.get("last_lng"),
    )


@router.post("/{token}/start", response_model=ShareStartResponse)
def start_sharing(
    token: str,
    settings: Settings = Depends(get_settings),
    share_repo: ShareSessionRepository = Depends(_get_share_repo),
    limiter: SlidingWindowRateLimiter = Depends(_get_limiter),
) -> ShareStartResponse:
    """Called only after the responder has explicitly pressed "Start
    Sharing" in the browser AND granted the geolocation permission prompt
    (enforced client-side in the page's own JS -- this endpoint has no way
    to verify browser permission state itself, so the page is the one place
    consent is actually gated; this endpoint's job is purely server-side
    token/session validation)."""
    _enforce_rate_limit(limiter, token)
    payload = _verify_or_403(token, settings)  # checks the INVITE clock only
    try:
        session = share_repo.mark_active(
            payload.session_id,
            responder_id=payload.responder_id,
            active_duration_seconds=settings.SHARE_SESSION_MAX_DURATION_SECONDS,
        )
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sharing service is temporarily unavailable. Please try again shortly.",
        )
    if session is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _GENERIC_403)
    return ShareStartResponse(success=True, status=session["status"])


@router.post("/{token}/location", response_model=ShareLocationUpdateResponse)
def update_location(
    token: str,
    request: ShareLocationUpdateRequest,
    settings: Settings = Depends(get_settings),
    share_repo: ShareSessionRepository = Depends(_get_share_repo),
    responder_repo: MongoResponderRepository = Depends(_get_responder_repo),
    limiter: SlidingWindowRateLimiter = Depends(_get_limiter),
) -> ShareLocationUpdateResponse:
    """Checks the ACTIVE-SESSION clock only (not the invite's own expiry --
    see module docstring). Writes through to the existing
    MongoResponderRepository.update_location() so the operator's already-
    existing map/polling picks this up with zero new frontend code, exactly
    as the share-link plan specifies."""
    _enforce_rate_limit(limiter, token)
    payload = _verify_or_403(token, settings)
    try:
        active_session = share_repo.is_active(payload.session_id)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sharing service is temporarily unavailable. Location was not recorded.",
        )
    if active_session is None or active_session.get("responder_id") != payload.responder_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _GENERIC_403)

    try:
        share_repo.record_update(
            payload.session_id,
            latitude=request.latitude,
            longitude=request.longitude,
            accuracy_meters=request.accuracy_meters,
        )
        responder_repo.update_location(
            payload.responder_id,
            latitude=request.latitude,
            longitude=request.longitude,
            accuracy_meters=request.accuracy_meters,
        )
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sharing service is temporarily unavailable. Location was not recorded.",
        )
    return ShareLocationUpdateResponse(success=True)


@router.post("/{token}/stop", response_model=ShareStopResponse)
def stop_sharing(
    token: str,
    settings: Settings = Depends(get_settings),
    share_repo: ShareSessionRepository = Depends(_get_share_repo),
    limiter: SlidingWindowRateLimiter = Depends(_get_limiter),
) -> ShareStopResponse:
    """Always safe to call on a validly-signed token regardless of the
    session's current status (pending/active/already-stopped/expired) --
    stopping is a terminal, idempotent transition. This is deliberately
    MORE permissive than /start: a responder must always be able to shut
    off sharing, even if the session already expired on its own."""
    _enforce_rate_limit(limiter, token)
    payload = _verify_or_403(token, settings)
    try:
        share_repo.mark_stopped(payload.session_id)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The sharing service is temporarily unavailable. Please try again shortly.",
        )
    return ShareStopResponse(success=True)


_SHARE_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SENTINEL-X -- Share your location</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px 16px; background: #0b1220; color: #e6ebf2; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  p { line-height: 1.5; color: #aab4c4; }
  button { width: 100%; padding: 14px; font-size: 16px; border-radius: 10px; border: none; margin-top: 16px; cursor: pointer; }
  #startBtn { background: #2563eb; color: white; }
  #stopBtn { background: #dc2626; color: white; display: none; }
  #status { margin-top: 20px; padding: 14px; border-radius: 10px; background: #141c2e; font-size: 14px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .badge-pending { background: #3f3313; color: #f5c84c; }
  .badge-active { background: #10381f; color: #4ade80; }
  .badge-stopped, .badge-expired { background: #3a1414; color: #f87171; }
  #error { color: #f87171; margin-top: 12px; display: none; }
</style>
</head>
<body>
  <h1>SENTINEL-X</h1>
  <p>An operator has requested your live location to coordinate a response. Sharing is <strong>completely voluntary</strong>: your location is only sent while this page is open and you have pressed Start Sharing, and you can stop at any time.</p>

  <div id="status">Checking invitation&hellip;</div>
  <div id="error"></div>

  <button id="startBtn">Start Sharing</button>
  <button id="stopBtn">Stop Sharing</button>

<script>
const TOKEN = "__TOKEN__";
const base = "/api/v1/share/" + TOKEN;
let watchId = null;

function badge(status) {
  return '<span class="badge badge-' + status + '">' + status + '</span>';
}

function showError(msg) {
  const el = document.getElementById("error");
  el.textContent = msg;
  el.style.display = "block";
}

async function refreshStatus() {
  try {
    const resp = await fetch(base + "/status");
    if (!resp.ok) {
      document.getElementById("status").innerHTML = "This invitation link is invalid, expired, or no longer active.";
      document.getElementById("startBtn").style.display = "none";
      document.getElementById("stopBtn").style.display = "none";
      return;
    }
    const data = await resp.json();
    let html = badge(data.status) + " &middot; " + data.responder_name;
    if (data.last_update_at) {
      html += "<br>Last update: " + new Date(data.last_update_at).toLocaleTimeString();
    }
    document.getElementById("status").innerHTML = html;
    if (data.status === "active") {
      document.getElementById("startBtn").style.display = "none";
      document.getElementById("stopBtn").style.display = "block";
    } else if (data.status === "stopped" || data.status === "expired") {
      document.getElementById("startBtn").style.display = "none";
      document.getElementById("stopBtn").style.display = "none";
      stopWatching();
    }
  } catch (e) {
    showError("Could not reach the server. Check your connection.");
  }
}

function stopWatching() {
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
}

async function sendLocation(coords) {
  try {
    await fetch(base + "/location", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy_meters: coords.accuracy || null,
      }),
    });
  } catch (e) {
    // A transient network hiccup posting one fix is not fatal -- the next
    // watchPosition callback will simply try again.
  }
}

document.getElementById("startBtn").addEventListener("click", async () => {
  if (!navigator.geolocation) {
    showError("This browser does not support location sharing.");
    return;
  }
  try {
    const resp = await fetch(base + "/start", { method: "POST" });
    if (!resp.ok) {
      showError("This invitation link is invalid or has expired. Please ask the operator to resend it.");
      return;
    }
  } catch (e) {
    showError("Could not reach the server. Check your connection.");
    return;
  }
  watchId = navigator.geolocation.watchPosition(
    (pos) => { sendLocation(pos.coords); refreshStatus(); },
    (err) => { showError("Location permission was denied or is unavailable."); },
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
  );
  refreshStatus();
});

document.getElementById("stopBtn").addEventListener("click", async () => {
  const stopBtn = document.getElementById("stopBtn");
  if (stopBtn.disabled) return; // guards against duplicate taps while a stop request is already in flight
  stopBtn.disabled = true;
  const originalLabel = stopBtn.textContent;
  stopBtn.textContent = "Stopping sharing…";
  document.getElementById("error").style.display = "none";

  // The watch is only cleared once the backend has actually confirmed the
  // stop below -- clearing it here first (as the previous version did)
  // would silently end tracking even if the /stop request then failed,
  // leaving the responder's phone no longer reporting while the backend
  // (and the operator's map) still showed the session as active.
  try {
    const resp = await fetch(base + "/stop", { method: "POST" });
    if (!resp.ok) {
      throw new Error("stop request rejected");
    }
    stopWatching();
    stopBtn.textContent = "Sharing stopped";
  } catch (e) {
    showError("Could not stop sharing -- check your connection and try again.");
    stopBtn.textContent = originalLabel;
    stopBtn.disabled = false;
    return;
  }
  await refreshStatus();
});

refreshStatus();
setInterval(refreshStatus, 6000);
</script>
</body>
</html>
"""
