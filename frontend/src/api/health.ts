import { apiGet } from "./client";

export interface AppHealth {
  status: string;
  inference_ready: boolean;
}

export interface YoloHealth {
  status: string;
  model_loaded: boolean;
  device: string;
}

export function getAppHealth(): Promise<AppHealth> {
  return apiGet<AppHealth>("/api/health");
}

export function getYoloHealth(): Promise<YoloHealth> {
  return apiGet<YoloHealth>("/api/v1/yolo/health");
}
