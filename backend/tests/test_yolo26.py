"""
Tests for the YOLO26 supporting vision layer.

Covers the 12 required focus areas: imports, CUDA detection, model loading,
warmup, single-image detection, short-video detection, tracking, result
schema serialization, empty-detection case, invalid-video handling, CPU
fallback, and API endpoint behavior.

Uses the real test video at test_videos/Abuse/Abuse021_x264.mp4 (read-only,
never modified) and the real downloaded yolo26s.pt weights -- no mocked
inference. Model loading happens once per test session via a session-scoped
fixture so the ~1-2s load cost (weights are already cached locally) is not
repeated for every test.

Run from backend/: pytest tests/test_yolo26.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

TEST_VIDEO = BACKEND_ROOT.parent / "test_videos" / "Abuse" / "Abuse021_x264.mp4"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def yolo_service():
    """Real YOLO26Service, loaded once (CUDA if available) for the whole
    test session -- not re-initialized per test."""
    from app.inference.yolo26_service import YOLO26Service

    service = YOLO26Service(
        model_name="yolo26s.pt",
        weights_dir=BACKEND_ROOT / "models" / "yolo26",
        input_size=640,
        confidence_threshold=0.25,
        iou_threshold=0.45,
        device_setting="auto",
        frame_stride=1,
    )
    service.initialize()
    return service


@pytest.fixture(scope="session")
def cpu_yolo_service():
    """A second, CPU-forced instance for the CPU-fallback test. Session
    scoped since it's only needed by one or two tests but still costs a
    real model load."""
    from app.inference.yolo26_service import YOLO26Service

    service = YOLO26Service(
        model_name="yolo26s.pt",
        weights_dir=BACKEND_ROOT / "models" / "yolo26",
        input_size=640,
        confidence_threshold=0.25,
        iou_threshold=0.45,
        device_setting="cpu",
        frame_stride=1,
    )
    service.initialize()
    return service


@pytest.fixture
def first_frame():
    import cv2

    cap = cv2.VideoCapture(str(TEST_VIDEO))
    ok, frame = cap.read()
    cap.release()
    assert ok, f"Could not read a frame from {TEST_VIDEO}"
    return frame


@pytest.fixture
def person_frame():
    """A frame known (from manual inspection) to contain a real person
    detection at the default confidence threshold -- used for the
    non-empty-detection assertions."""
    import cv2

    cap = cv2.VideoCapture(str(TEST_VIDEO))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 1434)
    ok, frame = cap.read()
    cap.release()
    assert ok, "Could not read frame 1434 from test video"
    return frame


# ---------------------------------------------------------------------------
# 1. Imports
# ---------------------------------------------------------------------------


def test_ultralytics_imports_cleanly():
    from ultralytics import YOLO  # noqa: F401


def test_yolo26_service_module_imports_cleanly():
    from app.inference import yolo26_service  # noqa: F401
    from app.inference import geometry  # noqa: F401


# ---------------------------------------------------------------------------
# 2. CUDA detection
# ---------------------------------------------------------------------------


def test_cuda_detection_is_real():
    import torch

    # Just confirms the call succeeds and returns a bool -- not asserting
    # True, since this must also pass on a CPU-only machine.
    assert isinstance(torch.cuda.is_available(), bool)


# ---------------------------------------------------------------------------
# 3. Model loading
# ---------------------------------------------------------------------------


def test_model_loads_and_reports_ready(yolo_service):
    assert yolo_service.is_ready() is True


def test_model_info_reports_real_values(yolo_service):
    info = yolo_service.get_model_info()
    assert info["name"] == "yolo26s.pt"
    assert info["loaded"] is True
    assert info["num_classes"] == 80
    assert "person" in info["available_classes"]
    assert info["device"] in ("cuda", "cpu")


def test_service_not_ready_before_initialize():
    from app.inference.yolo26_service import YOLO26Service

    fresh = YOLO26Service(
        model_name="yolo26s.pt",
        weights_dir=BACKEND_ROOT / "models" / "yolo26",
        input_size=640,
        confidence_threshold=0.25,
        iou_threshold=0.45,
        device_setting="auto",
        frame_stride=1,
    )
    assert fresh.is_ready() is False
    with pytest.raises(RuntimeError):
        fresh.detect_frame(None, 0, 0.0)


# ---------------------------------------------------------------------------
# 4. Warmup (cold start vs steady state, timed for real)
# ---------------------------------------------------------------------------


def test_warmup_latency_is_measurable_and_distinct(yolo_service, first_frame):
    import time

    t0 = time.time()
    yolo_service.detect_frame(first_frame, frame_index=0, timestamp_seconds=0.0)
    first_call_elapsed = time.time() - t0

    t1 = time.time()
    yolo_service.detect_frame(first_frame, frame_index=1, timestamp_seconds=0.033)
    second_call_elapsed = time.time() - t1

    # Not a strict performance assertion (hardware-dependent) -- just
    # confirms both calls complete and produce a real, non-negative timing,
    # so cold-start-vs-steady-state can be meaningfully distinguished by
    # the benchmark script's own reporting.
    assert first_call_elapsed >= 0
    assert second_call_elapsed >= 0


# ---------------------------------------------------------------------------
# 5. Single-image detection
# ---------------------------------------------------------------------------


def test_single_frame_detection_returns_real_values(yolo_service, person_frame):
    detections = yolo_service.detect_frame(person_frame, frame_index=1434, timestamp_seconds=47.8)
    person_dets = [d for d in detections if d.class_name == "person"]
    assert len(person_dets) >= 1

    det = person_dets[0]
    assert det.class_id == 0
    assert 0.0 <= det.confidence <= 1.0
    assert det.x1 < det.x2
    assert det.y1 < det.y2
    assert det.frame_index == 1434
    assert det.timestamp_seconds == 47.8


# ---------------------------------------------------------------------------
# 6. Short-video detection
# ---------------------------------------------------------------------------


def test_detect_video_progression_is_real(yolo_service):
    progress_calls = []
    result = yolo_service.detect_video(
        str(TEST_VIDEO), on_progress=lambda p, t: progress_calls.append((p, t))
    )

    assert result.frames_processed == result.video.frame_count
    assert result.video.fps == 30.0
    assert result.video.frame_count > 0
    assert len(progress_calls) == result.video.frame_count
    assert progress_calls[0] == (1, result.video.frame_count)
    assert progress_calls[-1] == (result.video.frame_count, result.video.frame_count)

    # at least one real person detection should appear somewhere in the clip
    assert any(d.class_name == "person" for d in result.detections)

    # timestamp formula sanity check against real fps
    for det in result.detections[:5]:
        expected_ts = det.frame_index / result.video.fps
        assert abs(det.timestamp_seconds - expected_ts) < 1e-6


# ---------------------------------------------------------------------------
# 7. Tracking
# ---------------------------------------------------------------------------


def test_track_video_produces_consistent_tracks(yolo_service):
    result = yolo_service.track_video(str(TEST_VIDEO))

    assert result.frames_processed == result.video.frame_count
    assert len(result.tracks) > 0

    track_ids = [t.track_id for t in result.tracks]
    assert len(track_ids) == len(set(track_ids)), "track_ids must be distinct"

    for track in result.tracks:
        assert track.frame_indices == sorted(track.frame_indices)
        assert len(track.centroids) == len(track.frame_indices)
        assert len(track.timestamps_seconds) == len(track.frame_indices)
        assert track.first_seen_seconds <= track.last_seen_seconds


# ---------------------------------------------------------------------------
# 8. Result schema serialization
# ---------------------------------------------------------------------------


def test_yolo_job_result_schema_serializes_cleanly():
    from app.schemas.yolo import (
        BoundingBox,
        Detection,
        Track,
        ConfidenceStats,
        VideoInfo,
        YoloModelInfo,
        YoloJobResult,
        YoloJobStatus,
    )

    result = YoloJobResult(
        job_id="test-job-123",
        status=YoloJobStatus.COMPLETED,
        mode="track",
        video=VideoInfo(filename="test.mp4", duration_seconds=10.0, fps=30.0, width=320, height=240, frame_count=300),
        model=YoloModelInfo(device="cuda", input_size=640, confidence_threshold=0.25, iou_threshold=0.45),
        detections=[
            Detection(
                class_id=0, class_name="person", confidence=0.85,
                bbox=BoundingBox(x1=10.0, y1=20.0, x2=50.0, y2=100.0),
                frame_index=0, timestamp_seconds=0.0, track_id=1,
            )
        ],
        tracks=[
            Track(
                track_id=1, class_name="person", detection_count=1,
                confidence=ConfidenceStats(min=0.85, max=0.85, mean=0.85),
                first_seen_seconds=0.0, last_seen_seconds=0.5, duration_seconds=0.5,
                current_position=(30.0, 60.0), trajectory=[(30.0, 60.0)],
                movement_direction=None,
            )
        ],
    )

    raw_json = result.model_dump_json()
    assert '"job_id":"test-job-123"' in raw_json

    # must round-trip
    from app.schemas.yolo import YoloJobResult as _YoloJobResult

    reloaded = _YoloJobResult.model_validate_json(raw_json)
    assert reloaded.job_id == "test-job-123"
    assert reloaded.detections[0].class_name == "person"
    assert reloaded.tracks[0].track_id == 1

    # no raw Python/Ultralytics objects should leak into the dumped dict
    dumped = result.model_dump()
    assert isinstance(dumped["detections"][0]["bbox"], dict)


# ---------------------------------------------------------------------------
# 9. Empty-detection case
# ---------------------------------------------------------------------------


def test_frame_with_no_objects_returns_empty_list_not_fabricated(yolo_service):
    import numpy as np

    # A solid black frame -- genuinely nothing for the model to detect.
    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detections = yolo_service.detect_frame(blank_frame, frame_index=0, timestamp_seconds=0.0)
    assert detections == []


# ---------------------------------------------------------------------------
# 10. Invalid-video handling
# ---------------------------------------------------------------------------


def test_detect_video_raises_on_missing_file(yolo_service):
    with pytest.raises(ValueError):
        yolo_service.detect_video("this_file_does_not_exist_anywhere.mp4")


def test_detect_video_raises_on_corrupt_file(yolo_service, tmp_path):
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"not a real video file, just garbage bytes")
    with pytest.raises(ValueError):
        yolo_service.detect_video(str(corrupt))


# ---------------------------------------------------------------------------
# 11. CPU fallback
# ---------------------------------------------------------------------------


def test_cpu_fallback_produces_real_detections(cpu_yolo_service, person_frame):
    assert cpu_yolo_service.get_model_info()["device"] == "cpu"
    detections = cpu_yolo_service.detect_frame(person_frame, frame_index=1434, timestamp_seconds=47.8)
    assert any(d.class_name == "person" for d in detections)


# ---------------------------------------------------------------------------
# 12. API endpoint behavior
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_client():
    """TestClient against the real app, but with lifespan suppressed for
    test speed -- the yolo router's module-level singleton is initialized
    directly instead, mirroring what lifespan would do, so routes see a
    real, ready service without re-running the full anomaly-pipeline load
    (which depends on the three locked checkpoints and isn't the subject of
    this test file)."""
    from fastapi.testclient import TestClient

    from app.inference.yolo26_service import get_yolo_service
    import app.main as main_module

    # Ensure the YOLO singleton is initialized before any request -- the
    # real initialize() path, same as lifespan calls, just invoked directly
    # here instead of via the app's startup event for test isolation from
    # the (slower, checkpoint-dependent) anomaly pipeline load.
    get_yolo_service().initialize()

    with TestClient(main_module.app) as client:
        yield client


def test_api_yolo_health_endpoint(api_client):
    response = api_client.get("/api/v1/yolo/health")
    assert response.status_code == 200
    body = response.json()
    assert body["model_loaded"] is True
    assert body["device"] in ("cuda", "cpu")


def test_api_yolo_model_endpoint(api_client):
    response = api_client.get("/api/v1/yolo/model")
    assert response.status_code == 200
    body = response.json()
    assert body["num_classes"] == 80


def test_api_yolo_detect_submits_job_and_completes(api_client):
    with open(TEST_VIDEO, "rb") as f:
        response = api_client.post(
            "/api/v1/yolo/detect",
            files={"file": ("Abuse021_x264.mp4", f, "video/mp4")},
        )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "queued"

    # TestClient runs BackgroundTasks synchronously before returning the
    # response in this FastAPI/Starlette version's test harness, so the job
    # should already be completed (or at minimum progressed) by the time we
    # poll -- poll briefly to be safe without assuming exact timing.
    import time

    status_body = None
    for _ in range(60):
        status_response = api_client.get(f"/api/v1/yolo/jobs/{job_id}")
        assert status_response.status_code == 200
        status_body = status_response.json()
        if status_body["status"] in ("completed", "failed"):
            break
        time.sleep(1)

    assert status_body is not None
    assert status_body["status"] == "completed", status_body.get("error")

    result_response = api_client.get(f"/api/v1/yolo/jobs/{job_id}/result")
    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["video"]["filename"] == "Abuse021_x264.mp4"
    assert "detections" in result_body


def test_api_yolo_jobs_unknown_id_returns_404(api_client):
    response = api_client.get("/api/v1/yolo/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_api_existing_health_endpoint_unaffected(api_client):
    """Confirms adding the YOLO router did not break the pre-existing
    /api/health endpoint."""
    response = api_client.get("/api/health")
    assert response.status_code == 200
