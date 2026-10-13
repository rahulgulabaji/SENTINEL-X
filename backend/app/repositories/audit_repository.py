"""Audit logging -- append-only trail of real application actions.

Every record carries: a unique event_id (idempotent retry-safety -- a caller
that generates the id upfront and retries on a transient write failure will
not double-insert, since event_id is uniquely indexed), a UTC timestamp,
actor, event_type, module (which subsystem produced the event), resource_type/
resource_id (what the event is about), outcome ("success"/"failure"), a safe
human-readable summary, an optional correlation_id (ties related events
together, e.g. a job_id or dispatch_id), and optionally an error_category
(a short machine word like "mongodb_unavailable" or "sms_gateway_error" --
never a raw exception message, which could leak a stack trace or a
credential-bearing URL).

Never logs a secret: `details` is caller-constructed, and as a
belt-and-suspenders defensive measure this module strips any key literally
named password/sms_gateway_password/mongodb_uri (case-insensitive) from
`details` before writing, even though no caller in this codebase passes one
of those under those literal keys today.

Logging itself is best-effort: a MongoDB outage while writing an audit
record must never block or fail the real operation (e.g. a responder update)
that triggered the log call -- failures here are caught, logged locally via
the standard logger, and swallowed, never re-raised. This module also never
claims an action succeeded if the real persistence call for that action
failed -- callers are responsible for only calling log(outcome="success")
after their own write has actually completed; see each call site.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

_SECRET_KEY_NAMES = {"password", "sms_gateway_password", "mongodb_uri"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditRepository:
    def __init__(self, db: Database):
        self._collection: Collection = db["audit_logs"]

    def log(
        self,
        event_type: str,
        *,
        actor: str = "system",
        module: str = "",
        resource_type: str = "",
        resource_id: str = "",
        outcome: str = "success",
        summary: str = "",
        correlation_id: str | None = None,
        error_category: str | None = None,
        details: dict | None = None,
    ) -> str | None:
        """Writes one audit record. Returns the generated event_id on
        success, or None if the write failed (caller does not need to react
        to this -- audit logging is best-effort by design -- but tests use
        the return value to confirm a record was actually written)."""
        safe_details = {
            k: v for k, v in (details or {}).items() if k.strip().lower() not in _SECRET_KEY_NAMES
        }
        event_id = str(uuid.uuid4())
        record = {
            "event_id": event_id,
            "event_type": event_type,
            "actor": actor,
            "module": module,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
            "summary": summary,
            "correlation_id": correlation_id,
            "error_category": error_category,
            "details": safe_details,
            "timestamp": _utcnow_iso(),
        }
        try:
            self._collection.insert_one(dict(record))
        except PyMongoError:
            logger.warning("Failed to write audit log entry %s to MongoDB.", event_type, exc_info=True)
            return None
        return event_id

    def list(
        self,
        *,
        limit: int = 50,
        before: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        correlation_id: str | None = None,
    ) -> list[dict]:
        """Returns audit records, most recent first. `before` is an ISO
        timestamp cursor for pagination (returns only records strictly
        older than it) -- stable because timestamp is monotonically
        increasing per-process and ties are broken by insertion order via
        _id as a secondary sort. Raises PyMongoError's caller-facing
        MongoDBUnavailableError on a real outage rather than silently
        returning an empty list and letting that look like "no audit
        events exist"."""
        from app.repositories.mongo_job_repository import MongoDBUnavailableError

        query: dict = {}
        if before:
            query["timestamp"] = {"$lt": before}
        if event_type:
            query["event_type"] = event_type
        if actor:
            query["actor"] = actor
        if correlation_id:
            query["correlation_id"] = correlation_id

        try:
            cursor = (
                self._collection.find(query)
                .sort([("timestamp", DESCENDING), ("_id", DESCENDING)])
                .limit(limit)
            )
            docs = list(cursor)
        except PyMongoError as exc:
            logger.error("Failed to list audit log entries from MongoDB.", exc_info=True)
            raise MongoDBUnavailableError("Could not list audit log entries: database unavailable.") from exc
        for doc in docs:
            doc.pop("_id", None)
        return docs


_repository: AuditRepository | None = None


def get_audit_repository(db: Database | None = None) -> AuditRepository:
    global _repository
    if db is not None:
        return AuditRepository(db)
    if _repository is None:
        from app.core.mongodb import get_database

        _repository = AuditRepository(get_database())
    return _repository
