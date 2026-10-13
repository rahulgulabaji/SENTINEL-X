"""MongoDB-backed share sessions for the voluntary live-location-sharing
feature.

Same constructor-takes-a-db / raise-MongoDBUnavailableError-on-failure
convention as responder_repository.py and dispatch_repository.py.

Two separate expiry clocks are tracked on each document, matching the
share-link design: `invite_expires_at` bounds first use (checked only by
mark_active()); `active_until` bounds an already-started session (checked
only by record_update()/is_active()). The raw share token is NEVER stored --
only `token_hash` (sha256, see app/core/share_tokens.py:hash_token) -- so a
database read alone can never yield a usable token, matching this project's
existing "never store the password field" convention
(dispatch_repository.py).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.share_tokens import hash_token as _hash_token
from app.repositories.mongo_job_repository import MongoDBUnavailableError

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_STOPPED = "stopped"
STATUS_EXPIRED = "expired"

# session_kind distinguishes a dispatch-triggered share session (no longer
# created by app/api/routes/dispatch.py -- incident SMS now links to the
# incident's own location instead of asking the responder to share theirs;
# this kind is kept for backward compatibility with old records) from a
# duty-shift session (created by
# app/services/duty_session_service.py when a responder sends "join" with
# no specific incident attached yet). A document written before this
# field existed reads back as SESSION_KIND_DISPATCH via
# `.get("session_kind", SESSION_KIND_DISPATCH)` -- no migration needed.
SESSION_KIND_DISPATCH = "dispatch"
SESSION_KIND_DUTY = "duty"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class ShareSessionRepository:
    def __init__(self, db: Database):
        self._collection: Collection = db["share_sessions"]

    def create(
        self,
        *,
        responder_id: str,
        dispatch_id: str | None,
        invite_ttl_seconds: int,
        token_factory,
        session_kind: str = SESSION_KIND_DISPATCH,
    ) -> tuple[dict, str]:
        """Creates a new pending share session and returns (document, raw
        token). `token_factory(session_id, responder_id) -> str` mints the
        signed token (see app/core/share_tokens.issue_token) -- passed in
        rather than imported here, so this repository stays free of any
        dependency on the token-signing module, matching this project's
        existing separation between storage (repositories/) and the
        core/ modules that have no I/O of their own. The session_id a
        token embeds must be generated before the document is built (the
        token can't reference an id that doesn't exist yet), which is why
        token minting happens inside this method rather than the caller
        supplying a pre-computed token_hash -- that would otherwise need a
        second write to attach it after the fact.

        The returned document's own `token_hash` field is populated before
        the single insert -- no second write, no reach into this
        repository's private `_collection` from outside the class.

        `session_kind` defaults to "dispatch" (today's only kind, used by
        app/api/routes/dispatch.py), preserving every existing call site's
        behavior with zero changes required there. Pass "duty" for a
        shift-start session with no incident attached yet (dispatch_id may
        be None in that case) -- see get_active_duty_session_for_responder
        / list_active_duty_sessions below.
        """
        now = _utcnow()
        session_id = str(uuid.uuid4())
        token = token_factory(session_id, responder_id)
        doc = {
            "session_id": session_id,
            "token_hash": _hash_token(token),
            "responder_id": responder_id,
            "dispatch_id": dispatch_id,
            "session_kind": session_kind,
            "created_at": _iso(now),
            "invite_expires_at": _iso(now + timedelta(seconds=invite_ttl_seconds)),
            "active_until": None,
            "status": STATUS_PENDING,
            "last_update_at": None,
            "last_lat": None,
            "last_lng": None,
            "last_accuracy_m": None,
        }
        try:
            self._collection.insert_one(dict(doc))
        except PyMongoError as exc:
            logger.error("Failed to create share session for responder %s in MongoDB.", responder_id, exc_info=True)
            raise MongoDBUnavailableError("Could not create share session: database unavailable.") from exc
        doc.pop("_id", None)
        return doc, token

    def reissue_token(self, session_id: str, *, new_token: str) -> bool:
        """Overwrites an existing session's token_hash with a freshly
        minted token's hash, without touching status/active_until/any other
        field. Used when a login resumes an already-active/pending duty
        session: the original raw token was never stored (only its hash),
        so a repeat login needs a new usable token bound to the same
        session rather than being locked out. Returns True if a session
        with this id existed and was updated."""
        try:
            result = self._collection.update_one(
                {"session_id": session_id}, {"$set": {"token_hash": _hash_token(new_token)}}
            )
        except PyMongoError as exc:
            logger.error("Failed to reissue token for session %s in MongoDB.", session_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not reissue token for session {session_id}: database unavailable.") from exc
        return result.matched_count > 0

    def get_active_duty_session_for_responder(self, responder_id: str) -> dict | None:
        """The responder's current duty session, if any -- "pending" (join
        sent, link not yet opened) or "active" (sharing, not yet expired)
        only. Used for JOIN_JOB idempotency (resume instead of creating a
        second session) and by duty_session_service.get_duty_status().
        Lazily expires a stale "active" row the same way is_active() does,
        so a long-dead session is never returned as if it were current.
        """
        try:
            doc = self._collection.find_one(
                {
                    "responder_id": responder_id,
                    "session_kind": SESSION_KIND_DUTY,
                    "status": {"$in": [STATUS_PENDING, STATUS_ACTIVE]},
                },
                sort=[("created_at", -1)],
            )
        except PyMongoError as exc:
            logger.error("Failed to read duty session for responder %s from MongoDB.", responder_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not read duty session for responder {responder_id}: database unavailable.") from exc
        if doc is None:
            return None
        if doc["status"] == STATUS_ACTIVE and not self._is_active_doc(doc):
            self._mark_expired(doc["session_id"])
            return None
        doc.pop("_id", None)
        return doc

    def list_active_duty_sessions(self) -> list[dict]:
        """Every responder's duty session that is genuinely "active" right
        now (opened the link, pressed Start, not yet expired) -- NOT
        "pending" (joined but never actually started sharing). Used by
        app/services/duty_dispatch_service.py to find dispatch-eligible
        on-duty responders; "pending" is deliberately excluded here since a
        responder who never opened their link has no real location to
        dispatch against."""
        try:
            docs = list(
                self._collection.find({"session_kind": SESSION_KIND_DUTY, "status": STATUS_ACTIVE})
            )
        except PyMongoError as exc:
            logger.error("Failed to list active duty sessions from MongoDB.", exc_info=True)
            raise MongoDBUnavailableError("Could not list active duty sessions: database unavailable.") from exc
        out = []
        for doc in docs:
            if not self._is_active_doc(doc):
                self._mark_expired(doc["session_id"])
                continue
            doc.pop("_id", None)
            out.append(doc)
        return out

    def _is_active_doc(self, doc: dict) -> bool:
        """Pure check against an already-fetched document -- same
        active_until comparison is_active() makes, factored out so
        list_active_duty_sessions() doesn't need a second round-trip per
        candidate."""
        active_until = doc.get("active_until")
        if doc.get("status") != STATUS_ACTIVE or not active_until:
            return False
        return _utcnow() < _parse_iso(active_until)

    def get(self, session_id: str) -> dict | None:
        try:
            doc = self._collection.find_one({"session_id": session_id})
        except PyMongoError as exc:
            logger.error("Failed to read share session %s from MongoDB.", session_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not read share session {session_id}: database unavailable.") from exc
        if doc is None:
            return None
        doc.pop("_id", None)
        return doc

    def mark_active(self, session_id: str, *, responder_id: str, active_duration_seconds: int) -> dict | None:
        """Transitions a PENDING session to ACTIVE. Idempotent: calling this
        again on an already-ACTIVE session for the same responder succeeds
        without resetting active_until (so a page reload / double-tap of
        Start doesn't quietly grant extra time). Returns None if the session
        doesn't exist, belongs to a different responder, or is already
        stopped/expired -- the route maps None to a generic 403.

        Invitation expiry (`invite_expires_at`) is intentionally checked by
        the caller (via share_tokens.verify_token, before this is called),
        not here -- this method only enforces the session's own state
        machine, not the token's.
        """
        try:
            existing = self._collection.find_one({"session_id": session_id})
        except PyMongoError as exc:
            logger.error("Failed to read share session %s in MongoDB.", session_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not read share session {session_id}: database unavailable.") from exc

        if existing is None or existing.get("responder_id") != responder_id:
            return None

        if existing.get("status") == STATUS_ACTIVE:
            existing.pop("_id", None)
            return existing  # already active -- idempotent no-op

        if existing.get("status") != STATUS_PENDING:
            return None  # stopped/expired -- cannot be (re)started

        now = _utcnow()
        try:
            doc = self._collection.find_one_and_update(
                {"session_id": session_id, "status": STATUS_PENDING},
                {
                    "$set": {
                        "status": STATUS_ACTIVE,
                        "active_until": _iso(now + timedelta(seconds=active_duration_seconds)),
                    }
                },
                return_document=True,
            )
        except PyMongoError as exc:
            logger.error("Failed to activate share session %s in MongoDB.", session_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not activate share session {session_id}: database unavailable.") from exc
        if doc is None:
            return None
        doc.pop("_id", None)
        return doc

    def is_active(self, session_id: str) -> dict | None:
        """Returns the session document if status is ACTIVE and
        now < active_until, else None (and, as a side effect, flips a
        timed-out ACTIVE session to EXPIRED so subsequent reads/UI reflect
        it truthfully rather than looking perpetually 'active')."""
        doc = self.get(session_id)
        if doc is None or doc.get("status") != STATUS_ACTIVE:
            return None
        active_until = doc.get("active_until")
        if not active_until or _utcnow() >= _parse_iso(active_until):
            self._mark_expired(session_id)
            return None
        return doc

    def record_update(self, session_id: str, *, latitude: float, longitude: float, accuracy_meters: float | None) -> bool:
        """Stamps the session's own last-update fields (used by the share
        page's own status display). Does NOT write to the responders
        collection -- that write-through happens in the route, via the
        existing MongoResponderRepository.update_location(), keeping this
        repository focused on share-session state only. Returns False if
        the session is not currently active (caller should treat as 403)."""
        now = _iso(_utcnow())
        try:
            result = self._collection.update_one(
                {"session_id": session_id, "status": STATUS_ACTIVE},
                {
                    "$set": {
                        "last_update_at": now,
                        "last_lat": latitude,
                        "last_lng": longitude,
                        "last_accuracy_m": accuracy_meters,
                    }
                },
            )
        except PyMongoError as exc:
            logger.error("Failed to record location update for share session %s in MongoDB.", session_id, exc_info=True)
            raise MongoDBUnavailableError(
                f"Could not record location update for share session {session_id}: database unavailable."
            ) from exc
        return result.matched_count > 0

    def mark_stopped(self, session_id: str) -> bool:
        """Idempotent: safe to call on any existing session regardless of
        current status (pending/active/already-stopped/expired) -- stopping
        is always a safe, final transition. Returns False only if the
        session_id doesn't exist at all."""
        try:
            result = self._collection.update_one(
                {"session_id": session_id},
                {"$set": {"status": STATUS_STOPPED}},
            )
        except PyMongoError as exc:
            logger.error("Failed to stop share session %s in MongoDB.", session_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not stop share session {session_id}: database unavailable.") from exc
        return result.matched_count > 0

    def _mark_expired(self, session_id: str) -> None:
        try:
            self._collection.update_one(
                {"session_id": session_id, "status": STATUS_ACTIVE},
                {"$set": {"status": STATUS_EXPIRED}},
            )
        except PyMongoError:
            # Best-effort only -- is_active() already returns None to the
            # caller regardless, so a failure to persist the EXPIRED label
            # doesn't change the authorization outcome, only a cosmetic
            # status field. Not re-raised.
            logger.warning("Failed to mark share session %s expired in MongoDB.", session_id, exc_info=True)


_repository: ShareSessionRepository | None = None


def get_share_session_repository(db: Database | None = None) -> ShareSessionRepository:
    """Process-wide singleton, same lazy-with-test-escape-hatch convention as
    get_mongo_responder_repository()/get_dispatch_repository()."""
    global _repository
    if db is not None:
        return ShareSessionRepository(db)
    if _repository is None:
        from app.core.mongodb import get_database

        _repository = ShareSessionRepository(get_database())
    return _repository
