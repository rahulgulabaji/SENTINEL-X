"""Minimal in-memory sliding-window rate limiter.

Same spirit and simplicity as DispatchIdempotencyGuard in
app/core/dispatch_config.py -- no new pip dependency (e.g. slowapi) for what
is a small, specific need: blunting brute-force token guessing and update
flooding against the new /v1/share/* surface introduced by the
voluntary-location-sharing feature. Not applied to any pre-existing route;
existing endpoints' rate behavior is unchanged.

Deliberately not persisted -- a backend restart clearing accumulated counts
is acceptable, matching DispatchIdempotencyGuard's own in-memory-only design.
"""

from __future__ import annotations

import threading
import time


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        """Returns True if `key` is still under its limit (and records this
        call as a hit), False if the limit is already exceeded (no hit is
        recorded for a rejected call -- a sustained flood doesn't just keep
        resetting its own window)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, [])
            cutoff = now - self._window_seconds
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if len(hits) >= self._max_requests:
                return False
            hits.append(now)
            return True


_share_limiter: SlidingWindowRateLimiter | None = None


def get_share_rate_limiter() -> SlidingWindowRateLimiter:
    """20 requests per 10 seconds per key -- generous enough for a
    legitimate client polling /status every few seconds and posting a
    location update on a normal watchPosition cadence, tight enough to
    blunt a scripted flood against a single token."""
    global _share_limiter
    if _share_limiter is None:
        _share_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=10.0)
    return _share_limiter


_chat_auth_limiter: SlidingWindowRateLimiter | None = None


def get_chat_auth_rate_limiter() -> SlidingWindowRateLimiter:
    """10 requests per 60 seconds per responder_id -- the online-attack
    mitigation for the 6-digit PIN auth used by the chat/duty-session
    surface (see app/core/responder_auth.py). A 6-digit PIN has only
    1,000,000 possibilities; this limiter makes an online brute force
    impractically slow (at most 10 guesses/minute per responder_id)
    independent of the Argon2id hashing cost that mitigates an offline
    attack on a leaked hash."""
    global _chat_auth_limiter
    if _chat_auth_limiter is None:
        _chat_auth_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60.0)
    return _chat_auth_limiter
