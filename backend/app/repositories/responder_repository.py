"""MongoDB-backed responder registry + location history.

Duck-typed to app/core/responder_store.py's ResponderStore method surface
exactly (list_all/get/create/update/delete/update_location) -- deliberately
NOT a new ABC. The existing codebase only introduces an ABC where one already
existed before this task (JobRepository); responders never had one, and
retrofitting an abstraction nothing else requires would be unjustified
over-engineering for this change.

Reuses the existing Responder/ResponderLocation dataclasses from
responder_store.py as the in-process value type -- no duplicate dataclass is
defined here. responder_store.py itself is untouched and stays in place as
the migration source / pre-existing JSON-backed implementation.

Current-location vs history: the embedded `location` field on a `responders`
document is the current-state source of truth (matches today's embedded
shape exactly -- zero API/route change). `responder_locations` is a pure
append-only history collection, one document per GPS fix, written in
addition to (never instead of) the current-state update. GeoJSON coordinate
order is [longitude, latitude] -- NOT [latitude, longitude]; getting this
backwards is the single easiest bug to introduce here, hence the inline
comment at the one place it's constructed below.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.responder_store import Responder, ResponderLocation, VALID_STATUSES, DEFAULT_STATUS, normalize_status
from app.repositories.mongo_job_repository import MongoDBUnavailableError

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _doc_to_responder(doc: dict) -> Responder:
    doc.pop("_id", None)
    location_data = doc.get("location") or {}
    return Responder(
        id=doc["id"],
        name=doc.get("name", ""),
        phone_number=doc.get("phone_number", ""),
        role=doc.get("role", ""),
        unit=doc.get("unit", ""),
        status=doc.get("status", DEFAULT_STATUS),
        location=ResponderLocation.from_dict(location_data),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        # None for any document written before PIN auth existed -- never
        # fabricated, see app/core/responder_auth.py.
        pin_hash=doc.get("pin_hash"),
        pin_issued_at=doc.get("pin_issued_at"),
        # None for any document written before username/password login
        # existed -- never fabricated, same discipline as pin_hash above.
        username=doc.get("username"),
        password_hash=doc.get("password_hash"),
    )


class MongoResponderRepository:
    """Same method surface as ResponderStore. All methods raise
    MongoDBUnavailableError (never return a silently-empty/None result that
    could be mistaken for "no such responder") when MongoDB itself can't be
    reached -- a connectivity failure must never look identical to a
    legitimate 404."""

    def __init__(self, db: Database):
        self._responders: Collection = db["responders"]
        self._locations: Collection = db["responder_locations"]

    def list_all(self) -> list[Responder]:
        try:
            docs = list(self._responders.find({}))
        except PyMongoError as exc:
            logger.error("Failed to list responders from MongoDB.", exc_info=True)
            raise MongoDBUnavailableError("Could not list responders: database unavailable.") from exc
        out = []
        for doc in docs:
            try:
                out.append(_doc_to_responder(doc))
            except (KeyError, ValueError):
                # Malformed document (e.g. missing required `id`) -- skip
                # and log rather than let one bad record crash the whole
                # listing, same resilience responder_store.py's
                # _load_from_disk() already applies to a corrupt JSON file.
                logger.exception("Skipping malformed responder document: %r", doc)
        return out

    def get(self, responder_id: str) -> Responder | None:
        try:
            doc = self._responders.find_one({"id": responder_id})
        except PyMongoError as exc:
            logger.error("Failed to read responder %s from MongoDB.", responder_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not read responder {responder_id}: database unavailable.") from exc
        if doc is None:
            return None
        return _doc_to_responder(doc)

    def create(
        self,
        *,
        id: str | None = None,
        name: str,
        phone_number: str = "",
        role: str = "",
        unit: str = "",
        status: str = DEFAULT_STATUS,
        pin_hash: str | None = None,
        pin_issued_at: str | None = None,
        username: str | None = None,
        password_hash: str | None = None,
    ) -> Responder:
        """pin_hash/pin_issued_at/password_hash are pre-computed by the
        caller (the route layer, via app/core/responder_auth.py) -- this
        repository stays a dumb persistence layer and never generates or
        hashes a credential itself, matching this file's existing
        separation of concerns."""
        responder_id = id or str(uuid.uuid4())
        now = _utcnow_iso()
        responder = Responder(
            id=responder_id,
            name=name,
            phone_number=phone_number,
            role=role,
            unit=unit,
            status=normalize_status(status),
            created_at=now,
            updated_at=now,
            pin_hash=pin_hash,
            pin_issued_at=pin_issued_at,
            username=username,
            password_hash=password_hash,
        )
        try:
            # Upsert, matching ResponderStore.create()'s existing semantics:
            # an id collision overwrites (treated as a retry of the same
            # registration), not a 409.
            self._responders.update_one(
                {"id": responder_id},
                {"$set": responder.to_dict()},
                upsert=True,
            )
        except PyMongoError as exc:
            logger.error("Failed to create responder %s in MongoDB.", responder_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not create responder {responder_id}: database unavailable.") from exc
        return responder

    def get_by_username(self, username: str) -> Responder | None:
        """Looks up a responder by their login username. Used only by the
        login route -- never exposes password_hash beyond this process
        boundary (the route layer verifies the password and discards the
        hash immediately after)."""
        try:
            doc = self._responders.find_one({"username": username})
        except PyMongoError as exc:
            logger.error("Failed to look up responder by username in MongoDB.", exc_info=True)
            raise MongoDBUnavailableError("Could not look up responder by username: database unavailable.") from exc
        if doc is None:
            return None
        return _doc_to_responder(doc)

    def reissue_pin(self, responder_id: str, *, pin_hash: str, pin_issued_at: str) -> Responder | None:
        """Operator-triggered PIN rotation: overwrites pin_hash/pin_issued_at
        only, leaving every other field untouched. Returns None if the
        responder doesn't exist (never silently creates one)."""
        try:
            doc = self._responders.find_one_and_update(
                {"id": responder_id},
                {"$set": {"pin_hash": pin_hash, "pin_issued_at": pin_issued_at, "updated_at": _utcnow_iso()}},
                return_document=True,
            )
        except PyMongoError as exc:
            logger.error("Failed to reissue PIN for responder %s in MongoDB.", responder_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not reissue PIN for responder {responder_id}: database unavailable.") from exc
        if doc is None:
            return None
        return _doc_to_responder(doc)

    def update(self, responder_id: str, **fields) -> Responder | None:
        if "status" in fields and fields["status"] is not None:
            fields["status"] = normalize_status(fields["status"])
        clean_fields = {k: v for k, v in fields.items() if v is not None}
        clean_fields["updated_at"] = _utcnow_iso()
        try:
            doc = self._responders.find_one_and_update(
                {"id": responder_id},
                {"$set": clean_fields},
                return_document=True,
            )
        except PyMongoError as exc:
            logger.error("Failed to update responder %s in MongoDB.", responder_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not update responder {responder_id}: database unavailable.") from exc
        if doc is None:
            return None
        return _doc_to_responder(doc)

    def delete(self, responder_id: str) -> bool:
        try:
            result = self._responders.delete_one({"id": responder_id})
        except PyMongoError as exc:
            logger.error("Failed to delete responder %s in MongoDB.", responder_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not delete responder {responder_id}: database unavailable.") from exc
        return result.deleted_count > 0

    def update_location(
        self,
        responder_id: str,
        *,
        latitude: float,
        longitude: float,
        accuracy_meters: float | None,
    ) -> Responder | None:
        now = _utcnow_iso()
        new_location = ResponderLocation(
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            last_seen_at=now,
        )
        try:
            doc = self._responders.find_one_and_update(
                {"id": responder_id},
                {"$set": {"location": new_location.to_dict(), "updated_at": now}},
                return_document=True,
            )
            if doc is not None:
                # Append-only history write -- GeoJSON coordinate order is
                # [longitude, latitude], NOT [latitude, longitude]. This is
                # the one place that order is constructed; get it backwards
                # here and every geospatial query/map rendering silently
                # transposes north/south and east/west.
                self._locations.insert_one(
                    {
                        "responder_id": responder_id,
                        "location": {"type": "Point", "coordinates": [longitude, latitude]},
                        "accuracy_meters": accuracy_meters,
                        "timestamp": now,
                    }
                )
        except PyMongoError as exc:
            logger.error("Failed to update location for responder %s in MongoDB.", responder_id, exc_info=True)
            raise MongoDBUnavailableError(
                f"Could not update location for responder {responder_id}: database unavailable."
            ) from exc
        if doc is None:
            return None
        return _doc_to_responder(doc)


_repository: MongoResponderRepository | None = None


def get_mongo_responder_repository(db: Database | None = None) -> MongoResponderRepository:
    """Process-wide singleton, same lazy-with-test-escape-hatch convention as
    get_responder_store()/get_sms_config_store(). Passing `db` explicitly
    builds a fresh, uncached instance (used by tests to point this module at
    a mongomock database without touching the real singleton)."""
    global _repository
    if db is not None:
        return MongoResponderRepository(db)
    if _repository is None:
        from app.core.mongodb import get_database

        _repository = MongoResponderRepository(get_database())
    return _repository
