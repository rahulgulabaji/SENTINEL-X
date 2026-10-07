"""
One-off benchmark script for the YOLO26 supporting vision layer. Not imported
by the app -- run manually (`python scripts/benchmark_yolo.py` from
`backend/`) whenever hardware, model, or config changes and the numbers in
docs/YOLO26.md need refreshing.

Measures, on the actual installed GPU/CPU:
- cold-start latency (model load + first-inference overhead), reported
  separately and never folded into steady-state FPS
- steady-state detect FPS and per-frame latency (plain detection)
- steady-state track FPS and per-frame latency (ByteTrack via model.track)
- peak VRAM usage via torch.cuda.max_memory_allocated()

Only loads yolo26n.pt for comparison if the S-model's measured FPS is below
a conservative usability threshold -- not run speculatively (see plan).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch

from app.inference.yolo26_service import YOLO26Service

TEST_VIDEO = Path(__file__).resolve().parent.parent.parent / "test_videos" / "Abuse" / "Abuse021_x264.mp4"

# Below this steady-state FPS on the detect pass, additionally measure
# yolo26n.pt for a real comparison rather than silently switching models.
MIN_ACCEPTABLE_FPS = 8.0


def _reset_vram_stats() -> None:
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()


def _vram_mb() -> tuple[float, float]:
    if not torch.cuda.is_available():
        return 0.0, 0.0
    current = torch.cuda.memory_allocated() / (1024 * 1024)
    peak = torch.cuda.max_memory_allocated() / (1024 * 1024)
    return current, peak


def benchmark_model(model_name: str) -> dict:
    print(f"\n{'=' * 70}")
    print(f"Benchmarking {model_name}")
    print(f"{'=' * 70}")

    _reset_vram_stats()

    service = YOLO26Service(
        model_name=model_name,
        weights_dir=Path(__file__).resolve().parent.parent / "models" / "yolo26",
        input_size=640,
        confidence_threshold=0.25,
        iou_threshold=0.45,
        device_setting="auto",
        frame_stride=1,
    )

    t_cold_start = time.time()
    service.initialize()
    cold_load_elapsed = time.time() - t_cold_start

    info = service.get_model_info()
    print(f"Device: {info['device']}")
    print(f"Input size: {info['input_size']}")
    print(f"Confidence threshold: {info['confidence_threshold']}")
    print(f"Model load time (cold start, includes any download): {cold_load_elapsed:.2f}s")

    import cv2

    cap = cv2.VideoCapture(str(TEST_VIDEO))
    ok, first_frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Could not read a frame from {TEST_VIDEO}")

    # First-inference latency is reported separately -- warming up CUDA
    # kernels/cuDNN algo selection on the very first call is a real, distinct
    # cost from steady-state throughput, and conflating the two would
    # misreport steady-state FPS.
    t_warmup = time.time()
    service.detect_frame(first_frame, frame_index=0, timestamp_seconds=0.0)
    warmup_elapsed = time.time() - t_warmup
    print(f"First-inference (warmup) latency: {warmup_elapsed * 1000:.1f} ms")

    # --- steady-state detect benchmark ---
    _reset_vram_stats()
    t0 = time.time()
    detect_result = service.detect_video(str(TEST_VIDEO))
    detect_elapsed = time.time() - t0
    detect_fps = detect_result.frames_processed / detect_elapsed if detect_elapsed > 0 else 0.0
    detect_latency_ms = (detect_elapsed / detect_result.frames_processed * 1000.0) if detect_result.frames_processed else 0.0
    _, detect_peak_vram = _vram_mb()

    print("\n--- detect_video() ---")
    print(f"Video: {TEST_VIDEO.name} ({detect_result.video.width}x{detect_result.video.height}, "
          f"{detect_result.video.frame_count} frames @ {detect_result.video.fps:.1f} fps, "
          f"{detect_result.video.duration_seconds:.1f}s)")
    print(f"Frames processed: {detect_result.frames_processed}")
    print(f"Total detections: {len(detect_result.detections)}")
    print(f"Total processing time: {detect_elapsed:.2f}s")
    print(f"Average inference latency: {detect_latency_ms:.2f} ms/frame")
    print(f"Steady-state inference FPS: {detect_fps:.2f}")
    if torch.cuda.is_available():
        print(f"Peak VRAM during detect: {detect_peak_vram:.1f} MB")

    # --- steady-state track benchmark ---
    _reset_vram_stats()
    t0 = time.time()
    track_result = service.track_video(str(TEST_VIDEO))
    track_elapsed = time.time() - t0
    track_fps = track_result.frames_processed / track_elapsed if track_elapsed > 0 else 0.0
    track_latency_ms = (track_elapsed / track_result.frames_processed * 1000.0) if track_result.frames_processed else 0.0
    _, track_peak_vram = _vram_mb()

    print("\n--- track_video() ---")
    print(f"Frames processed: {track_result.frames_processed}")
    print(f"Total detections: {len(track_result.detections)}")
    print(f"Unique tracks: {len(track_result.tracks)}")
    print(f"Total processing time: {track_elapsed:.2f}s")
    print(f"Average inference latency: {track_latency_ms:.2f} ms/frame")
    print(f"Steady-state inference FPS: {track_fps:.2f}")
    if torch.cuda.is_available():
        print(f"Peak VRAM during track: {track_peak_vram:.1f} MB")

    return {
        "model_name": model_name,
        "device": info["device"],
        "cold_load_elapsed": cold_load_elapsed,
        "warmup_latency_ms": warmup_elapsed * 1000,
        "detect_fps": detect_fps,
        "detect_latency_ms": detect_latency_ms,
        "detect_peak_vram_mb": detect_peak_vram,
        "track_fps": track_fps,
        "track_latency_ms": track_latency_ms,
        "track_peak_vram_mb": track_peak_vram,
        "frame_count": detect_result.video.frame_count,
        "video_resolution": f"{detect_result.video.width}x{detect_result.video.height}",
    }


def main() -> None:
    if not TEST_VIDEO.exists():
        print(f"ERROR: test video not found at {TEST_VIDEO}")
        sys.exit(1)

    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        total_vram = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
        print(f"Total VRAM: {total_vram:.0f} MB")

    results = [benchmark_model("yolo26s.pt")]

    if results[0]["detect_fps"] < MIN_ACCEPTABLE_FPS:
        print(
            f"\nyolo26s.pt steady-state detect FPS ({results[0]['detect_fps']:.2f}) is below "
            f"the {MIN_ACCEPTABLE_FPS} FPS usability threshold -- running yolo26n.pt for a "
            f"real comparison."
        )
        results.append(benchmark_model("yolo26n.pt"))
    else:
        print(
            f"\nyolo26s.pt steady-state detect FPS ({results[0]['detect_fps']:.2f}) is at or "
            f"above the {MIN_ACCEPTABLE_FPS} FPS threshold -- yolo26n.pt comparison not run."
        )

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    for r in results:
        print(
            f"{r['model_name']}: device={r['device']}, detect_fps={r['detect_fps']:.2f}, "
            f"track_fps={r['track_fps']:.2f}, detect_latency={r['detect_latency_ms']:.1f}ms, "
            f"peak_vram_detect={r['detect_peak_vram_mb']:.0f}MB, "
            f"peak_vram_track={r['track_peak_vram_mb']:.0f}MB, "
            f"cold_load={r['cold_load_elapsed']:.2f}s, warmup={r['warmup_latency_ms']:.1f}ms"
        )


if __name__ == "__main__":
    main()
