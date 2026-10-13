"""Small shared constants/helpers for the dispatch feature: the live/stale/
offline threshold and classification, plus a tiny in-memory idempotency
guard against accidental double-click dispatch.

Kept separate from responder_store.py (storage) and the dispatch route
(HTTP layer) since both need the live/stale logic and only the route needs
the idempotency guard -- a small shared module avoids import cycles either
way.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

# Configurable via env var, per the task's explicit requirement -- not
# hardcoded. 60s default matches the task's own example threshold.
import os

STALE_THRESHOLD_SECONDS: float = float(os.getenv("RESPONDER_STALE_THRESHOLD_SECONDS", "60"))

LIVE = "live"
STALE = "stale"
OFFLINE = "offline"


def classify_location_liveness(last_seen_at: str | None, *, now: datetime | None = None) -> str:
    """Returns LIVE, STALE, or OFFLINE for a responder's last reported
    location.

    OFFLINE: no location has ever been reported (last_seen_at is None).
    LIVE: last_seen_at is within STALE_THRESHOLD_SECONDS of now.
    STALE: last_seen_at exists but is older than the threshold -- the
    record is NOT deleted (per the task's explicit instruction), it's just
    not dispatchable/live anymore.
    """
    if not last_seen_at:
        return OFFLINE
    try:
        seen = datetime.fromisoformat(last_seen_at)
    except ValueError:
        return OFFLINE
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    age_seconds = (reference - seen).total_seconds()
    if age_seconds <= STALE_THRESHOLD_SECONDS:
        return LIVE
    return STALE


class DispatchIdempotencyGuard:
    """Protects against accidental double-click dispatch: if the same
    (responder_id, idempotency_key) was sent within the last
    `window_seconds`, a second call is reported as deduplicated instead of
    sending a second real SMS.

    Deliberately simple per the task's explicit "do not overengineer"
    instruction: an in-memory dict with a lock, swept lazily on each call.
    Not persisted -- a backend restart naturally clears it, which is fine
    since its only purpose is suppressing a rapid double-click, not
    long-term dispatch history.
    """

    def __init__(self, window_seconds: float = 10.0):
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._recent: dict[str, float] = {}  # key -> monotonic timestamp of first send

    def check_and_mark(self, key: str) -> bool:
        """Returns True if this is a NEW request (caller should proceed and
        actually send), False if it's a duplicate within the window
        (caller should skip sending and report deduplicated=True)."""
        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            if key in self._recent:
                return False
            self._recent[key] = now
            return True

    def _sweep(self, now: float) -> None:
        expired = [k for k, ts in self._recent.items() if now - ts > self._window_seconds]
        for k in expired:
            del self._recent[k]


_guard: DispatchIdempotencyGuard | None = None


def get_dispatch_idempotency_guard() -> DispatchIdempotencyGuard:
    global _guard
    if _guard is None:
        _guard = DispatchIdempotencyGuard()
    return _guard
