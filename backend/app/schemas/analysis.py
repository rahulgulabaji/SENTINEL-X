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

    # DIAGNOSTIC-ONLY passthrough of app.inference.final_demo_inference's
    # build_model_window_diagnostics() output. Deliberately untyped (list /
    # dict) rather than modeled with strict sub-schemas, since this is a
    # debugging aid, not part of the evidence/UI contract -- the frontend
    # timeline must keep using temporal_evidence, not these fields.
    model_window_diagnostics: list = Field(default_factory=list)
    model_detection_summary: dict | None = None

    error: str | None = None


class IncidentResponse(BaseModel):
    """A reviewable record auto-created when a job completes with
    anomaly_detected=True. Never implies dispatch/SMS -- see
    app/repositories/incident_repository.py's module docstring."""

    incident_id: str
    job_id: str
    status: str
    anomaly_probability: float | None = None
    likely_action: str | None = None
    action_confidence: float | None = None
    created_at: str
    updated_at: str


class IncidentUpdateStatusRequest(BaseModel):
    status: str = Field(..., description="New incident status, e.g. 'open', 'acknowledged', 'resolved'.")


class DetectionEventResponse(BaseModel):
    """One per temporal_evidence window on an anomaly-detected job -- a
    queryable projection, not a duplicate of the job record itself. See
    app/repositories/detection_event_repository.py's module docstring."""

    job_id: str
    window_index: int
    start_time_seconds: float
    end_time_seconds: float
    stage1_attention: float
    stage2_attention: float | None = None
    likely_action: str | None = None
    action_confidence: float | None = None
    anomaly_detected: bool
    created_at: str


class AuditLogEntry(BaseModel):
    event_id: str
    event_type: str
    actor: str
    module: str = ""
    resource_type: str = ""
    resource_id: str = ""
    outcome: str = "success"
    summary: str = ""
    correlation_id: str | None = None
    error_category: str | None = None
    details: dict = Field(default_factory=dict)
    timestamp: str


class AnalysisJobSummary(BaseModel):
    """Lightweight list-view projection of AnalysisResult -- the fields a
    history table needs, without the full temporal_evidence/diagnostics
    payload. Used only by GET /v1/analysis (list); GET /{job_id}/result
    still returns the full AnalysisResult, unchanged."""

    job_id: str
    status: AnalysisStatus
    filename: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    anomaly_detected: bool | None = None
    anomaly_probability: float | None = None
    likely_action: str | None = None
    action_confidence: float | None = None
    error: str | None = None
