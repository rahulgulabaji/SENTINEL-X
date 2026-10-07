"""
yolo26_service.py

Supporting computer-vision layer for SENTINEL-X: real-time object detection
and multi-object tracking via the official Ultralytics YOLO26-S pretrained
model (COCO weights). This is strictly ADDITIVE to the authoritative
I3D -> Stage1 -> Stage2 anomaly pipeline in final_demo_inference.py -- it
never replaces it, never touches its checkpoints, and the two pipelines are
never merged into one model.

Mirrors the InferencePipeline pattern already established in
final_demo_inference.py: a module-level singleton, constructed empty (no
GPU/CPU memory touched at import time), with initialize() called once from
FastAPI's lifespan hook. A YOLO load failure must never crash the anomaly
pipeline's own loading -- callers are expected to wrap initialize() in its
own try/except (done in main.py) and check is_ready() before use.

Design notes:
- Model is loaded exactly once and reused for every request (never
  reconstructed per-frame or per-request).
- CUDA is used automatically when available ("auto" device setting);
  otherwise falls back to CPU cleanly, both reported honestly in
  get_model_info().
- Video processing streams frame-by-frame (OpenCV VideoCapture), never
  buffers an entire video's frames in memory -- only compact per-frame
  detection records are retained, not frame pixel data.
- Tracking uses Ultralytics' own built-in ByteTrack integration
  (model.track(..., tracker="bytetrack.yaml")) -- no custom tracker.
- A single process-wide threading.Lock serializes calls into the underlying
  model, since a single Ultralytics YOLO instance is not guaranteed safe
  under concurrent calls from multiple threads (FastAPI BackgroundTasks runs
  jobs in a thread pool). This is "thread-safe enough" for the current
  single-user/demo backend; a future worker-process migration would not
  need this lock at all (each worker would own its own model instance).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import cv2
import torch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Operationally-relevant COCO class groupings (Phase 1 scope). The model
# itself is never restricted to these classes -- full COCO-80 detection
# stays available internally (see get_model_info()["available_classes"])
# -- this is purely a display/aggregation convenience for SENTINEL-X.
# ---------------------------------------------------------------------------
PERSON_CLASSES = {"person"}
VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}


@dataclass
class RawDetection:
    """One detected object in one frame. Plain dataclass (not a Pydantic
    schema) to keep this module framework-agnostic, same convention as
    InferenceOutput in final_demo_inference.py."""

    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    frame_index: int
    timestamp_seconds: float
    track_id: int | None = None


@dataclass
class RawTrack:
    """Accumulated history for one track_id across a video."""

    track_id: int
    class_name: str
    confidences: list[float] = field(default_factory=list)
    centroids: list[tuple[float, float]] = field(default_factory=list)
    frame_indices: list[int] = field(default_factory=list)
    timestamps_seconds: list[float] = field(default_factory=list)
    first_seen_seconds: float = 0.0
    last_seen_seconds: float = 0.0


@dataclass
class VideoProperties:
    fps: float
    frame_count: int
    width: int
    height: int
    duration_seconds: float


@dataclass
class DetectionRunResult:
    video: VideoProperties
    detections: list[RawDetection]
    elapsed_seconds: float
    frames_processed: int


@dataclass
class TrackingRunResult:
    video: VideoProperties
    detections: list[RawDetection]
    tracks: list[RawTrack]
    elapsed_seconds: float
    frames_processed: int


def _open_capture(video_path: str) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        raise ValueError(f"Could not open video file: {video_path}")
    return cap


def _read_video_properties(cap: cv2.VideoCapture) -> VideoProperties:
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = (frame_count / fps) if fps > 0 else 0.0
    return VideoProperties(
        fps=fps, frame_count=frame_count, width=width, height=height,
        duration_seconds=duration,
    )


class YOLO26Service:
    """Loads YOLO26-S once, then exposes detect_frame/detect_video/
    track_video against the single loaded model instance."""

    def __init__(
        self,
        model_name: str,
        weights_dir: Path,
        input_size: int,
        confidence_threshold: float,
        iou_threshold: float,
        device_setting: str,
        frame_stride: int,
    ):
        self._model_name = model_name
        self._weights_dir = weights_dir
        self._input_size = input_size
        self._confidence_threshold = confidence_threshold
        self._iou_threshold = iou_threshold
        self._device_setting = device_setting
        self._frame_stride = max(1, frame_stride)

        self._model = None
        self._device: str | None = None
        self._class_names: dict[int, str] = {}
        self._is_ready = False
        self._lock = threading.Lock()

    # -- lifecycle ----------------------------------------------------------

    def initialize(self) -> None:
        """Loads the YOLO26-S model once. Safe to call exactly once at
        startup (FastAPI lifespan). The Ultralytics package handles the
        pretrained-weight download automatically on first load; weights are
        cached under self._weights_dir, kept separate from the three locked
        anomaly-pipeline checkpoints."""
        from ultralytics import YOLO  # imported lazily so a missing/broken

        if self._device_setting == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = self._device_setting

        self._weights_dir.mkdir(parents=True, exist_ok=True)
        weights_path = self._weights_dir / self._model_name

        t0 = time.time()
        # Ultralytics resolves a bare model name (e.g. "yolo26s.pt") against
        # its own cache dir and downloads if missing. Pointing it at a path
        # inside our own weights_dir keeps the download there instead of
        # Ultralytics' global default cache, and makes the location explicit
        # and inspectable.
        model = YOLO(str(weights_path) if weights_path.exists() else self._model_name)
        if not weights_path.exists():
            # Ultralytics downloaded to its own cache; persist a copy into
            # our local weights_dir so subsequent loads use the pinned path
            # and the location is explicit/inspectable, as requested.
            try:
                resolved = Path(model.ckpt_path) if getattr(model, "ckpt_path", None) else None
                if resolved and resolved.exists() and resolved != weights_path:
                    import shutil

                    shutil.copy2(resolved, weights_path)
                    logger.info("YOLO weights cached at %s", weights_path)
            except OSError:
                logger.exception("Could not cache YOLO weights locally; using Ultralytics' own cache.")

        model.to(self._device)
        self._class_names = dict(model.names)
        self._model = model
        self._is_ready = True

        logger.info("YOLO model loaded")
        logger.info("YOLO device: %s", self._device)
        logger.info("YOLO model: %s", self._model_name)
        logger.info("YOLO model load time: %.2fs", time.time() - t0)

    def is_ready(self) -> bool:
        return self._is_ready

    def get_model_info(self) -> dict:
        return {
            "name": self._model_name,
            "task": "detect",
            "device": self._device,
            "input_size": self._input_size,
            "confidence_threshold": self._confidence_threshold,
            "iou_threshold": self._iou_threshold,
            "loaded": self._is_ready,
            "num_classes": len(self._class_names),
            "available_classes": list(self._class_names.values()),
            "operational_classes": {
                "person": sorted(PERSON_CLASSES),
                "vehicle": sorted(VEHICLE_CLASSES),
            },
        }

    # -- single-frame detection ----------------------------------------------

    def detect_frame(self, frame, frame_index: int = 0, timestamp_seconds: float = 0.0) -> list[RawDetection]:
        """Runs detection on a single already-decoded BGR frame (as returned
        by cv2.VideoCapture.read()). Does not touch the video file system --
        callers decode frames themselves."""
        self._require_ready()
        with self._lock:
            results = self._model.predict(
                source=frame,
                imgsz=self._input_size,
                conf=self._confidence_threshold,
                iou=self._iou_threshold,
                device=self._device,
                verbose=False,
            )
        return self._extract_detections(results[0], frame_index, timestamp_seconds)

    # -- video detection (no tracking) ---------------------------------------

    def detect_video(self, video_path: str, on_progress: Callable[[int, int], None] | None = None) -> DetectionRunResult:
        """Streams the video frame-by-frame, running detection at
        self._frame_stride. Releases the VideoCapture unconditionally. Never
        buffers decoded frames beyond the one currently being processed."""
        self._require_ready()
        cap = _open_capture(video_path)
        try:
            props = _read_video_properties(cap)
            detections: list[RawDetection] = []
            frame_index = 0
            frames_processed = 0
            t0 = time.time()

            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                if frame_index % self._frame_stride == 0:
                    timestamp = (frame_index / props.fps) if props.fps > 0 else 0.0
                    with self._lock:
                        results = self._model.predict(
                            source=frame,
                            imgsz=self._input_size,
                            conf=self._confidence_threshold,
                            iou=self._iou_threshold,
                            device=self._device,
                            verbose=False,
                        )
                    detections.extend(
                        self._extract_detections(results[0], frame_index, timestamp)
                    )
                    frames_processed += 1
                    if on_progress is not None:
                        on_progress(frame_index + 1, props.frame_count)

                frame_index += 1

            elapsed = time.time() - t0
            return DetectionRunResult(
                video=props, detections=detections, elapsed_seconds=elapsed,
                frames_processed=frames_processed,
            )
        finally:
            cap.release()

    # -- video tracking -------------------------------------------------------

    def track_video(self, video_path: str, on_progress: Callable[[int, int], None] | None = None) -> TrackingRunResult:
        """Streams the video frame-by-frame through Ultralytics' built-in
        ByteTrack integration (ultralytics' own tracker, not a custom one).
        Accumulates per-track history (class, confidences, centroids,
        frame span) as it goes, then returns both the raw per-frame
        detections and the reduced per-track summaries."""
        self._require_ready()
        cap = _open_capture(video_path)
        try:
            props = _read_video_properties(cap)
            detections: list[RawDetection] = []
            tracks: dict[int, RawTrack] = {}
            frame_index = 0
            frames_processed = 0
            t0 = time.time()

            # model.track() keeps its own internal tracker state across
            # calls via persist=True -- it must be called once per frame, in
            # order, on the same model instance, for track IDs to be
            # continuous. Frame striding for tracking is therefore not
            # supported the same way as plain detection (skipping frames
            # would break track continuity); tracking always runs stride=1.
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                timestamp = (frame_index / props.fps) if props.fps > 0 else 0.0
                with self._lock:
                    results = self._model.track(
                        source=frame,
                        imgsz=self._input_size,
                        conf=self._confidence_threshold,
                        iou=self._iou_threshold,
                        device=self._device,
                        persist=True,
                        tracker="bytetrack.yaml",
                        verbose=False,
                    )
                frame_dets = self._extract_detections(results[0], frame_index, timestamp)
                detections.extend(frame_dets)

                for det in frame_dets:
                    if det.track_id is None:
                        continue
                    centroid = ((det.x1 + det.x2) / 2.0, (det.y1 + det.y2) / 2.0)
                    track = tracks.get(det.track_id)
                    if track is None:
                        track = RawTrack(
                            track_id=det.track_id,
                            class_name=det.class_name,
                            first_seen_seconds=timestamp,
                        )
                        tracks[det.track_id] = track
                    track.confidences.append(det.confidence)
                    track.centroids.append(centroid)
                    track.frame_indices.append(frame_index)
                    track.timestamps_seconds.append(timestamp)
                    track.last_seen_seconds = timestamp

                frames_processed += 1
                if on_progress is not None:
                    on_progress(frame_index + 1, props.frame_count)
                frame_index += 1

            elapsed = time.time() - t0
            return TrackingRunResult(
                video=props, detections=detections, tracks=list(tracks.values()),
                elapsed_seconds=elapsed, frames_processed=frames_processed,
            )
        finally:
            cap.release()
            # Reset the tracker's internal state so the next track_video()
            # call (a different video) doesn't continue IDs/history from
            # this one.
            if self._model is not None and hasattr(self._model, "predictor"):
                self._model.predictor = None

    # -- internal -------------------------------------------------------------

    def _require_ready(self) -> None:
        if not self._is_ready or self._model is None:
            raise RuntimeError("YOLO26Service method called before initialize() completed.")

    def _extract_detections(self, result, frame_index: int, timestamp_seconds: float) -> list[RawDetection]:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)
        ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else None

        out: list[RawDetection] = []
        for i in range(len(boxes)):
            class_id = int(classes[i])
            out.append(
                RawDetection(
                    class_id=class_id,
                    class_name=self._class_names.get(class_id, str(class_id)),
                    confidence=float(confs[i]),
                    x1=float(xyxy[i][0]), y1=float(xyxy[i][1]),
                    x2=float(xyxy[i][2]), y2=float(xyxy[i][3]),
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                    track_id=int(ids[i]) if ids is not None else None,
                )
            )
        return out


_service: YOLO26Service | None = None


def get_yolo_service() -> YOLO26Service:
    """Module-level singleton accessor, mirroring get_pipeline() in
    final_demo_inference.py. Created empty on first access; initialize() is
    expected to be called exactly once by the FastAPI lifespan hook."""
    global _service
    if _service is None:
        from app.core.config import get_settings

        settings = get_settings()
        _service = YOLO26Service(
            model_name=settings.YOLO_MODEL_NAME,
            weights_dir=settings.YOLO_WEIGHTS_DIR,
            input_size=settings.YOLO_INPUT_SIZE,
            confidence_threshold=settings.YOLO_CONFIDENCE_THRESHOLD,
            iou_threshold=settings.YOLO_IOU_THRESHOLD,
            device_setting=settings.YOLO_DEVICE,
            frame_stride=settings.YOLO_FRAME_STRIDE,
        )
    return _service
