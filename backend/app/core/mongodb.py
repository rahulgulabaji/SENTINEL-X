"""MongoDB Atlas connection module -- the one place a `MongoClient` is ever
constructed in this codebase.

Same lazy-singleton-with-test-escape-hatch convention already used by
app/core/responder_store.py's get_responder_store() and
app/core/sms_config_store.py's get_sms_config_store(): a module-level
`_client`/`_db` pair, built once on first access, with a `client=`/`db=`
override parameter so tests can point this module at a fresh (mongomock)
instance without touching the real singleton.

Construction is deliberately cheap and never raises, even if Atlas is
completely unreachable -- PyMongo's MongoClient does not perform a network
round-trip in its constructor; it connects lazily on first actual operation
(https://pymongo.readthedocs.io/ -- "MongoClient is a non-blocking,
lazily-connecting client" is the documented default behavior; nothing here
changes that). That is intentional and relied upon: the FastAPI app must
start cleanly even when MONGODB_URI is unset or Atlas is down, but any
*operation* against a repository must surface a truthful connectivity error
rather than silently doing nothing or falling back to fake data. `ping()`
below is the one function that actually talks to the server and is the
correct place to find out whether the database is really reachable.

Never logs or returns the configured MONGODB_URI anywhere -- settings.
MONGODB_URI is read once by get_mongo_client() to construct the client and
is never written to a log line, exception message, or API response in this
module.
"""

from __future__ import annotations

import logging

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

# Fail fast on an unreachable/misconfigured server rather than hanging a
# request indefinitely -- 5s is generous enough for a real Atlas round trip
# over a normal connection, short enough that a health check or a repository
# call returns a truthful "disconnected" promptly instead of blocking.
DEFAULT_SERVER_SELECTION_TIMEOUT_MS = 5000

_client: MongoClient | None = None
_db: Database | None = None


def get_mongo_client(settings=None) -> MongoClient:
    """Process-wide MongoClient singleton. Constructing a MongoClient never
    raises and never blocks on a server round-trip (PyMongo connects lazily)
    -- so calling this is always safe during startup even if Atlas is
    unreachable or MONGODB_URI is unset (an empty URI is still accepted by
    MongoClient's constructor; only an actual operation against it will then
    fail, truthfully, via ServerSelectionTimeoutError).

    Passing `settings` explicitly builds a fresh, uncached client (used by
    tests to point this module at mongomock without touching the real
    singleton) -- same convention as get_responder_store(settings=...).
    """
    global _client
    if settings is not None:
        return MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=DEFAULT_SERVER_SELECTION_TIMEOUT_MS,
        )
    if _client is None:
        from app.core.config import get_settings

        resolved = get_settings()
        _client = MongoClient(
            resolved.MONGODB_URI,
            serverSelectionTimeoutMS=DEFAULT_SERVER_SELECTION_TIMEOUT_MS,
        )
    return _client


def get_database(settings=None) -> Database:
    """Returns the configured database (MONGODB_DATABASE, default
    "sentinel_x") on the shared client. Does not touch the network --
    selecting a database by name is a local, client-side operation in
    PyMongo."""
    global _db
    if settings is not None:
        from app.core.config import get_settings as _get_settings

        resolved = settings
        client = get_mongo_client(settings=resolved)
        return client[resolved.MONGODB_DATABASE]
    if _db is None:
        from app.core.config import get_settings

        resolved = get_settings()
        _db = get_mongo_client()[resolved.MONGODB_DATABASE]
    return _db


def ping(db: Database | None = None) -> bool:
    """The one function that actually talks to the server. Returns True only
    if the database genuinely responded; catches every PyMongoError (timeout,
    auth failure, DNS failure, network error) and returns False rather than
    raising -- callers (the health endpoint, repositories deciding whether to
    report a truthful "unavailable" error) must never crash because Atlas is
    temporarily down."""
    target = db if db is not None else get_database()
    try:
        target.command("ping")
        return True
    except PyMongoError:
        logger.warning("MongoDB ping failed -- reporting disconnected.", exc_info=True)
        return False


def ensure_indexes(db: Database | None = None) -> None:
    """Creates every index this application needs, idempotently --
    create_index() is itself a safe no-op if an equivalent index already
    exists, so this can run on every startup without accumulating duplicate
    indexes. Deliberately non-fatal on failure (caught and logged by the
    caller in app/main.py's lifespan, matching the existing YOLO26
    load-failure pattern) -- an index that can't be created yet because
    Atlas is temporarily unreachable must not block the app from starting."""
    target = db if db is not None else get_database()

    target["responders"].create_index([("id", ASCENDING)], unique=True, name="responders_id_unique")
    # Sparse: legacy/PIN-only responders have no username at all, and a
    # sparse unique index only enforces uniqueness among documents that
    # actually have the field -- multiple missing-username documents don't
    # collide with each other.
    target["responders"].create_index(
        [("username", ASCENDING)], unique=True, sparse=True, name="responders_username_unique"
    )

    target["responder_locations"].create_index(
        [("responder_id", ASCENDING), ("timestamp", ASCENDING)], name="responder_locations_responder_timestamp"
    )
    # 2dsphere on the GeoJSON `location` field. Not currently queried by any
    # $near/$geoNear call -- nearby search stays Haversine-over-embedded-
    # lat/lng in app/core/geo.py, unchanged. This index exists only for
    # future-proofing and direct Atlas/Compass geospatial inspection.
    target["responder_locations"].create_index([("location", "2dsphere")], name="responder_locations_geo")

    target["analysis_jobs"].create_index([("job_id", ASCENDING)], unique=True, name="analysis_jobs_job_id_unique")
    # AnalysisResult has no `created_at` field -- `started_at` is the real
    # timestamp field or the "closest to created_at" for ordering purposes.
    target["analysis_jobs"].create_index([("started_at", ASCENDING)], name="analysis_jobs_started_at")
    target["analysis_jobs"].create_index([("status", ASCENDING)], name="analysis_jobs_status")

    target["incidents"].create_index([("incident_id", ASCENDING)], unique=True, name="incidents_incident_id_unique")
    target["incidents"].create_index([("created_at", ASCENDING)], name="incidents_created_at")
    target["incidents"].create_index([("status", ASCENDING)], name="incidents_status")

    target["dispatches"].create_index([("dispatch_id", ASCENDING)], unique=True, name="dispatches_dispatch_id_unique")
    target["dispatches"].create_index([("incident_id", ASCENDING)], name="dispatches_incident_id")
    target["dispatches"].create_index([("responder_id", ASCENDING)], name="dispatches_responder_id")
    target["dispatches"].create_index([("created_at", ASCENDING)], name="dispatches_created_at")

    # audit_logs: unique event_id for idempotent retry-safety (callers that
    # generate an id upfront and retry on a transient failure won't double-
    # insert), plus timestamp (list ordering/pagination) and event_type/actor
    # (the two fields a read API will most commonly filter on).
    target["audit_logs"].create_index([("event_id", ASCENDING)], unique=True, sparse=True, name="audit_logs_event_id_unique")
    target["audit_logs"].create_index([("timestamp", ASCENDING)], name="audit_logs_timestamp")
    target["audit_logs"].create_index([("event_type", ASCENDING)], name="audit_logs_event_type")
    target["audit_logs"].create_index([("actor", ASCENDING)], name="audit_logs_actor")
    target["audit_logs"].create_index([("correlation_id", ASCENDING)], sparse=True, name="audit_logs_correlation_id")

    # detection_events: job_id is the natural lookup key (one job fans out to
    # many detection-event documents, one per temporal-evidence window), plus
    # timestamp for ordering.
    target["detection_events"].create_index([("job_id", ASCENDING)], name="detection_events_job_id")
    target["detection_events"].create_index([("timestamp", ASCENDING)], name="detection_events_timestamp")

    # share_sessions: unique session_id for direct lookup (the token's `sid`
    # claim resolves straight to one document); invite_expires_at indexed to
    # support a future cleanup job that prunes long-dead pending invitations
    # (no such job exists yet -- this is forward-looking, same as the
    # responder_locations 2dsphere index above).
    target["share_sessions"].create_index([("session_id", ASCENDING)], unique=True, name="share_sessions_session_id_unique")
    target["share_sessions"].create_index([("invite_expires_at", ASCENDING)], name="share_sessions_invite_expires_at")


def close_mongo_client() -> None:
    """Closes the shared client cleanly and resets the module singletons --
    called from app/main.py's lifespan shutdown half. Safe to call even if
    the client was never constructed (e.g. app shut down before any Mongo
    operation ran)."""
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
