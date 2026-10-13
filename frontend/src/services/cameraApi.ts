/**
 * Camera registry service boundary.
 *
 * The real SENTINEL-X backend has no camera registry, no geolocation
 * concept, and no stream/RTSP integration (confirmed by direct inspection
 * of `backend/app/` — zero matches for camera/lat/lng anywhere server-side).
 * Camera identity and geographic placement are therefore not real data
 * today, and must never be fabricated to make the UI look populated.
 *
 * This module returns an empty list until a real camera source exists —
 * either a backend camera registry or the forthcoming Map API. The shape
 * below is what the UI consumes; swapping the body of `getCameras()` for a
 * real fetch later requires no call-site changes.
 */

export interface CameraRecord {
  id: string;
  title: string;
  location: string;
  resolution: string;
  /** Geographic coordinates — only ever present once a real source (Map
   * API / backend registry) supplies them. Never fabricated. */
  lat: number | null;
  lng: number | null;
  /** Which real backend engine this camera's video should be analyzed
   * with. Not a claim about the camera itself. */
  type: "anomaly" | "vision_yolo";
}

/**
 * Returns the list of real, backend/Map-API-known cameras. Currently
 * always empty — no real camera source is wired up yet. Deliberately
 * async so a future network-backed implementation is a drop-in swap.
 */
export async function getCameras(): Promise<CameraRecord[]> {
  return [];
}
