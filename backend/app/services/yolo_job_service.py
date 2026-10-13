"""
Orchestrates one YOLO26 job: the function the JobExecutor actually runs in
the background for /api/v1/yolo/detect and /api/v1/yolo/track. Mirrors the
role analysis_service.run_analysis_job plays for the anomaly pipeline --
upload validation and safe-filename generation happen in the route before
this runs; this function assumes an already-saved, valid video file and
owns the "run YOLO inference and record the outcome" half.

Also home to the deterministic post-processing (object counting, zone/line
evaluation) that turns raw YOLO26Service output into the YoloJobResult
schema the API returns -- all derived from actual inference, nothing
fabricated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.inference.geometry import line_crossing, point_in_polygon
from app.inference.yolo26_service import (
    PERSON_CLASSES,
    VEHICLE_CLASSES,
    RawDetection,
    RawTrack,
    YOLO26Service,
    get_yolo_service,
)
from app.schemas.yolo import (
    BoundingBox,
    ConfidenceStats,
    Detection,
    Line,
    LineCrossingEvent,
    ObjectCounts,
    PerformanceInfo,
    Track,
    VideoInfo,
    YoloJobStatus,
    YoloModelInfo,
    YoloSummary,
    Zone,
    ZoneEvent,
)
from app.services.job_repository import JobRepository

logger = logging.getLogger(__name__)


def _to_detection_schema(det: RawDetection) -> Detection:
    return Detection(
        class_id=det.class_id,
        class_name=det.class_name,
        confidence=det.confidence,
        bbox=BoundingBox(x1=det.x1, y1=det.y1, x2=det.x2, y2=det.y2),
        frame_index=det.frame_index,
        timestamp_seconds=det.timestamp_seconds,
        track_id=det.track_id,
    )


def _movement_direction(centroids: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Normalized direction vector from the first to the most recent
    centroid. Only computed once a track has >= 2 recorded positions --
    otherwise None, never fabricated."""
    if len(centroids) < 2:
        return None
    (x0, y0), (x1, y1) = centroids[0], centroids[-1]
    dx, dy = x1 - x0, y1 - y0
    magnitude = (dx ** 2 + dy ** 2) ** 0.5
    if magnitude == 0:
        return (0.0, 0.0)
    return (dx / magnitude, dy / magnitude)


def _to_track_schema(track: RawTrack) -> Track:
    confidences = track.confidences or [0.0]
    return Track(
        track_id=track.track_id,
        class_name=track.class_name,
        detection_count=len(track.confidences),
        confidence=ConfidenceStats(
            min=min(confidences), max=max(confidences),
            mean=sum(confidences) / len(confidences),
        ),
        first_seen_seconds=track.first_seen_seconds,
        last_seen_seconds=track.last_seen_seconds,
        duration_seconds=max(0.0, track.last_seen_seconds - track.first_seen_seconds),
        current_position=track.centroids[-1] if track.centroids else (0.0, 0.0),
        trajectory=list(track.centroids),
        movement_direction=_movement_direction(track.centroids),
    )


def _compute_object_counts(detections: list[RawDetection]) -> tuple[ObjectCounts, int, int]:
    """Per-frame max simultaneous counts for persons/vehicles, plus a
    by-class tally across the whole run. Returns (counts_for_last_frame,
    max_persons_any_frame, max_vehicles_any_frame)."""
    by_frame: dict[int, list[RawDetection]] = {}
    for det in detections:
        by_frame.setdefault(det.frame_index, []).append(det)

    by_class: dict[str, int] = {}
    max_persons = 0
    max_vehicles = 0
    last_frame_counts = ObjectCounts()

    for frame_index in sorted(by_frame.keys()):
        frame_dets = by_frame[frame_index]
        persons = sum(1 for d in frame_dets if d.class_name in PERSON_CLASSES)
        vehicles = sum(1 for d in frame_dets if d.class_name in VEHICLE_CLASSES)
        max_persons = max(max_persons, persons)
        max_vehicles = max(max_vehicles, vehicles)
        for d in frame_dets:
            by_class[d.class_name] = by_class.get(d.class_name, 0) + 1
        if frame_index == max(by_frame.keys()):
            last_frame_counts = ObjectCounts(persons=persons, vehicles=vehicles, by_class=dict(by_class))

    last_frame_counts.by_class = by_class
    return last_frame_counts, max_persons, max_vehicles


def _evaluate_zones(detections: list[RawDetection], zones: list[Zone]) -> list[ZoneEvent]:
    events: list[ZoneEvent] = []
    for det in detections:
        centroid = ((det.x1 + det.x2) / 2.0, (det.y1 + det.y2) / 2.0)
        for zone in zones:
            if point_in_polygon(centroid, zone.polygon):
                events.append(
                    ZoneEvent(
                        zone_id=zone.id, track_id=det.track_id, class_name=det.class_name,
                        frame_index=det.frame_index, timestamp_seconds=det.timestamp_seconds,
                    )
                )
    return events


def _evaluate_line_crossings(tracks: list[RawTrack], lines: list[Line]) -> list[LineCrossingEvent]:
    events: list[LineCrossingEvent] = []
    for track in tracks:
        for i in range(1, len(track.centroids)):
            prev_point = track.centroids[i - 1]
            curr_point = track.centroids[i]
            for line in lines:
                if line_crossing(prev_point, curr_point, list(line.points)):
                    events.append(
                        LineCrossingEvent(
                            line_id=line.id, track_id=track.track_id, class_name=track.class_name,
                            frame_index=track.frame_indices[i],
                            timestamp_seconds=track.timestamps_seconds[i],
                        )
                    )
    return events


def run_yolo_job(
    job_id: str,
    video_path: Path,
    original_filename: str,
    mode: str,
    zones: list[Zone],
    lines: list[Line],
    job_repository: JobRepository,
) -> None:
    """mode is "detect" or "track". Runs the YOLO26Service accordingly,
    reduces the raw output into the YoloJobResult schema, and persists it
    via job_repository.update(). Never fabricates a value it cannot compute
    from the real inference output."""
    job_repository.update(
        job_id, status=YoloJobStatus.PROCESSING, started_at=datetime.now(timezone.utc),
    )

    service: YOLO26Service = get_yolo_service()

    def on_progress(processed: int, total: int) -> None:
        progress = (processed / total) if total > 0 else None
        job_repository.update(
            job_id, processed_frames=processed, total_frames=total, progress=progress,
        )

    try:
        if mode == "track":
            run_result = service.track_video(str(video_path), on_progress=on_progress)
            raw_tracks = run_result.tracks
        else:
            run_result = service.detect_video(str(video_path), on_progress=on_progress)
            raw_tracks = []

        detections = [_to_detection_schema(d) for d in run_result.detections]
        tracks = [_to_track_schema(t) for t in raw_tracks]

        object_counts, max_persons, max_vehicles = _compute_object_counts(run_result.detections)
        zone_events = _evaluate_zones(run_result.detections, zones) if zones else []
        line_events = _evaluate_line_crossings(raw_tracks, lines) if (lines and raw_tracks) else []

        model_info_dict = service.get_model_info()
        elapsed = run_result.elapsed_seconds
        frames_processed = run_result.frames_processed
        inference_fps = (frames_processed / elapsed) if elapsed > 0 else 0.0
        avg_latency_ms = (elapsed / frames_processed * 1000.0) if frames_processed > 0 else 0.0

        job_repository.update(
            job_id,
            status=YoloJobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            processed_frames=frames_processed,
            total_frames=run_result.video.frame_count,
            progress=1.0,
            video=VideoInfo(
                filename=original_filename,
                duration_seconds=run_result.video.duration_seconds,
                fps=run_result.video.fps,
                width=run_result.video.width,
                height=run_result.video.height,
                frame_count=run_result.video.frame_count,
            ),
            model=YoloModelInfo(
                device=model_info_dict["device"],
                input_size=model_info_dict["input_size"],
                confidence_threshold=model_info_dict["confidence_threshold"],
                iou_threshold=model_info_dict["iou_threshold"],
            ),
            summary=YoloSummary(
                unique_tracks=len(tracks),
                max_persons=max_persons,
                max_vehicles=max_vehicles,
                object_counts=object_counts,
            ),
            detections=detections,
            tracks=tracks,
            zones=zones,
            zone_events=zone_events,
            line_crossings=line_events,
            performance=PerformanceInfo(
                processing_time_seconds=elapsed,
                frames_processed=frames_processed,
                inference_fps=inference_fps,
                average_latency_ms=avg_latency_ms,
            ),
        )
    except Exception as exc:
        logger.exception("YOLO job %s failed for %s", job_id, original_filename)
        job_repository.update(
            job_id, status=YoloJobStatus.FAILED, completed_at=datetime.now(timezone.utc),
            error=str(exc),
        )
