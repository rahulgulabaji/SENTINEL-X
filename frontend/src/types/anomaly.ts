/**
 * Mirrors backend/app/schemas/analysis.py exactly. Field names and
 * optionality match the Pydantic models field-for-field — no invented
 * fields, no renamed fields.
 */

export type AnomalyStatus = "queued" | "processing" | "completed" | "failed";

export interface ActionCandidate {
  class_name: string;
  probability: number;
}

export interface AnomalyModelInfo {
  stage1_name: string;
  stage2_name: string;
  i3d_backbone: string;
}

/**
 * Real per-window attention weights from the existing whole-video
 * attention-pooling modules, mapped to real source-video timestamps.
 *
 * NOT a per-window classification: stage1_attention / stage2_attention
 * describe how much this window's embedding contributed to the single
 * whole-video result, not an independent anomaly/action verdict for this
 * window alone. stage2 fields are null whenever stage2 did not run
 * (video judged not anomalous).
 */
export interface TemporalWindowEvidence {
  window_index: number;
  start_time_seconds: number;
  end_time_seconds: number;
  stage1_attention: number;
  stage1_attention_normalized: number;
  stage2_attention: number | null;
  stage2_attention_normalized: number | null;
}

export interface TemporalEvidence {
  available: boolean;
  window_duration_seconds: number;
  windows: TemporalWindowEvidence[];
}

export interface AnalysisResult {
  job_id: string;
  status: AnomalyStatus;
  filename: string;

  started_at: string | null;
  completed_at: string | null;
  processing_time_seconds: number | null;

  anomaly_detected: boolean | null;
  anomaly_probability: number | null;

  likely_action: string | null;
  action_confidence: number | null;
  action_candidates: ActionCandidate[];

  model_info: AnomalyModelInfo;

  temporal_evidence: TemporalEvidence;

  error: string | null;
}

export interface SubmitAnalysisResponse {
  job_id: string;
  status: AnomalyStatus;
}
