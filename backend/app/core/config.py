"""
Application configuration.

A plain dataclass rather than pydantic-settings: this keeps config dependency-free
and transparent, and all paths are derived from BACKEND_ROOT so nothing here is
hardcoded to a particular machine or install location.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# backend/app/core/config.py -> parents[0]=core, [1]=app, [2]=backend
BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Pre-existing gap, not specific to any one feature: nothing in this codebase
# previously called load_dotenv(), so backend/.env was silently ignored and
# only real exported shell env vars ever took effect (.env.example was
# effectively aspirational documentation only). python-dotenv was already an
# installed dependency; this just wires it up. override=False: real
# exported env vars still win over .env, same precedence as before this
# line existed for anything already being set that way.
load_dotenv(BACKEND_ROOT / ".env", override=False)


def _split_origins(raw: str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    APP_NAME: str = "SENTINEL-X API"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    BACKEND_ROOT: Path = BACKEND_ROOT
    MODELS_DIR: Path = BACKEND_ROOT / "models"
    STORAGE_DIR: Path = BACKEND_ROOT / "storage"
    UPLOAD_DIR: Path = BACKEND_ROOT / "storage" / "uploads"
    RESULTS_DIR: Path = BACKEND_ROOT / "storage" / "results"
    EVIDENCE_DIR: Path = BACKEND_ROOT / "storage" / "evidence"

    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
    ALLOWED_VIDEO_EXTENSIONS: tuple[str, ...] = (".mp4", ".avi", ".mov", ".mkv")

    # --- Local demo mode (explicit opt-in, OFF by default) ----------------
    # When true, app/api/routes/analysis.py uses the original
    # InMemoryJobRepository (storage/results/*.json) for analysis-job
    # tracking instead of MongoDB -- for running the real inference pipeline
    # on a machine with no reachable MongoDB Atlas cluster (e.g. a live
    # demo/presentation). This affects ONLY analysis-job persistence; the
    # inference pipeline itself (I3D/Stage1/Stage2/YOLO26) is identical
    # either way, and no result is ever fabricated.
    #
    # Does not touch responders/dispatch/incidents/audit-log, which remain
    # MongoDB-only and will still correctly report 503 if Atlas is
    # unreachable -- this flag never mixes Mongo and JSON records for the
    # same entity type. Default False: normal operation is unaffected and
    # still requires a real MongoDB connection for analysis jobs, exactly as
    # before this flag existed.
    LOCAL_DEMO_MODE: bool = os.getenv("LOCAL_DEMO_MODE", "false").strip().lower() == "true"

    CORS_ALLOWED_ORIGINS: list[str] = field(
        default_factory=lambda: _split_origins(
            os.getenv(
                "CORS_ALLOWED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            )
        )
    )

    # --- YOLO26 supporting vision layer -----------------------------------
    # A separate, additive CV layer (object detection/tracking) alongside the
    # authoritative I3D/Stage1/Stage2 anomaly pipeline above. See
    # app/inference/yolo26_service.py. All overridable via env vars, same
    # convention as the rest of this file.
    YOLO_MODEL_NAME: str = os.getenv("YOLO_MODEL_NAME", "yolo26s.pt")
    YOLO_WEIGHTS_DIR: Path = BACKEND_ROOT / "models" / "yolo26"
    YOLO_INPUT_SIZE: int = int(os.getenv("YOLO_INPUT_SIZE", "640"))
    YOLO_CONFIDENCE_THRESHOLD: float = float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.25"))
    YOLO_IOU_THRESHOLD: float = float(os.getenv("YOLO_IOU_THRESHOLD", "0.45"))
    YOLO_DEVICE: str = os.getenv("YOLO_DEVICE", "auto")  # "auto" | "cuda" | "cpu"
    YOLO_FRAME_STRIDE: int = int(os.getenv("YOLO_FRAME_STRIDE", "1"))
    YOLO_UPLOAD_DIR: Path = BACKEND_ROOT / "storage" / "uploads" / "yolo"
    YOLO_RESULTS_DIR: Path = BACKEND_ROOT / "storage" / "results" / "yolo"
    YOLO_EVIDENCE_DIR: Path = BACKEND_ROOT / "storage" / "evidence" / "yolo"

    # --- SMS Gateway (Android phone acting as a physical SMS modem) -------
    # Isolated notification feature -- see app/services/sms_gateway.py and
    # app/api/routes/notifications.py. NOT wired into the analysis pipeline.
    # Disabled by default; every value is env-var backed, nothing hardcoded.
    SMS_GATEWAY_ENABLED: bool = os.getenv("SMS_GATEWAY_ENABLED", "false").strip().lower() == "true"
    SMS_GATEWAY_URL: str = os.getenv("SMS_GATEWAY_URL", "")
    SMS_GATEWAY_USERNAME: str = os.getenv("SMS_GATEWAY_USERNAME", "")
    SMS_GATEWAY_PASSWORD: str = os.getenv("SMS_GATEWAY_PASSWORD", "")

    # --- Grok / xAI incident summarization ---------------------------------
    # Isolated AI-summary feature -- see app/services/grok_summary_service.py
    # and the GET /v1/incidents/latest/summary/ai route. NOT wired into the
    # analysis pipeline, incident creation, or dispatch. Disabled by default:
    # until GROK_ENABLED=true AND a real XAI_API_KEY is set, the service only
    # ever returns its deterministic, non-fabricated fallback summary -- it
    # never silently calls out to a real external API by default. The key is
    # never logged or returned in any API response.
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    GROK_MODEL: str = os.getenv("GROK_MODEL", "grok-4.7")
    GROK_ENABLED: bool = os.getenv("GROK_ENABLED", "false").strip().lower() == "true"
    GROK_TIMEOUT_SECONDS: float = float(os.getenv("GROK_TIMEOUT_SECONDS", "10"))

    # Permanent persistence layer (MongoDB Atlas). Never logged, never
    # returned in any API response -- see app/core/mongodb.py. Empty string
    # default is intentional: constructing a MongoClient with an empty URI
    # never raises (PyMongo connects lazily), so the app still starts
    # cleanly when this is unset; only an actual database operation then
    # fails, truthfully, rather than silently.
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "sentinel_x")

    # --- Voluntary live location sharing (share-link feature) -------------
    # HMAC signing key for share tokens -- see app/core/share_tokens.py.
    # Falls back to a random key generated at import time if unset, so dev
    # still works, but a logged warning makes clear tokens won't survive a
    # backend restart in that case (every previously-issued link becomes
    # unverifiable). Never logged itself.
    SHARE_SECRET_KEY: str = os.getenv("SENTINEL_SHARE_SECRET_KEY", "")
    # Two independent clocks, deliberately not the same value -- see the
    # share-link plan: SHARE_INVITE_TTL_SECONDS bounds how long the link in
    # the SMS is valid for first use (/start only); SHARE_SESSION_MAX_DURATION_SECONDS
    # bounds how long an already-started tracking session may keep posting
    # updates (/location, /status only). A responder who opens the link just
    # before the invite expires still gets the full active-tracking window.
    SHARE_INVITE_TTL_SECONDS: int = int(os.getenv("SHARE_INVITE_TTL_SECONDS", "900"))
    SHARE_SESSION_MAX_DURATION_SECONDS: int = int(
        os.getenv("SHARE_SESSION_MAX_DURATION_SECONDS", "7200")
    )
    # Externally-reachable base URL (e.g. the ngrok HTTPS URL during testing)
    # used only to build the share link text included in the dispatch SMS --
    # never used for any trust/auth decision. Empty by default; dispatch.py
    # falls back to a clear placeholder if this isn't set rather than
    # silently emitting a broken link.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def get_settings() -> Settings:
    """Returns the process-wide Settings instance.

    A function (rather than a bare module-level constant) so routes/services
    depend on `Depends(get_settings)` and tests can override it later without
    monkeypatching a module attribute.
    """
    return _settings


_settings = Settings()
