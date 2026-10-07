# YOLO26-S Supporting Vision Layer

Added 2026-10-06. A second, independent computer-vision layer on top of the existing SENTINEL-X
FastAPI backend — real-time object detection and multi-object tracking via the official
Ultralytics YOLO26-S pretrained model (COCO weights). It is **additive only**: it never touches,
retrains, or merges with the authoritative I3D → Stage1 binary detector → Stage2 action
classifier pipeline (`backend/app/inference/final_demo_inference.py`), which remains the sole
source of anomaly/action intelligence. YOLO26 answers a different question — "what objects are
in this footage, and where did they go" — not "is this an anomaly."

## Purpose

- Real-time-ish object detection (person, bicycle, car, motorcycle, bus, truck, and the full
  COCO-80 set internally) on uploaded video.
- Multi-object tracking with persistent IDs across frames (ByteTrack).
- Deterministic analytics derived only from real detections/tracks: object counts, max
  simultaneous objects, track duration, movement direction, zone entry, line-crossing counts.
- A standalone, independently queryable layer a frontend or operator can call alongside (not
  instead of) the anomaly pipeline.

## Model

- **Model:** YOLO26-S (`yolo26s.pt`), official Ultralytics pretrained COCO weights.
- **Pretrained, not fine-tuned.** No training, fine-tuning, or dataset creation was performed —
  explicitly out of scope for this phase (see Limitations).
- **Ultralytics version:** `8.4.137` (already present in the environment before this work; pinned
  in `requirements.txt`, not a blind add).
- **Weights location:** `backend/models/yolo26/yolo26s.pt`, downloaded on first `initialize()`
  call from Ultralytics' official release (`https://github.com/ultralytics/assets/releases/...`),
  cached locally thereafter. Kept in its own directory, separate from the three locked
  anomaly-pipeline checkpoints (`backend/models/{i3d,stage1_binary,stage2_action}/`). Already
  covered by the repo's root `.gitignore` `*.pt` rule — never committed.

## Installation

Already satisfied in this environment — no action needed on a machine with the same setup:

```bash
pip install -r backend/requirements.txt   # includes ultralytics==8.4.137
```

First call to `YOLO26Service.initialize()` (done automatically by the FastAPI `lifespan` hook on
server startup) downloads `yolo26s.pt` (~20MB) if not already cached under
`backend/models/yolo26/`.

## Configuration

All settings in `backend/app/core/config.py`, overridable via environment variables (see
`backend/.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `YOLO_MODEL_NAME` | `yolo26s.pt` | Model weights file |
| `YOLO_INPUT_SIZE` | `640` | Inference resolution (pixels) |
| `YOLO_CONFIDENCE_THRESHOLD` | `0.25` | Minimum detection confidence |
| `YOLO_IOU_THRESHOLD` | `0.45` | NMS IoU threshold |
| `YOLO_DEVICE` | `auto` | `auto` (CUDA if available, else CPU) / `cuda` / `cpu` |
| `YOLO_FRAME_STRIDE` | `1` | Process every Nth frame for `detect_video()` (tracking always runs stride=1 — see Tracking) |

## Architecture

```
backend/app/
  inference/
    yolo26_service.py    YOLO26Service: initialize/is_ready/get_model_info/
                          detect_frame/detect_video/track_video (singleton via get_yolo_service())
    geometry.py           point_in_polygon(), line_crossing() — pure functions, no dependency
  schemas/yolo.py          Detection, Track, Zone, Line, ZoneEvent, LineCrossingEvent,
                            YoloModelInfo, VideoInfo, YoloSummary, YoloJobResult (Pydantic)
  services/yolo_job_service.py
                            run_yolo_job(): runs detection/tracking, reduces raw output into
                            YoloJobResult, computes object counts + zone/line events
  api/routes/yolo.py        /api/v1/yolo/* routes
```

**Model loading:** singleton pattern mirroring the anomaly pipeline's `InferencePipeline`/
`get_pipeline()`. `YOLO26Service` is constructed empty at import time (no I/O); `initialize()` is
called once from FastAPI's `lifespan`, independently of and in parallel in spirit with the
anomaly pipeline's own `load()` call — each wrapped in its own try/except so a YOLO load failure
can never prevent the anomaly pipeline from serving (and vice versa). `is_ready()` reports the
real state; `/api/v1/yolo/health` returns `model_not_loaded` honestly rather than crashing if
`initialize()` failed.

**Thread safety:** a single `threading.Lock` serializes calls into the one shared Ultralytics
model instance, since FastAPI `BackgroundTasks` runs jobs in a thread pool and a single
Ultralytics `YOLO` instance is not guaranteed safe under concurrent calls. This is "thread-safe
enough" for single-user/demo scale. A future worker-process migration (e.g. Celery) would not
need this lock at all — each worker process would own its own model instance.

**Job infrastructure reused, not forked.** YOLO video jobs flow through the *same*
`JobRepository`/`JobExecutor` abstractions the anomaly pipeline uses — a second
`InMemoryJobRepository` instance (same class, pointed at `storage/results/yolo/` instead of
`storage/results/`) and the same `InProcessJobExecutor`. `JobExecutor.submit()`'s 3-argument
interface (`job_id, video_path, original_filename`) is unchanged; YOLO-specific parameters
(`mode`, `zones`, `lines`) are bound via closure before the executor is constructed, so no shared
interface was altered.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/yolo/health` | `{status, model_loaded, device}` |
| GET | `/api/v1/yolo/model` | Full model info: device, input size, thresholds, all 80 class names, operational groupings |
| POST | `/api/v1/yolo/detect` | Upload a video, optional `zones` form field (JSON) → `202` + `job_id` |
| POST | `/api/v1/yolo/track` | Upload a video, optional `zones`/`lines` form fields (JSON) → `202` + `job_id` |
| GET | `/api/v1/yolo/jobs/{job_id}` | Current job status (`queued`/`processing`/`completed`/`failed`), real `processed_frames`/`total_frames`/`progress` while running |
| GET | `/api/v1/yolo/jobs/{job_id}/result` | Completed `YoloJobResult` (409 if not completed yet) |
| GET | `/api/v1/yolo/tracks/{job_id}/{track_id}` | One track's full detail: class, first/last seen, duration, trajectory, detection count, confidence stats |

Long video jobs never block the HTTP request — the same upload → `job_id` → poll pattern as the
existing `/api/v1/analysis` endpoint. `processed_frames`/`total_frames`/`progress` are only ever
set from a real `processed/total` ratio reported by the streaming loop; if `total` is unknown
(e.g. corrupt frame-count metadata), `progress` is left `null` rather than fabricated.

## Detection

Full COCO-80 class capability is always available from the model (`get_model_info()["available_classes"]`
lists all 80). For SENTINEL-X's operational purposes, classes are additionally grouped into
`person` and `vehicle` (bicycle, car, motorcycle, bus, truck) buckets at the service layer — this
is a display/aggregation convenience, not a restriction on what the model can detect.

Each `Detection` carries: `class_id`, `class_name`, `confidence`, pixel-coordinate `bbox`
(`x1,y1,x2,y2`), `frame_index`, `timestamp_seconds` (`frame_index / video_fps`), and `track_id`
(only present when produced via `/track`, `null` for plain `/detect`).

## Tracking

Multi-object tracking uses Ultralytics' own built-in ByteTrack integration
(`model.track(..., tracker="bytetrack.yaml", persist=True)`) — not a custom tracker
implementation. Chosen specifically for being lightweight and appropriate for this hardware class,
per the task's requirement.

**Important constraint:** tracking always runs at frame stride 1 (every frame), regardless of
`YOLO_FRAME_STRIDE`. `model.track()` with `persist=True` maintains internal tracker state across
calls — skipping frames would break track continuity and produce incorrect IDs. `YOLO_FRAME_STRIDE`
only affects plain `detect_video()`.

Each `Track` is reduced from accumulated per-frame history into: `track_id`, `class_name`,
`detection_count`, confidence `{min, max, mean}`, `first_seen_seconds`, `last_seen_seconds`,
`duration_seconds`, `current_position` (most recent centroid), `trajectory` (full centroid
history), and `movement_direction` — a normalized `(dx, dy)` vector from the first to the most
recent centroid, **only computed once a track has ≥ 2 recorded positions**; otherwise `null`,
never fabricated.

Tracking is validated against **file-based video only**. SENTINEL-X does not claim real-time
RTSP/WebRTC tracking support — that path has not been built or verified end-to-end.

## Zones and line-crossing

Deterministic geometry in `app/inference/geometry.py` — standard ray-casting point-in-polygon and
O(1) segment-intersection line crossing. No GIS library, no new dependency.

- **Zone:** `{id, name, polygon: [[x,y], ...]}`. Evaluated per-detection, per-frame: if a
  detection's bounding-box centroid falls inside the polygon, a `ZoneEvent` is recorded.
- **Line:** `{id, name, points: [[x1,y1], [x2,y2]]}` — exactly 2 points. Evaluated per-track:
  whenever a track's movement between two consecutive frames crosses the line segment, a
  `LineCrossingEvent` is recorded (requires tracking — zones work with plain detection too, lines
  do not).

Both are optional request parameters (JSON passed as form fields to `/detect` / `/track`). If
none are configured, `zones`/`line_crossings` in the result are empty lists — never fabricated
placeholder data.

## Performance (measured, RTX 3050 Laptop 6GB)

Benchmark script: `backend/scripts/benchmark_yolo.py` (run manually, not part of the app).
Measured 2026-10-06 against `test_videos/Abuse/Abuse021_x264.mp4` (320×240, 1913 frames @ 30fps,
63.8s duration):

| Metric | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU |
| CUDA | Available, used (`device=cuda`) |
| Model load (cold start, cached weights) | 1.52s |
| First-inference (warmup) latency | 1296.9 ms — **reported separately, never folded into steady-state FPS** |
| `detect_video()` steady-state FPS | 20.87 |
| `detect_video()` avg latency | 47.92 ms/frame |
| `detect_video()` peak VRAM | 100 MB |
| `track_video()` steady-state FPS | 15.95 |
| `track_video()` avg latency | 62.68 ms/frame |
| `track_video()` peak VRAM | 100 MB |

YOLO26-S comfortably clears the 8 FPS usability threshold on this hardware — a YOLO26-N
comparison was not run, per the plan's "only compare if S is genuinely borderline" rule.

CPU fallback was verified functionally correct (produces real detections when forced to
`device="cpu"`), but CPU throughput was not separately benchmarked for FPS in this pass — only
GPU numbers above are from the formal benchmark run.

## Testing

`backend/tests/test_yolo26.py`, 20 tests, all passing (`pytest tests/test_yolo26.py -v`, 2026-10-06):
imports, CUDA detection, model loading, warmup, single-image detection, short-video detection,
tracking, result schema serialization (round-trip), empty-detection case (blank frame → `[]`,
never fabricated), invalid-video handling (missing file, corrupt file), CPU fallback, and 5 live
API endpoint tests (health, model info, full detect job lifecycle via `TestClient`, 404 on unknown
job, confirming `/api/health` still works).

## Known limitations

- **No combined anomaly+YOLO endpoint.** The two pipelines are independently callable; there is
  no single request that runs both and merges results. Both remain modular per the task's
  explicit instruction, and the engineering cost of a true combined, correctly-sequenced
  async endpoint was judged out of scope for this phase.
- **Real-time RTSP/WebRTC tracking is not implemented or verified.** Tracking has only been
  validated against file-based uploaded video.
- **No Pose/segmentation/depth/OBB/classification models.** The architecture (separate service
  module, pluggable model name via config) allows adding these later without rewriting the
  detection service, but none are implemented in this pass.
- **No training or fine-tuning.** YOLO26-S runs with stock COCO pretrained weights; it has not
  been adapted to this project's specific camera footage or anomaly classes.
- **False positives at default threshold on low-resolution surveillance footage.** On the
  320×240 test clip, `detect_video()` at the default `YOLO_CONFIDENCE_THRESHOLD=0.25` returned a
  substantial number of likely-spurious detections (e.g. `frisbee`, `chair`, `tv`,
  `refrigerator`) alongside genuine `person`/`bicycle` detections. This is an honest, measured
  property of a COCO-pretrained general-purpose detector on compressed low-resolution CCTV
  footage at a permissive threshold — not a bug. `YOLO_CONFIDENCE_THRESHOLD` is the tuning knob
  for a specific deployment; it was not silently raised to make output look cleaner.
- **CPU inference FPS not formally benchmarked.** Functional correctness on CPU was verified; a
  CPU throughput number was not captured in this pass.
- **In-memory YOLO job index is lost on process restart**, same documented limitation as the
  existing analysis pipeline's `JobRepository` — JSON result files on disk survive, but startup
  rehydration is not wired in for either pipeline yet.
