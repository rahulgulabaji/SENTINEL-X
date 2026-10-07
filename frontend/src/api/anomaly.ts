import { apiGet, apiPostMultipart } from "./client";
import type { AnalysisResult, SubmitAnalysisResponse } from "../types/anomaly";

export function submitAnalysis(file: File): Promise<SubmitAnalysisResponse> {
  return apiPostMultipart<SubmitAnalysisResponse>("/api/v1/analysis", file);
}

export function getAnalysisStatus(jobId: string): Promise<AnalysisResult> {
  return apiGet<AnalysisResult>(`/api/v1/analysis/${jobId}`);
}

export function getAnalysisResult(jobId: string): Promise<AnalysisResult> {
  return apiGet<AnalysisResult>(`/api/v1/analysis/${jobId}/result`);
}
