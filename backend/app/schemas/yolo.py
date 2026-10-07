"""Pydantic schemas for the YOLO26 supporting-vision-layer API.

Mirrors the shape and conventions of app/schemas/analysis.py: an explicit
status enum, a flat top-level result model, and small nested models for
grouped fields -- designed so the frontend can consume clean JSON without
knowing anything about Ultralytics internals.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class YoloJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    frame_index: int
    timestamp_seconds: float
    track_id: int | None = None


class ConfidenceStats(BaseModel):
    min: float
    max: float
    mean: float


class Track(BaseModel):
    track_id: int
    class_name: str
    detection_count: int
    confidence: ConfidenceStats
    first_seen_seconds: float
    last_seen_seconds: float
    duration_seconds: float
    current_position: tuple[float, float]
    trajectory: list[tuple[float, float]]
    movement_direction: tuple[float, float] | None = None


class Zone(BaseModel):
    id: str
    name: str
    polygon: list[tuple[float, float]]


class Line(BaseModel):
    id: str
    name: str
    points: tuple[tuple[float, float], tuple[float, float]]


class ZoneEvent(BaseModel):
    zone_id: str
    track_id: int | None
    class_name: str
    frame_index: int
    timestamp_seconds: float


class LineCrossingEvent(BaseModel):
    line_id: str
    track_id: int
    class_name: str
    frame_index: int
    timestamp_seconds: float


class YoloModelInfo(BaseModel):
    name: str = "YOLO26-S"
    task: str = "detect"
    device: str
    input_size: int
    confidence_threshold: float
    iou_threshold: float


class VideoInfo(BaseModel):
    filename: str
    duration_seconds: float
    fps: float
    width: int
    height: int
    frame_count: int


class ObjectCounts(BaseModel):
    persons: int = 0
    vehicles: int = 0
    by_class: dict[str, int] = Field(default_factory=dict)


class YoloSummary(BaseModel):
    unique_tracks: int = 0
    max_persons: int = 0
    max_vehicles: int = 0
    object_counts: ObjectCounts = Field(default_factory=ObjectCounts)


class PerformanceInfo(BaseModel):
    processing_time_seconds: float
    frames_processed: int
    inference_fps: float
    average_latency_ms: float


class YoloJobResult(BaseModel):
    job_id: str
    status: YoloJobStatus
    mode: str  # "detect" | "track"

    started_at: datetime | None = None
    completed_at: datetime | None = None

    processed_frames: int | None = None
    total_frames: int | None = None
    progress: float | None = None

    video: VideoInfo | None = None
    model: YoloModelInfo | None = None
    summary: YoloSummary | None = None

    detections: list[Detection] = Field(default_factory=list)
    tracks: list[Track] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    line_crossings: list[LineCrossingEvent] = Field(default_factory=list)
    zone_events: list[ZoneEvent] = Field(default_factory=list)

    performance: PerformanceInfo | None = None

    error: str | None = None
