import { useEffect, useRef } from "react";
import type { Detection } from "../types/yolo";

interface DetectionOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  detections: Detection[];
  /** Native frame size the backend's bbox coordinates are expressed in —
   * required to scale real pixel coords onto the rendered video element. */
  videoWidth: number;
  videoHeight: number;
  mode: "detections" | "tracking";
}

const BOX_COLOR = "#4fa6d9";
const TRACK_COLOR = "#49a87a";

/** Canvas overlay drawing real backend bbox coordinates over the currently
 * visible video frame. Draws nothing when there are no real detections for
 * the current timestamp — never a placeholder or fabricated box. */
export function DetectionOverlay({
  videoRef,
  detections,
  videoWidth,
  videoHeight,
  mode,
}: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video || !videoWidth || !videoHeight) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = () => {
      const rect = video.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const scaleX = rect.width / videoWidth;
      const scaleY = rect.height / videoHeight;
      const currentTime = video.currentTime;

      // Nearest-frame match within one real backend-observed timestamp
      // window. If nothing matches, nothing is drawn — no fabricated boxes.
      const visible = detections.filter((d) => Math.abs(d.timestamp_seconds - currentTime) < 0.12);

      for (const d of visible) {
        if (mode === "tracking" && d.track_id == null) continue;
        const color = mode === "tracking" ? TRACK_COLOR : BOX_COLOR;
        const x = d.bbox.x1 * scaleX;
        const y = d.bbox.y1 * scaleY;
        const w = (d.bbox.x2 - d.bbox.x1) * scaleX;
        const h = (d.bbox.y2 - d.bbox.y1) * scaleY;

        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(x, y, w, h);

        const label =
          mode === "tracking" && d.track_id != null
            ? `#${d.track_id} ${d.class_name}`
            : `${d.class_name} ${(d.confidence * 100).toFixed(0)}%`;

        ctx.font = "11px 'IBM Plex Mono', monospace";
        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = color;
        ctx.fillRect(x, Math.max(0, y - 15), textWidth + 8, 15);
        ctx.fillStyle = "#0b0f13";
        ctx.fillText(label, x + 4, Math.max(11, y - 4));
      }
    };

    // Driven by the video's own timeline events rather than requestAnimationFrame:
    // rAF is throttled or fully suspended in backgrounded/hidden tabs (confirmed via
    // document.hidden in this environment), which silently starved the redraw loop.
    // timeupdate/seeked/loadedmetadata cover real playback and scrubbing; a low-rate
    // interval fallback keeps the overlay correct even while visibilitychange holds
    // rAF back, and resize keeps the canvas sized to the rendered video element.
    draw();
    video.addEventListener("timeupdate", draw);
    video.addEventListener("seeked", draw);
    video.addEventListener("loadedmetadata", draw);
    video.addEventListener("play", draw);
    window.addEventListener("resize", draw);
    const intervalId = window.setInterval(draw, 100);

    return () => {
      video.removeEventListener("timeupdate", draw);
      video.removeEventListener("seeked", draw);
      video.removeEventListener("loadedmetadata", draw);
      video.removeEventListener("play", draw);
      window.removeEventListener("resize", draw);
      window.clearInterval(intervalId);
    };
  }, [detections, videoWidth, videoHeight, mode, videoRef]);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute left-0 top-0"
      aria-hidden="true"
    />
  );
}
