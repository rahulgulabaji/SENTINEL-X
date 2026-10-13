"""Runtime responder registry + live GPS location store.

Same write-through JSON philosophy as app/core/sms_config_store.py and
app/services/job_repository.py: an in-memory dict as the source of truth
during the process lifetime, a threading.Lock() guarding reads/writes
(FastAPI's sync `def` routes run on Starlette's thread pool, so concurrent
requests are real), and persistence to disk on every create/update/delete
so registered responders survive a restart.

Unlike sms_config_store.py (one JSON blob) this is a small *collection*
keyed by responder id, one JSON file per responder under
storage/responders/{id}.json -- mirrors job_repository.py's
one-file-per-record layout exactly, and (unlike a single combined file)
means a single corrupted record can't take down the whole registry on
rehydration.

No fake/demo responders are ever created here. An empty directory means
zero responders, and every read method correctly returns an empty
list/None in that case -- never fabricated data.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Statuses are free-form-ish but normalized to lowercase on write so
# "AVAILABLE" (sent by the real frontend registration form) and "available"
# compare equal everywhere else in this module and in dispatch logic.
VALID_STATUSES = {"available", "busy", "offline"}
DEFAULT_STATUS = "available"


@dataclass(frozen=True)
class ResponderLocation:
    """Last known GPS fix for a responder. None fields mean "never
    reported a location yet" -- distinct from (0.0, 0.0), which is a real
    (if unlikely) coordinate."""

    latitude: float | None = None
    longitude: float | None = None
    accuracy_meters: float | None = None
    last_seen_at: str | None = None  # ISO 8601 UTC, server-stamped -- never client-supplied

    def to_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy_meters": self.accuracy_meters,
            "last_seen_at": self.last_seen_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "ResponderLocation":
        return ResponderLocation(
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            accuracy_meters=data.get("accuracy_meters"),
            last_seen_at=data.get("last_seen_at"),
        )


@dataclass(frozen=True)
class Responder:
    """A registered responder. Deliberately separate from the Pydantic API
    schemas (schemas/responders.py) -- this is the storage layer's own
    value type, same separation sms_config_store.py already uses.

    `unit` and `phone`/`phone_number` naming: the real frontend
    (frontend/src/App.jsx handleRegisterResponder) sends `phone` and
    `unit`, not `phone_number`. Both are accepted at the schema layer via
    aliases, but this storage type uses one canonical field name
    (phone_number) plus `unit` as its own first-class optional field, so
    there is exactly one source of truth here regardless of which alias
    the request used.
    """

    id: str
    name: str
    phone_number: str = ""
    role: str = ""
    unit: str = ""
    status: str = DEFAULT_STATUS
    location: ResponderLocation = field(default_factory=ResponderLocation)
    created_at: str = ""
    updated_at: str = ""
    # Chat/duty-session auth (see app/core/responder_auth.py). pin_hash is
    # an Argon2id hash, never the raw PIN -- the raw PIN is returned once
    # by the create-responder route and never persisted anywhere. None
    # means "no PIN issued yet" (e.g. a responder created before this
    # field existed) -- verify_pin() is never called against None.
    pin_hash: str | None = None
    pin_issued_at: str | None = None
    # Username/password login (see app/core/responder_auth.py's
    # hash_password/verify_password). password_hash is Argon2id, never the
    # raw password -- the raw password is returned once by the
    # create-responder route and never persisted anywhere, same discipline
    # as pin_hash above. Both None means "legacy PIN-only responder,
    # created before login existed" -- never fabricated.
    username: str | None = None
    password_hash: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phone_number": self.phone_number,
            "role": self.role,
            "unit": self.unit,
            "status": self.status,
            "location": self.location.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pin_hash": self.pin_hash,
            "pin_issued_at": self.pin_issued_at,
            "username": self.username,
            "password_hash": self.password_hash,
        }

    @staticmethod
    def from_dict(data: dict) -> "Responder":
        return Responder(
            id=data["id"],
            name=data.get("name", ""),
            phone_number=data.get("phone_number", ""),
            role=data.get("role", ""),
            unit=data.get("unit", ""),
            status=data.get("status", DEFAULT_STATUS),
            location=ResponderLocation.from_dict(data.get("location") or {}),
            # pin_hash/pin_issued_at: None for any record persisted before
            # this field existed -- never fabricated, just absent until a
            # PIN is explicitly (re)issued for that responder.
            pin_hash=data.get("pin_hash"),
            pin_issued_at=data.get("pin_issued_at"),
            username=data.get("username"),
            password_hash=data.get("password_hash"),
            # created_at/updated_at are backfilled for records persisted by
            # an older version of this store (before these fields existed)
            # -- never fabricated as a fake historical timestamp, just
            # stamped "now" the first time they're loaded without one, so a
            # restart doesn't crash on an older storage/responders/*.json.
            created_at=data.get("created_at") or _utcnow_iso(),
            updated_at=data.get("updated_at") or data.get("created_at") or _utcnow_iso(),
        )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_status(status: str | None) -> str:
    """Lowercases and validates. Falls back to DEFAULT_STATUS for an
    unrecognized value rather than raising -- a responder's status is
    operationally important but not worth hard-failing registration over
    an unexpected string; callers that care about strict validation (the
    route layer) check VALID_STATUSES themselves before calling this."""
    candidate = (status or "").strip().lower()
    return candidate if candidate in VALID_STATUSES else DEFAULT_STATUS


class ResponderStore:
    """Thread-safe, write-through, file-persisted responder registry.

    One JSON file per responder under `dir_path`, named `{id}.json`. Loads
    all existing files on construction (rehydration is immediate, not a
    deferred TODO like job_repository.py's, since responders are a small
    persistent registry rather than high-volume transient job state).
    """

    def __init__(self, dir_path: Path):
        self._dir_path = dir_path
        self._lock = threading.Lock()
        self._responders: dict[str, Responder] = {}
        self._load_from_disk()

    # -- reads ---------------------------------------------------------

    def list_all(self) -> list[Responder]:
        with self._lock:
            return list(self._responders.values())

    def get(self, responder_id: str) -> Responder | None:
        with self._lock:
            return self._responders.get(responder_id)

    # -- writes ----------------------------------------------------------

    def create(
        self,
        *,
        id: str | None = None,
        name: str,
        phone_number: str = "",
        role: str = "",
        unit: str = "",
        status: str = DEFAULT_STATUS,
    ) -> Responder:
        """Registers a new responder. `id` may be client-supplied (the real
        frontend generates its own `RESP-{timestamp}` ids) -- if omitted, a
        uuid4 is generated. If `id` collides with an existing responder,
        that responder is overwritten (treated as an upsert), which is the
        same semantics PUT would give anyway and avoids a confusing 409 for
        a client that's simply retrying its own registration."""
        with self._lock:
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
            )
            self._responders[responder_id] = responder
            self._persist(responder)
            return responder

    def update(self, responder_id: str, **fields) -> Responder | None:
        """Partial update of metadata fields (name/phone_number/role/unit/
        status). Does not touch `location` -- use update_location() for
        that, which is intentionally a separate, narrower method so a
        metadata PUT can never accidentally wipe a live GPS fix."""
        with self._lock:
            existing = self._responders.get(responder_id)
            if existing is None:
                return None
            if "status" in fields and fields["status"] is not None:
                fields["status"] = normalize_status(fields["status"])
            clean_fields = {k: v for k, v in fields.items() if v is not None}
            clean_fields["updated_at"] = _utcnow_iso()
            updated = replace(existing, **clean_fields)
            self._responders[responder_id] = updated
            self._persist(updated)
            return updated

    def delete(self, responder_id: str) -> bool:
        with self._lock:
            if responder_id not in self._responders:
                return False
            del self._responders[responder_id]
            path = self._dir_path / f"{responder_id}.json"
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to delete responder file %s", path)
            return True

    def update_location(
        self,
        responder_id: str,
        *,
        latitude: float,
        longitude: float,
        accuracy_meters: float | None,
    ) -> Responder | None:
        """Records a new GPS fix. last_seen_at is ALWAYS the server's own
        current timestamp -- never taken from the request body, so a
        client clock skew or replayed stale payload can't fake liveness."""
        with self._lock:
            existing = self._responders.get(responder_id)
            if existing is None:
                return None
            new_location = ResponderLocation(
                latitude=latitude,
                longitude=longitude,
                accuracy_meters=accuracy_meters,
                last_seen_at=_utcnow_iso(),
            )
            updated = replace(existing, location=new_location, updated_at=_utcnow_iso())
            self._responders[responder_id] = updated
            self._persist(updated)
            return updated

    # -- persistence -----------------------------------------------------

    def _load_from_disk(self) -> None:
        if not self._dir_path.exists():
            return
        for path in sorted(self._dir_path.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                responder = Responder.from_dict(data)
                self._responders[responder.id] = responder
            except (OSError, ValueError, KeyError):
                logger.exception("Failed to rehydrate responder from %s -- skipping.", path)

    def _persist(self, responder: Responder) -> None:
        try:
            self._dir_path.mkdir(parents=True, exist_ok=True)
            path = self._dir_path / f"{responder.id}.json"
            path.write_text(json.dumps(responder.to_dict(), indent=2), encoding="utf-8")
        except OSError:
            logger.exception("Failed to persist responder %s", responder.id)


_store: ResponderStore | None = None


def get_responder_store(settings=None) -> ResponderStore:
    """Process-wide ResponderStore singleton, same convention as
    get_settings()/get_sms_config_store() elsewhere in this codebase.

    Passing `settings` explicitly builds a fresh, uncached instance (used by
    tests to point at a temp directory without touching the real singleton).
    """
    global _store
    if settings is not None:
        return ResponderStore(dir_path=settings.STORAGE_DIR / "responders")
    if _store is None:
        from app.core.config import get_settings

        _store = ResponderStore(dir_path=get_settings().STORAGE_DIR / "responders")
    return _store
