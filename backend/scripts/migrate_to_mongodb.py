#!/usr/bin/env python
"""Standalone, manually-invoked migration script: copies the existing
JSON-file-backed data (storage/responders/*.json, storage/results/*.json)
into MongoDB. Never run automatically by the app itself.

Idempotent by design: every write is an upsert keyed on the record's own id
(`id` for responders, `job_id` for analysis jobs), so running this script
twice in a row produces the exact same document count as running it once --
safe to re-run after adding more local JSON files, or just to double-check
nothing was missed.

Never touches storage/sms_gateway_config.json -- no code path in this
script reads it, and it is explicitly out of scope for migration (secrets
stay file-backed, see app/core/sms_config_store.py).

Prints only counts -- never document contents, the configured MongoDB URI,
or any credential.

Usage (from backend/, with MONGODB_URI already set in the environment or a
loaded .env):
    python scripts/migrate_to_mongodb.py

Exits non-zero immediately (before touching any file) if MONGODB_URI is
unset or MongoDB is unreachable -- fail fast, not halfway through a batch.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.mongodb import get_database, ping  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("migrate_to_mongodb")


def _load_json_files(directory: Path) -> list[dict]:
    """Reads every *.json file in `directory`, skipping (and logging, not
    raising on) any file that fails to parse -- a single corrupt record must
    not abort the whole migration run."""
    records = []
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            logger.warning("Skipping unreadable/corrupt file: %s", path.name)
    return records


def migrate_responders(db) -> int:
    responders_dir = BACKEND_ROOT / "storage" / "responders"
    records = _load_json_files(responders_dir)
    collection = db["responders"]
    count = 0
    for record in records:
        responder_id = record.get("id")
        if not responder_id:
            logger.warning("Skipping responder record with no 'id' field.")
            continue
        collection.update_one({"id": responder_id}, {"$set": record}, upsert=True)
        count += 1
    return count


def migrate_analysis_jobs(db) -> int:
    results_dir = BACKEND_ROOT / "storage" / "results"
    records = _load_json_files(results_dir)
    collection = db["analysis_jobs"]
    count = 0
    for record in records:
        job_id = record.get("job_id")
        if not job_id:
            logger.warning("Skipping analysis job record with no 'job_id' field.")
            continue
        collection.update_one({"job_id": job_id}, {"$set": record}, upsert=True)
        count += 1
    return count


def main() -> int:
    settings = get_settings()
    if not settings.MONGODB_URI:
        logger.error("MONGODB_URI is not set. Set it in the environment or .env before running this script.")
        return 1

    db = get_database()
    if not ping(db):
        logger.error("Could not reach MongoDB. Check MONGODB_URI and network connectivity before running this script.")
        return 1

    logger.info("Connected to MongoDB database '%s'. Starting migration...", settings.MONGODB_DATABASE)

    responder_count = migrate_responders(db)
    job_count = migrate_analysis_jobs(db)

    logger.info("Migrated %d responder(s) and %d analysis job(s).", responder_count, job_count)
    logger.info(
        "Note: storage/sms_gateway_config.json was NOT migrated (secrets stay file-backed by design)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
