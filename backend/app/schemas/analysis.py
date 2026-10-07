"""Pydantic schemas for the analysis API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionCandidate(BaseModel):
    class_name: str
    probability: float


class TemporalWindowEvidence(BaseModel):
    """Real per-window attention weights from the existing whole-video
    attention-pooling modules (GatedAttentionMIL / TemporalAttention),
    mapped to real source-video timestamps.

    NOT a per-window classification -- stage1_attention / stage2_attention
    describe how much this window's embedding contributed to the single
    whole-video result, not an independent anomaly/action verdict for this
    window alone. stage2 fields are null whenever stage2 did not run
    (video judged not anomalous).
    """

    window_index: int
    start_time_seconds: float
    end_time_seconds: float
    stage1_attention: float
    stage1_attention_normalized: float
    stage2_attention: float | None = None
    stage2_attention_normalized: float | None = None


class TemporalEvidence(BaseModel):
    """Container for the per-window attention timeline. `available=False`
    means no temporal evidence could be produced for this result -- the
    frontend must show an honest empty state, never fabricate windows."""

    available: bool = False
    window_duration_seconds: float = 0.0
    windows: list[TemporalWindowEvidence] = Field(default_factory=list)


class ModelInfo(BaseModel):
    stage1_name: str = "final_binary_detector_v1"
    stage2_name: str = "action_classifier_v2"
    i3d_backbone: str = "rgb_imagenet"


class AnalysisResult(BaseModel):
    job_id: str
    status: AnalysisStatus
    filename: str

    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_time_seconds: float | None = None

    anomaly_detected: bool | None = None
    anomaly_probability: float | None = None

    likely_action: str | None = None
    action_confidence: float | None = None
    action_candidates: list[ActionCandidate] = Field(default_factory=list)

    model_info: ModelInfo = Field(default_factory=ModelInfo)

    temporal_evidence: TemporalEvidence = Field(default_factory=TemporalEvidence)

    error: str | None = None
