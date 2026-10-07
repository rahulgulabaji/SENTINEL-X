/**
 * Shared types for the Tactical Terminal UI. A "camera" here is either:
 *  - a real registry entry once `cameraApi.getCameras()` returns one
 *    (currently always empty, since no backend camera registry exists), or
 *  - a locally-selected uploaded video file, which is real (a real File
 *    the operator picked) but carries no fabricated location/coordinates/
 *    threat-level metadata, since the backend has no geo data for it.
 */
import type { CameraRecord } from "../../services/cameraApi";

export type EngineType = "anomaly" | "vision_yolo";

/** An uploaded local video, standing in for a camera slot. Real filename
 * and real size; no invented geographic/threat metadata. */
export interface UploadedSource {
  kind: "uploaded";
  id: string;
  file: File;
  objectUrl: string;
  engineType: EngineType;
}

/** A real camera from a future registry/Map API. */
export interface RegistrySource extends CameraRecord {
  kind: "registry";
}

export type ActiveSource = UploadedSource | RegistrySource;

export type TerminalView = "landing" | "grid" | "single" | "logs";
