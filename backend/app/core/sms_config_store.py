"""Runtime-mutable SMS gateway configuration store.

Settings (app/core/config.py) is a frozen, process-lifetime singleton loaded
once from .env at import time -- by design, and not something this feature
should change (it's shared by YOLO/CORS/upload config too). But the SMS
gateway's URL/username/password/enabled flag need to be editable from the
UI and take effect immediately, without restarting FastAPI.

This module bridges that gap with a small write-through JSON store, same
pattern as InMemoryJobRepository (app/services/job_repository.py): an
in-memory value as the source of truth during the process lifetime, a
threading.Lock() guarding reads/writes (FastAPI's sync `def` routes run on
Starlette's thread pool, so concurrent requests are real), and persistence
to one JSON file on every update() so configuration survives a restart.

Seed-once-then-override semantics: on first run (no JSON file yet), the
store seeds itself from Settings.SMS_GATEWAY_* (i.e. whatever is in .env)
and writes that out immediately. From then on, the JSON file is the
source of truth forever -- Settings/.env are never consulted again, so a
UI-driven change always wins and survives a restart on its own.

sms_gateway.py (SmsGatewayService) is NOT modified to know about this
store. Instead, callers build a fresh Settings-shaped object via
dataclasses.replace() using current store values and pass that to
get_sms_gateway_service() -- see app/api/routes/notifications.py. This
file has no dependency on SmsGatewayService at all.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmsConfigValues:
    """Current SMS gateway configuration. Deliberately separate from both
    the Pydantic API schemas (schemas/notifications.py) and Settings --
    this is the storage layer's own value type."""

    enabled: bool = False
    url: str = ""
    username: str = ""
    password: str = ""

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "url": self.url, "username": self.username, "password": self.password}

    @staticmethod
    def from_dict(data: dict) -> "SmsConfigValues":
        return SmsConfigValues(
            enabled=bool(data.get("enabled", False)),
            url=str(data.get("url", "")),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
        )


class SmsConfigStore:
    """Thread-safe, write-through, file-persisted SMS gateway config.

    Never logs or exposes the password value itself -- only this module and
    the route layer touch `.password` directly, and the route layer never
    puts it in a response (see schemas.SmsConfigGetResponse's
    `password_configured: bool` instead of a password field).
    """

    def __init__(self, path: Path, seed: SmsConfigValues):
        self._path = path
        self._lock = threading.Lock()
        self._values = self._load_or_seed(seed)

    def get(self) -> SmsConfigValues:
        with self._lock:
            return self._values

    def update(
        self,
        *,
        enabled: bool | None = None,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> SmsConfigValues:
        """Partial update -- any argument left as None keeps its current
        value. `password` specifically: None or "" means "keep the existing
        password", matching the UI's blank-field-means-unchanged contract.
        """
        with self._lock:
            current = self._values
            updated = replace(
                current,
                enabled=current.enabled if enabled is None else enabled,
                url=current.url if url is None else url,
                username=current.username if username is None else username,
                password=current.password if not password else password,
            )
            self._values = updated
            self._persist(updated)
            return updated

    def _load_or_seed(self, seed: SmsConfigValues) -> SmsConfigValues:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                return SmsConfigValues.from_dict(data)
            except (OSError, ValueError):
                logger.exception("Failed to load SMS gateway config from %s -- falling back to seed.", self._path)
                return seed
        # First run: no file yet -- seed from Settings/.env and persist
        # immediately so this becomes the durable source of truth going
        # forward (file always wins once it exists).
        self._persist(seed)
        return seed

    def _persist(self, values: SmsConfigValues) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(values.to_dict(), indent=2), encoding="utf-8")
            try:
                # Best-effort owner-only permissions. No-op in practice on
                # Windows; correct and meaningful on any future Linux/macOS
                # deployment. Never fatal if unsupported.
                self._path.chmod(0o600)
            except OSError:
                pass
        except OSError:
            logger.exception("Failed to persist SMS gateway config to %s", self._path)


_store: SmsConfigStore | None = None


def get_sms_config_store(settings=None) -> SmsConfigStore:
    """Process-wide SmsConfigStore singleton, same convention as
    get_settings()/get_sms_gateway_service() elsewhere in this codebase.

    Passing `settings` explicitly builds a fresh, uncached instance (used by
    tests to point at a temp directory without touching the real singleton).
    """
    global _store
    if settings is not None:
        return SmsConfigStore(
            path=settings.STORAGE_DIR / "sms_gateway_config.json",
            seed=SmsConfigValues(
                enabled=settings.SMS_GATEWAY_ENABLED,
                url=settings.SMS_GATEWAY_URL,
                username=settings.SMS_GATEWAY_USERNAME,
                password=settings.SMS_GATEWAY_PASSWORD,
            ),
        )
    if _store is None:
        from app.core.config import get_settings

        base_settings = get_settings()
        _store = SmsConfigStore(
            path=base_settings.STORAGE_DIR / "sms_gateway_config.json",
            seed=SmsConfigValues(
                enabled=base_settings.SMS_GATEWAY_ENABLED,
                url=base_settings.SMS_GATEWAY_URL,
                username=base_settings.SMS_GATEWAY_USERNAME,
                password=base_settings.SMS_GATEWAY_PASSWORD,
            ),
        )
    return _store
