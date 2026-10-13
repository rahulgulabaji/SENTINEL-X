"""Dispatch SEND persistence only -- preview never writes here.

This is the one place preview/send are made unambiguously distinguishable:
preview_dispatch() in app/api/routes/dispatch.py never calls anything in
this module (it only ever logs via audit_repository), so a `dispatches`
document existing at all means a real SMS send was attempted. There is no
record_preview() method here, deliberately.

Never accepts or stores a password or any SMS gateway credential -- the
schema below has no such field, and the one value this module ever persists
from the gateway side is SmsResult (success: bool, message: str,
error: str|None), which structurally cannot carry a password since
app/services/sms_gateway.py's SmsResult dataclass never has one.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.repositories.mongo_job_repository import MongoDBUnavailableError

logger = logging.getLogger(__name__)


class DispatchRepository:
    def __init__(self, db: Database):
        self._collection: Collection = db["dispatches"]

    def record_send(
        self,
        *,
        incident_id: str | None,
        responder_id: str,
        message: str,
        success: bool,
        error: str | None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "dispatch_id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "responder_id": responder_id,
            "message": message,
            "status": "sent" if success else "failed",
            "created_at": now,
            "sent_at": now if success else None,
            "error": error,
        }
        try:
            self._collection.insert_one(dict(record))
        except PyMongoError as exc:
            # A failure to RECORD a dispatch must never be confused with a
            # failure to SEND one -- the SMS itself has already been
            # attempted by the caller before this is invoked. Log loudly but
            # do not re-raise as if the send itself failed; the route layer
            # decides separately whether an unrecorded-but-sent SMS should
            # still report success=True to the operator (it should -- the
            # SMS gateway's own result is authoritative for that).
            logger.error("Failed to record dispatch for responder %s in MongoDB.", responder_id, exc_info=True)
        return record

    def list_for_incident(self, incident_id: str) -> list[dict]:
        try:
            docs = list(self._collection.find({"incident_id": incident_id}))
        except PyMongoError as exc:
            logger.error("Failed to list dispatches for incident %s from MongoDB.", incident_id, exc_info=True)
            raise MongoDBUnavailableError(
                f"Could not list dispatches for incident {incident_id}: database unavailable."
            ) from exc
        for doc in docs:
            doc.pop("_id", None)
        return docs


_repository: DispatchRepository | None = None


def get_dispatch_repository(db: Database | None = None) -> DispatchRepository:
    global _repository
    if db is not None:
        return DispatchRepository(db)
    if _repository is None:
        from app.core.mongodb import get_database

        _repository = DispatchRepository(get_database())
    return _repository
