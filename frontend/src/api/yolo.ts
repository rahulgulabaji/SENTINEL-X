import { apiGet, apiPostMultipart } from "./client";
import type {
  SubmitYoloJobResponse,
  YoloJobResult,
  YoloModelInfoResponse,
} from "../types/yolo";

export function submitYoloDetect(file: File): Promise<SubmitYoloJobResponse> {
  return apiPostMultipart<SubmitYoloJobResponse>("/api/v1/yolo/detect", file);
}

export function submitYoloTrack(file: File): Promise<SubmitYoloJobResponse> {
  return apiPostMultipart<SubmitYoloJobResponse>("/api/v1/yolo/track", file);
}

export function getYoloJobStatus(jobId: string): Promise<YoloJobResult> {
  return apiGet<YoloJobResult>(`/api/v1/yolo/jobs/${jobId}`);
}

export function getYoloJobResult(jobId: string): Promise<YoloJobResult> {
  return apiGet<YoloJobResult>(`/api/v1/yolo/jobs/${jobId}/result`);
}

export function getYoloModelInfo(): Promise<YoloModelInfoResponse> {
  return apiGet<YoloModelInfoResponse>("/api/v1/yolo/model");
}
