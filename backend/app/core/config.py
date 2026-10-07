"""
Application configuration.

A plain dataclass rather than pydantic-settings: this keeps config dependency-free
and transparent, and all paths are derived from BACKEND_ROOT so nothing here is
hardcoded to a particular machine or install location.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# backend/app/core/config.py -> parents[0]=core, [1]=app, [2]=backend
BACKEND_ROOT = Path(__file__).resolve().parents[2]


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
