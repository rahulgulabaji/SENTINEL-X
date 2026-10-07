/**
 * Mirrors backend/app/schemas/yolo.py exactly. Field names and optionality
 * match the Pydantic models field-for-field — no invented fields.
 */

export type YoloStatus = "queued" | "processing" | "completed" | "failed";
export type YoloMode = "detect" | "track";

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Detection {
  class_id: number;
  class_name: string;
  confidence: number;
  bbox: BoundingBox;
  frame_index: number;
  timestamp_seconds: number;
  track_id: number | null;
}

export interface ConfidenceStats {
  min: number;
  max: number;
  mean: number;
}

export interface Track {
  track_id: number;
  class_name: string;
  detection_count: number;
  confidence: ConfidenceStats;
  first_seen_seconds: number;
  last_seen_seconds: number;
  duration_seconds: number;
  current_position: [number, number];
  trajectory: [number, number][];
  movement_direction: [number, number] | null;
}

export interface Zone {
  id: string;
  name: string;
  polygon: [number, number][];
}

export interface LineDef {
  id: string;
  name: string;
  points: [[number, number], [number, number]];
}

export interface ZoneEvent {
  zone_id: string;
  track_id: number | null;
  class_name: string;
  frame_index: number;
  timestamp_seconds: number;
}

export interface LineCrossingEvent {
  line_id: string;
  track_id: number;
  class_name: string;
  frame_index: number;
  timestamp_seconds: number;
}

export interface YoloModelInfo {
  name: string;
  task: string;
  device: string;
  input_size: number;
  confidence_threshold: number;
  iou_threshold: number;
}

export interface VideoInfo {
  filename: string;
  duration_seconds: number;
  fps: number;
  width: number;
  height: number;
  frame_count: number;
}

export interface ObjectCounts {
  persons: number;
  vehicles: number;
  by_class: Record<string, number>;
}

export interface YoloSummary {
  unique_tracks: number;
  max_persons: number;
  max_vehicles: number;
  object_counts: ObjectCounts;
}

export interface PerformanceInfo {
  processing_time_seconds: number;
  frames_processed: number;
  inference_fps: number;
  average_latency_ms: number;
}

export interface YoloJobResult {
  job_id: string;
  status: YoloStatus;
  mode: YoloMode;

  started_at: string | null;
  completed_at: string | null;

  processed_frames: number | null;
  total_frames: number | null;
  progress: number | null;

  video: VideoInfo | null;
  model: YoloModelInfo | null;
  summary: YoloSummary | null;

  detections: Detection[];
  tracks: Track[];
  zones: Zone[];
  line_crossings: LineCrossingEvent[];
  zone_events: ZoneEvent[];

  performance: PerformanceInfo | null;

  error: string | null;
}

export interface SubmitYoloJobResponse {
  job_id: string;
  status: YoloStatus;
}

/** GET /api/v1/yolo/model — full model info response (not nested in a job). */
export interface YoloModelInfoResponse {
  name: string;
  task: string;
  device: string;
  input_size: number;
  confidence_threshold: number;
  iou_threshold: number;
  loaded: boolean;
  num_classes: number;
  available_classes: string[];
  operational_classes: Record<string, string[]>;
}
