/**
 * Shared HTTP client for the SENTINEL-X backend. Centralizes base URL
 * resolution, JSON/multipart request handling, and error normalization so
 * no component calls fetch() directly.
 */

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

/** Raised for any non-2xx response, or a response the backend couldn't be
 * reached to produce at all. Carries enough detail for the UI to show a
 * real, specific error rather than a generic failure message. */
export class ApiError extends Error {
  status: number | null;
  detail: string | null;

  constructor(message: string, status: number | null = null, detail: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    try {
      return await response.text();
    } catch {
      return null;
    }
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new ApiError(
      detail ?? `Request failed with status ${response.status}`,
      response.status,
      detail,
    );
  }
  // 204 / empty body safety
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

function networkErrorToApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  return new ApiError(
    "Backend unavailable. Start SENTINEL-X backend on port 8000.",
    null,
    err instanceof Error ? err.message : String(err),
  );
}

export async function apiGet<T>(path: string): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { method: "GET" });
    return await handleResponse<T>(response);
  } catch (err) {
    throw networkErrorToApiError(err);
  }
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return await handleResponse<T>(response);
  } catch (err) {
    throw networkErrorToApiError(err);
  }
}

/** Multipart upload — used for all video submission endpoints. `extraFields`
 * are appended as additional form fields (e.g. YOLO's optional zones/lines
 * JSON strings). */
export async function apiPostMultipart<T>(
  path: string,
  file: File,
  extraFields?: Record<string, string>,
): Promise<T> {
  try {
    const formData = new FormData();
    formData.append("file", file);
    if (extraFields) {
      for (const [key, value] of Object.entries(extraFields)) {
        formData.append(key, value);
      }
    }
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      body: formData,
    });
    return await handleResponse<T>(response);
  } catch (err) {
    throw networkErrorToApiError(err);
  }
}
