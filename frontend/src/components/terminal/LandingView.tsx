import { useRef } from "react";
import type { ActiveSource, EngineType, UploadedSource } from "./types";
import { Icons } from "./icons";

/** First-view landing screen. Preserves the approved layout; the "launch"
 * actions are real — entering the camera matrix (which will show honest
 * empty slots until a real camera source exists) or uploading a real
 * video file directly into a single-camera session. */
export function LandingView({
  cameraCount,
  onEnterMatrix,
  onSourceUploaded,
}: {
  cameraCount: number;
  onEnterMatrix: () => void;
  onSourceUploaded: (source: UploadedSource) => void;
}) {
  const anomalyInputRef = useRef<HTMLInputElement>(null);
  const yoloInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File | undefined, engineType: EngineType) => {
    if (!file) return;
    const source: ActiveSource & { kind: "uploaded" } = {
      kind: "uploaded",
      id: `upload-${Date.now()}`,
      file,
      objectUrl: URL.createObjectURL(file),
      engineType,
    };
    onSourceUploaded(source);
  };

  return (
    <div className="flex-1 flex items-center justify-center p-6 overflow-auto">
      <div className="max-w-3xl w-full flex flex-col items-center text-center gap-6">
        <div className="w-16 h-16 rounded-sm bg-accent/10 border border-accent/30 flex items-center justify-center text-accent">
          <Icons.Shield className="w-8 h-8" />
        </div>

        <div>
          <h1 className="text-2xl font-bold font-mono tracking-wide text-white mb-2">SENTINEL-X TACTICAL TERMINAL</h1>
          <p className="text-sm text-text-secondary max-w-lg mx-auto">
            Real-time video intelligence: I3D + Stage 1/2 anomaly detection, YOLO26 object detection &amp; tracking.
            Upload a video to begin, or open the camera matrix.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
          <input
            ref={anomalyInputRef}
            type="file"
            accept="video/*"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0], "anomaly")}
          />
          <button
            onClick={() => anomalyInputRef.current?.click()}
            className="flex flex-col items-center gap-2 p-5 bg-surface-1 border border-border hover:border-accent/50 rounded-sm transition-colors group"
          >
            <Icons.AlertTriangle className="w-6 h-6 text-accent group-hover:scale-110 transition-transform" />
            <div className="font-mono text-xs font-semibold text-white">ANOMALY ANALYSIS</div>
            <div className="text-[11px] text-text-tertiary">Upload video → I3D / Stage 1 / Stage 2</div>
          </button>

          <input
            ref={yoloInputRef}
            type="file"
            accept="video/*"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0], "vision_yolo")}
          />
          <button
            onClick={() => yoloInputRef.current?.click()}
            className="flex flex-col items-center gap-2 p-5 bg-surface-1 border border-border hover:border-accent/50 rounded-sm transition-colors group"
          >
            <Icons.Zap className="w-6 h-6 text-accent group-hover:scale-110 transition-transform" />
            <div className="font-mono text-xs font-semibold text-white">VISION / YOLO26</div>
            <div className="text-[11px] text-text-tertiary">Upload video → detection &amp; tracking</div>
          </button>
        </div>

        <button
          onClick={onEnterMatrix}
          className="flex items-center gap-2 px-4 py-2 text-xs font-mono text-text-secondary hover:text-white border border-border hover:border-border-strong rounded-sm transition-colors"
        >
          <Icons.Grid className="w-3.5 h-3.5" />
          OPEN CAMERA MATRIX ({cameraCount})
          <Icons.ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
