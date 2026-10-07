# SENTINEL-X — Project Inventory & Source of Truth

_Last verified against the filesystem: 2026-10-06._

## 1. Document Purpose

This document exists to prevent, months from now:

- accidental use of old projects (`D:\2nd Try Major project\System\`, `WORKING_SYSTEM_GOLDEN_BACKUP\`, `C:\Users\Gulabaji\ucf_crime_demo\`) as a source for SENTINEL-X work
- accidental overwriting of trained models with similarly-named files from elsewhere
- accidental deletion or movement of model/video assets without a checksum check first
- confusion between the public (`SENTINEL-X`) and private (`SENTINEL-X-private`) GitHub repositories
- confusion about which model checkpoint is authoritative for each stage
- confusion about where test videos physically live and whether they were moved or copied
- accidental public exposure of protected model weights or test videos

**This document should be updated whenever the project structure, models, protected assets, or repositories change.** If a model is replaced, a file is moved, or a repository's contents change, update the relevant section here in the same session.

## 2. Current Project Status

| Field | Value |
|---|---|
| Project name | SENTINEL-X |
| Local root | `D:\SENTINEL-X` |
| Current status | FastAPI backend implemented and verified end-to-end (see §6a); no frontend yet |
| Training status | Models already trained. Do **not** retrain as part of normal project development. |
| Purpose of the 81 videos | Local test/demo dataset (train-split sanity check, not a generalization benchmark) |
| Purpose of the 3 models | Runtime inference only (I3D feature extraction, Stage 1 binary detection, Stage 2 action classification) |

## 3. AUTHORITATIVE LOCAL DIRECTORY TREE

Verified directly against the filesystem on 2026-10-06 (via `find`, excluding `.git/`):

```
D:\SENTINEL-X\
├── .gitignore
├── README.md
├── PROJECT_INVENTORY.md
├── backend\
│   ├── requirements.txt
│   ├── app\
│   │   └── inference\
│   │       ├── final_demo_inference.py
│   │       └── pytorch_i3d.py
│   └── models\
│       ├── README.md
│       ├── i3d\
│       │   └── rgb_imagenet.pt
│       ├── stage1_binary\
│       │   └── best_model.pt
│       └── stage2_action\
│           └── best_model.pt
└── test_videos\
    ├── README.md
    ├── Abuse\          (7 .mp4 files)
    ├── Arrest\         (7 .mp4 files)
    ├── Arson\          (7 .mp4 files)
    ├── Burglary\       (7 .mp4 files)
    ├── Explosion\      (7 .mp4 files)
    ├── Fighting\       (7 .mp4 files)
    ├── Normal\         (7 .mp4 files)
    ├── RoadAccidents\  (7 .mp4 files)
    ├── Robbery\        (7 .mp4 files)
    ├── Shooting\       (4 .mp4 files)
    ├── Shoplifting\    (7 .mp4 files)
    └── Vandalism\      (7 .mp4 files)
```

This matches the originally expected structure exactly, with three additions: `PROJECT_INVENTORY.md` (this file), and `README.md` files inside `backend/models/` and `test_videos/` (added when the public GitHub repo was prepared, documenting why those directories' binary contents are excluded from the public repo).

## 4. MODELS — COMPLETE INVENTORY

All values below were re-verified against the live filesystem on 2026-10-06, not assumed from prior conversation.

| Model | Current local path | Original source path | Purpose | Size | MD5 | Authoritative | GitHub location | Public/Private | May be replaced | May be retrained |
|---|---|---|---|---|---|---|---|---|---|---|
| Stage 1 — Final Binary Detector V1 | `D:\SENTINEL-X\backend\models\stage1_binary\best_model.pt` | `C:\Users\Gulabaji\ucf_crime_demo\final_binary_detector_v1\best_model.pt` | Binary anomaly detection (Normal vs Anomaly) | 7,220,514 bytes (6.9 MB) | `125ff7847dfc663567528f3d62fc5a9d` | YES | `rahulgulabaji/SENTINEL-X-private` (via Git LFS) | Private only | Only with explicit instruction + checksum re-verification | NO, not without explicit instruction |
| Stage 2 — Action Classifier V2 | `D:\SENTINEL-X\backend\models\stage2_action\best_model.pt` | `C:\Users\Gulabaji\ucf_crime_demo\action_classifier_v2\best_model.pt` | 13-class action/subtype classification, runs only when Stage 1 flags Anomaly | 8,280,738 bytes (7.9 MB) | `3e3753abfd0caeffd6f65194feb6e58b` | YES (see important caveat below) | `rahulgulabaji/SENTINEL-X-private` (via Git LFS) | Private only | Only with explicit instruction + checksum re-verification | NO, not without explicit instruction |
| I3D — RGB ImageNet backbone | `D:\SENTINEL-X\backend\models\i3d\rgb_imagenet.pt` | `C:\Users\Gulabaji\ucf_crime_demo\pytorch-i3d\models\rgb_imagenet.pt` | Feature extraction backbone (Inflated 3D ConvNet, ImageNet-pretrained) | 50,883,138 bytes (48.5 MB) | `591830edb0dc9c0b1298a326ca9bd3cc` | YES | `rahulgulabaji/SENTINEL-X-private` (via Git LFS) | Private only | Only with explicit instruction + checksum re-verification | NO, not without explicit instruction |

**Total size of all 3 models:** 66,384,390 bytes (~64 MB).

**Important caveat on Stage 2 V2 (documented honestly, not glossed over):** during the migration, the Stage 2 checkpoint physically present in this project (`action_classifier_v2/best_model.pt`) was checked against the inference code in [`final_demo_inference.py`](backend/app/inference/final_demo_inference.py). That script defines its own `ActionClassifierV2` / `ActWindowEncoder` / `TemporalAttention` classes which **do match** this checkpoint's state-dict keys and shapes — a live smoke test on 2026-10-06 confirmed Stage 2 loads and runs correctly end-to-end against this exact file (see §17 change log and the smoke-test result below). This is a **different, incompatible checkpoint** from the one that was running in the old `D:\2nd Try Major project\System\backend\` project (`stage2_subtype/best_model.pt`, MD5 `9babdfea0956ca61a47a9a0c88800e9c`) — that one uses different layer names (`window_encoder.fc`, `attention.fc1/fc2`) and a different GRU hidden size (96 vs 128), and is **not** interchangeable with the file in this project. SENTINEL-X's authoritative Stage 2 is `action_classifier_v2` / V2, paired with the matching architecture code already present in `final_demo_inference.py`. **Do not** pull in the old System's `stage2_subtype` checkpoint as a "newer" or "better" replacement without explicit instruction — the two are from different training runs and are not drop-in compatible with each other's code.

## 5. MODEL ARCHITECTURE NOTES

### Stage 1 — Final Binary Detector V1

```
WindowEncoder (BinWindowEncoder in code):
  Conv1d(1024 → 512, kernel_size=3)
  squeeze
  Linear(512 → 256)
  ReLU
GatedAttentionMIL:
  V, U: Linear(256 → 128)
  attention: Linear(128 → 1)
  masked softmax over windows
Classifier:
  Linear(256 → 128) → ReLU → Dropout(0.3) → Linear(128 → 2)
```

Historical locked evaluation (as recorded in the original training run, not independently re-verified from scratch in this session beyond the live smoke test in §17):

| Metric | Value |
|---|---|
| Best validation F1 | 0.8443 (epoch 11) |
| Test accuracy | 0.8069 |
| Precision | 0.7530 |
| Recall | 0.8929 |
| F1 | 0.8170 |
| ROC-AUC | 0.8931 |
| Confusion matrix | [[109, 41], [15, 125]] |
| Locked decision threshold | 0.50 |

### Stage 2 — Action Classifier V2

```
13 anomaly classes (Normal excluded; this stage only runs when Stage 1 flags Anomaly)
WindowEncoder (ActWindowEncoder in code):
  Conv1d(1024 → 512, kernel_size=3)
  squeeze
  Linear(512 → 256)
  ReLU
BiGRU:
  input 256, hidden 128, 1 layer, bidirectional
TemporalAttention:
  Linear(256 → 128) → Tanh → Linear(128 → 1)
  masked softmax over windows
Classifier:
  Linear(256 → 128) → ReLU → Dropout(0.3) → Linear(128 → 13)
```

Historical metrics (from the checkpoint's own `final_metrics.json` at its original source location):

| Metric | Value |
|---|---|
| Best validation macro F1 | 0.3042 (epoch 11) |
| Test accuracy | 0.3571 |
| Test macro F1 | 0.2634 |
| Test macro ROC-AUC | 0.7445 |

**IMPORTANT:** Stage 2 V2 (`action_classifier_v2`) is the intentionally selected authoritative Stage 2 model for this clean SENTINEL-X project. There was a later, different Stage 2 checkpoint (informally "V3" in the architecture's docstrings) living in the old `D:\2nd Try Major project\System\backend\models\stage2_subtype\` — that model is **not** part of SENTINEL-X and must not be substituted in without explicit future instruction.

## 6. INFERENCE CODE INVENTORY

### `final_demo_inference.py`

Path: `D:\SENTINEL-X\backend\app\inference\final_demo_inference.py`

Contains the complete runtime needed for both model stages: architecture definitions, model loading, preprocessing, and the end-to-end inference pipeline. Verified classes/functions actually present in the file (inspected directly, 2026-10-06):

Classes:
- `BinWindowEncoder` (nn.Module) — Stage 1 window encoder
- `GatedAttentionMIL` (nn.Module) — Stage 1 attention pooling
- `MILClassifier` (nn.Module) — Stage 1 full model
- `ActWindowEncoder` (nn.Module) — Stage 2 window encoder
- `TemporalAttention` (nn.Module) — Stage 2 attention pooling
- `ActionClassifierV2` (nn.Module) — Stage 2 full model

Functions:
- `sample_video_frames_sequential(video_path, fps_sample, img_size)` — frame sampling
- `build_window_tensor(frames, start, window_frames)` — builds one temporal window
- `build_window_starts(n_frames, window_frames, ...)` — computes window start indices ("Strategy B" sampling)
- `extract_i3d_features(i3d_model, frames, window_starts, device, batch_size)` — runs I3D over all windows
- `run_binary_detector(mil_model, i3d_features, device)` — Stage 1 forward pass
- `run_action_classifier(action_model, i3d_features, device)` — Stage 2 forward pass
- `main()` — CLI entrypoint, takes a video path and optional expected-class argument

Model paths are resolved relative to `backend/models/` (updated 2026-10-06 migration fix — see §17). `CALIBRATION_PATH` (an optional `threshold_calibration.json` under `stage1_binary/`) is read defensively with `os.path.isfile()` and is **not currently present** in this project; the script falls back to a 0.50 decision threshold when it's absent.

### `pytorch_i3d.py`

Path: `D:\SENTINEL-X\backend\app\inference\pytorch_i3d.py`

Purpose: defines the I3D (Inflated 3D ConvNet) backbone architecture that `rgb_imagenet.pt` loads its weights into. This is the architecture code the weights depend on — the `.pt` file alone is just tensors; this file defines what shape of model they populate.

Classes found: `MaxPool3dSamePadding`, `Unit3D`, `InceptionModule`, `InceptionI3d`.

Dependencies: `torch`, `torch.nn`, `torch.nn.functional`, `torch.autograd.Variable`, `numpy`, plus stdlib (`os`, `sys`, `collections.OrderedDict`). **No local project dependencies** — this file is self-contained and portable.

## 6a. BACKEND ARCHITECTURE (FastAPI)

Added 2026-10-06. A modular-monolith FastAPI backend wraps the existing inference pipeline. No model, architecture, preprocessing, or threshold logic was changed — see the refactor note below.

**`final_demo_inference.py` refactor (minimal, documented in-file):**
- Added `InferencePipeline` class (`load()`, `analyze(video_path) -> InferenceOutput`) extracted directly from the former body of `main()`, same call order, same arguments. `main()` is now a thin CLI wrapper that builds a pipeline, calls `load()` + `analyze()`, and prints the same report as before — the CLI entrypoint (`python final_demo_inference.py video.mp4`) still works identically.
- Added `InferenceOutput`, a plain dataclass (not Pydantic, to keep this file framework-agnostic).
- Added `get_pipeline()`, a module-level singleton accessor.
- Fixed the bare `from pytorch_i3d import InceptionI3d` import by explicitly inserting `SCRIPT_DIR` onto `sys.path` (previously relied on implicit CLI-execution behavior that broke once the file was imported as part of the `app` package).

**Directory layout added under `backend/`:**
```
app/
  main.py                       FastAPI app: lifespan, routers, CORS, global exception handler
  api/routes/health.py          GET /api/health
  api/routes/analysis.py        POST /api/v1/analysis, GET /api/v1/analysis/{job_id}, GET .../result
  core/config.py                Settings dataclass; all paths derived from BACKEND_ROOT
  schemas/analysis.py           AnalysisStatus enum, AnalysisResult/ActionCandidate/ModelInfo (Pydantic)
  services/job_repository.py    JobRepository ABC + InMemoryJobRepository (dict index + JSON write-through)
  services/job_executor.py      JobExecutor ABC + InProcessJobExecutor (wraps FastAPI BackgroundTasks)
  services/analysis_service.py  run_analysis_job(): processing -> inference -> completed/failed
storage/
  uploads/, results/, evidence/ (empty + .gitkeep; gitignored contents via *.mp4/*.json rules as applicable)
.env.example                    ENVIRONMENT, MAX_UPLOAD_SIZE_MB, CORS_ALLOWED_ORIGINS
```

**Model loading strategy:** lazy singleton. `InferencePipeline` is constructed empty at import time (no I/O, no memory use) and `.load()` is called exactly once from FastAPI's `lifespan` context manager at startup. Avoids both per-request reloads and import-time side effects.

**Job execution:** `JobExecutor` interface, backed for this phase by `InProcessJobExecutor` (FastAPI `BackgroundTasks`, in-process). Documented as a single-process/demo-scale strategy; swappable later for a worker-queue-backed executor (Celery/RQ) without changing the route or service layer. Not introduced now.

**Job state:** `JobRepository` interface, backed for this phase by `InMemoryJobRepository` (dict index + write-through JSON persistence to `storage/results/{job_id}.json` on every create/update). Includes a documented-but-unused `rebuild_from_disk()` stub and a `# TODO(startup-rehydrate)` marker as the extension point for rebuilding the in-memory index from disk on a future startup hook. Swappable later for a SQLite-backed implementation without changing the interface. Not introduced now.

**API endpoints:**
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | App liveness + `inference_ready` (models loaded) |
| POST | `/api/v1/analysis` | Upload a video, returns `202` + `job_id` |
| GET | `/api/v1/analysis/{job_id}` | Current job status/record |
| GET | `/api/v1/analysis/{job_id}/result` | Completed result only (409 if not yet completed) |
| GET | `/docs`, `/redoc` | FastAPI auto-generated API docs |

**Verified end-to-end (2026-10-06):** uploaded `test_videos/Abuse/Abuse021_x264.mp4` through the live HTTP API end-to-end. Result: `anomaly_detected=true`, `anomaly_probability=97.80%`, `likely_action=Abuse`, `action_confidence=57.20%` — matching the standalone CLI smoke test. `storage/results/{job_id}.json` confirmed written to disk.

**Known limitations (disclosed, not yet addressed):**
- In-memory job index is lost on process restart; JSON result files on disk survive, but startup rehydration is not wired in yet (`rebuild_from_disk()` exists but is unused).
- No auth or rate-limiting on the upload endpoint.
- `BackgroundTasks` runs in-process; fine at single-user/demo scale (~37–44s per video observed), not at concurrent multi-user scale.

## 6b. YOLO26-S SUPPORTING VISION LAYER

Added 2026-10-06. A second, independent computer-vision layer — object detection and multi-object
tracking via the official Ultralytics YOLO26-S pretrained model — added alongside the
authoritative anomaly pipeline above. Additive only: never merged with, never retrains, never
replaces the I3D/Stage1/Stage2 models. Full detail, API reference, performance benchmark, and
disclosed limitations: see [`docs/YOLO26.md`](docs/YOLO26.md).

Summary: `backend/app/inference/yolo26_service.py` (singleton `YOLO26Service`, loaded once at
startup, CUDA with CPU fallback), `backend/app/inference/geometry.py` (zone/line-crossing pure
functions), `backend/app/schemas/yolo.py`, `backend/app/services/yolo_job_service.py`, new routes
under `/api/v1/yolo/*` registered alongside the existing routers. Weights cached at
`backend/models/yolo26/yolo26s.pt` (gitignored, separate from the three locked checkpoints).
Reuses the existing `JobRepository`/`JobExecutor` abstractions verbatim — no second job system.
Verified end-to-end on 2026-10-06: real detection and tracking against
`test_videos/Abuse/Abuse021_x264.mp4` (26 distinct tracks, real `person`/`bicycle` detections),
20/20 tests passing, benchmarked at 20.87 FPS detect / 15.95 FPS track on the RTX 3050 6GB, and
the existing `/api/v1/analysis` flow re-verified to produce identical output (97.80%/Abuse/57.20%)
confirming zero regression.

## 7. TEST VIDEO INVENTORY

Verified directly against the filesystem, 2026-10-06:

| Class | Expected | Actual |
|---|---|---|
| Abuse | 7 | 7 |
| Arrest | 7 | 7 |
| Arson | 7 | 7 |
| Burglary | 7 | 7 |
| Explosion | 7 | 7 |
| Fighting | 7 | 7 |
| Normal | 7 | 7 |
| RoadAccidents | 7 | 7 |
| Robbery | 7 | 7 |
| Shooting | 4 | 4 |
| Shoplifting | 7 | 7 |
| Vandalism | 7 | 7 |
| **Total** | **81** | **81** |

- Actual total `.mp4` count: 81 (confirmed via `find -iname "*.mp4" | wc -l`)
- All 81 files have the `.mp4` extension; no other video formats present
- Total size: 1,694,741,881 bytes (~1.6 GB)
- Unexpected files in `test_videos/`: only `test_videos/README.md` (added for the public repo, documents the exclusion — not a video, not a migration artifact)
- No individual class folder has an unexpected count

**Original source:** `D:\2nd Try Major project\System\train_videos_sample\<ClassName>\*.mp4`

**Confirmed by filesystem check (not assumed):** the original source directory now contains **zero** `.mp4` files (`find ... -iname "*.mp4" | wc -l` → `0`). This confirms the migration was a true **move**, not a copy — the 81 videos exist only in `D:\SENTINEL-X\test_videos\` now. The source directory still retains its own `run_train_sample_check.py` and `train_sample_results.csv`, which were deliberately left behind (not part of the migration scope).

## 8. ASSET MIGRATION HISTORY

**Models (moved 2026-10-06):**

| Source | Destination |
|---|---|
| `C:\Users\Gulabaji\ucf_crime_demo\final_binary_detector_v1\best_model.pt` | `D:\SENTINEL-X\backend\models\stage1_binary\best_model.pt` |
| `C:\Users\Gulabaji\ucf_crime_demo\action_classifier_v2\best_model.pt` | `D:\SENTINEL-X\backend\models\stage2_action\best_model.pt` |
| `C:\Users\Gulabaji\ucf_crime_demo\pytorch-i3d\models\rgb_imagenet.pt` | `D:\SENTINEL-X\backend\models\i3d\rgb_imagenet.pt` |

**Runtime source files (moved 2026-10-06):**

| Source | Destination |
|---|---|
| `C:\Users\Gulabaji\ucf_crime_demo\pytorch-i3d\pytorch_i3d.py` | `D:\SENTINEL-X\backend\app\inference\pytorch_i3d.py` |
| `C:\Users\Gulabaji\ucf_crime_demo\final_demo_inference.py` | `D:\SENTINEL-X\backend\app\inference\final_demo_inference.py` |

**Videos (moved 2026-10-06):**

- Source: `D:\2nd Try Major project\System\train_videos_sample\<ClassName>\*.mp4` (81 files across 12 class folders)
- Destination: `D:\SENTINEL-X\test_videos\<ClassName>\*.mp4`

All of the above were **true moves** (verified empty source paths for the models/scripts; verified zero remaining `.mp4` files in the video source directory), not copies. Confirmed via filesystem checksums matching between pre-move and post-move states at the time of migration.

**Explicitly NOT touched, modified, or used as a source during this migration:**
- `D:\2nd Try Major project\System\backend\`
- `D:\2nd Try Major project\WORKING_SYSTEM_GOLDEN_BACKUP\`

## 9. PUBLIC GITHUB REPOSITORY

| Field | Value |
|---|---|
| Repository | `rahulgulabaji/SENTINEL-X` |
| URL | https://github.com/rahulgulabaji/SENTINEL-X |
| Visibility | **PUBLIC** |
| Branch | `main` |
| Initial commit | `9fea967` — "Initial public SENTINEL-X project" |
| Tag | `v1.0.0` |
| Purpose | Public portfolio / showcase / source-code repository |

**Expected contents:** source code, documentation, README, configuration templates, evaluation information, architecture notes. (Frontend, screenshots, and diagrams are planned but not yet present.)

**Must never contain:** `.pt`, `.pth`, `.ckpt`, `.onnx`, `.safetensors`, `.mp4`, private datasets, credentials, API keys, `.env` secrets, private backup files.

**Current tracked files** (verified via `git ls-files`, 2026-10-06): `.gitignore`, `README.md`, `backend/app/inference/final_demo_inference.py`, `backend/app/inference/pytorch_i3d.py`, `backend/models/README.md`, `backend/requirements.txt`, `test_videos/README.md`.

**Audit result (re-verified 2026-10-06, not assumed):**
- Model files publicly included: **NO**
- Videos publicly included: **NO**
- Secrets detected: **NO** (scanned tracked file contents for key/secret/password/token/private-key patterns)
- Old project path references detected: **NO** (scanned for `ucf_crime_demo`, `2nd Try Major project`, `WORKING_SYSTEM_GOLDEN_BACKUP`, `Gulabaji`)

## 10. PRIVATE GITHUB REPOSITORY

| Field | Value |
|---|---|
| Repository | `rahulgulabaji/SENTINEL-X-private` |
| URL | https://github.com/rahulgulabaji/SENTINEL-X-private |
| Visibility | **PRIVATE** |
| Branch | `main` |
| Initial commit | `3bdd080` — "Initial protected model and test data backup" |
| Tag | `v1.0.0-assets` |
| Purpose | Protected remote backup for trained model checkpoints and test videos |

**Contents:** 3 model checkpoints + 81 test videos, tracked via Git LFS.

**Verified LFS file count** (via `git lfs ls-files`, 2026-10-06): **84 files** (3 models + 81 videos).

**Total protected size:** 1,761,126,271 bytes (~1.7 GB)
- Models: 66,384,390 bytes (~64 MB)
- Videos: 1,694,741,881 bytes (~1.6 GB)

## 11. LOCAL PRIVATE STAGING

Location: `D:\SENTINEL-X-private-staging`

Status: Contains a local git repository + working copy of the 3 models and 81 videos, used to prepare and push the private GitHub backup. This directory is **separate from `D:\SENTINEL-X`** and is not part of the active project tree.

**Status: Pending explicit cleanup decision.** Do not delete this directory automatically. It will be removed, archived, or kept only when the user explicitly instructs it.

## 12. OLD PROJECTS / DO NOT TOUCH

> ⚠️ **The following locations are historical/legacy and MUST NOT be used as a source for SENTINEL-X unless explicitly instructed otherwise:**
>
> - `D:\2nd Try Major project\System\`
> - `D:\2nd Try Major project\WORKING_SYSTEM_GOLDEN_BACKUP\`

Also historical (origin of the model/runtime files that were moved out, now largely emptied of those specific files):

- `C:\Users\Gulabaji\ucf_crime_demo\`

**Specifically documented:** the old `System\backend\` contains a **different** Stage 2 checkpoint (`models/stage2_subtype/best_model.pt`, MD5 `9babdfea0956ca61a47a9a0c88800e9c`) with a different architecture (different layer names, different GRU hidden size) than the one used in SENTINEL-X. That checkpoint is **not** the authoritative Stage 2 model for this project. **SENTINEL-X uses `action_classifier_v2` / `best_model.pt`** (MD5 `3e3753abfd0caeffd6f65194feb6e58b`), paired with the matching `ActionClassifierV2` architecture already present in `final_demo_inference.py`.

Do not casually copy code, models, or data from any old system into SENTINEL-X. If a future need arises to pull something from the old locations, verify checksums and compatibility first, and update this document.

## 13. SOURCE OF TRUTH RULES

1. `D:\SENTINEL-X` is the clean, active project.
2. The three model files currently inside `D:\SENTINEL-X\backend\models\` are authoritative.
3. Do not replace them with similarly-named files from old projects.
4. Stage 2 V2 (`action_classifier_v2`) is authoritative.
5. Do not use the old Stage 2 "V3" checkpoint from `System\backend\models\stage2_subtype\`.
6. Do not touch `WORKING_SYSTEM_GOLDEN_BACKUP\`.
7. Do not expose models or videos in the public GitHub repo (`SENTINEL-X`).
8. Private assets belong in `SENTINEL-X-private`.
9. Public source code belongs in `SENTINEL-X`.
10. Before moving, replacing, or deleting a model, verify its checksum and update this document.
11. Before changing repository contents, update this document if the change affects protected assets.
12. Never retrain or overwrite an authoritative checkpoint accidentally.
13. Keep test videos private (not in the public repo).
14. Never commit credentials or secrets.
15. Never assume a similarly-named file is equivalent to an authoritative file — check the MD5.

## 14. FUTURE PROJECT STRUCTURE

Updated 2026-10-06: `app/api/`, `app/services/`, `app/core/`, `app/schemas/`, and `storage/` now **EXIST** (see §6a for details) — the FastAPI backend has been implemented. The items below remain planned/not yet built:

```
backend/
  app/
    inference/      [EXISTS]
    api/             [EXISTS — see §6a]
    core/            [EXISTS — see §6a]
    schemas/         [EXISTS — see §6a]
    services/        [EXISTS — see §6a]
    database/        PLANNED — NOT CURRENTLY PRESENT (SQLite-backed JobRepository)
  models/            [EXISTS]
  storage/           [EXISTS — see §6a]
  requirements.txt   [EXISTS]

frontend/            PLANNED — NOT CURRENTLY PRESENT
docs/                PLANNED — NOT CURRENTLY PRESENT (architecture diagrams, screenshots)
Celery/RQ worker     PLANNED — NOT CURRENTLY PRESENT (future JobExecutor implementation)
```

Do not create the remaining directories until actually implementing them; this section is documentation of intent only.

## 15. DEPENDENCY / ENVIRONMENT NOTES

Confirmed dependencies, from `backend/requirements.txt` (based on the versions actually installed in the development environment at the time of migration):

```
torch==2.9.1
numpy==2.1.3
opencv-python==4.10.0.84
```

Development environment notes (confirmed, not assumed): developed and smoke-tested on Python 3.13.15, with CPU-based inference verified working. A CUDA-capable GPU (NVIDIA RTX 3050 6GB Laptop GPU) is available on the development machine but inference does not require it — `final_demo_inference.py` runs on CPU.

No FastAPI/API-layer dependencies are confirmed yet since no API code exists in this project (see §14). Runtime dependency manifest beyond the three packages above is not yet finalized.

## 16. CHECKSUM / INTEGRITY TABLE

Re-verified directly against the filesystem, 2026-10-06:

| Asset | Path | Size | MD5 | Status |
|---|---|---|---|---|
| Stage 1 model | `backend/models/stage1_binary/best_model.pt` | 7,220,514 bytes | `125ff7847dfc663567528f3d62fc5a9d` | Authoritative |
| Stage 2 model | `backend/models/stage2_action/best_model.pt` | 8,280,738 bytes | `3e3753abfd0caeffd6f65194feb6e58b` | Authoritative |
| I3D backbone | `backend/models/i3d/rgb_imagenet.pt` | 50,883,138 bytes | `591830edb0dc9c0b1298a326ca9bd3cc` | Authoritative |
| Test videos (81 files) | `test_videos/<Class>/*.mp4` | 1,694,741,881 bytes total | Not individually recorded | Authoritative set — see note below |

Individual per-video checksums are not currently recorded; generating 81 individual MD5s was judged excessive for this inventory. The aggregate count (81) and total size (1,694,741,881 bytes) are the integrity reference. If individual video integrity verification is ever needed, that can be generated as a one-time manifest and added here.

## 17. GIT / VERSION HISTORY

| Tag | Repository | Represents |
|---|---|---|
| `v1.0.0` | Public (`SENTINEL-X`) | First public portfolio version — source code and documentation only, no protected assets |
| `v1.0.0-assets` | Private (`SENTINEL-X-private`) | First protected asset backup — 3 model checkpoints + 81 test videos via Git LFS |

**Post-migration verification (2026-10-06):** after moving `final_demo_inference.py` and `pytorch_i3d.py` into `backend/app/inference/`, the script's hardcoded model paths (originally written for the old flat `ucf_crime_demo/` layout) were updated to resolve against `backend/models/{i3d,stage1_binary,stage2_action}/`, and the now-unnecessary `sys.path.insert` for `pytorch_i3d` was removed since both files now live in the same directory. A live smoke test was then run:

```
Video: Abuse021_x264.mp4
I3D: 240 sampled frames → 32 temporal windows → feature shape (32, 1024, 3)
Stage 1: ANOMALY — 97.80% (attention weights sum to 1.000000, as expected)
Stage 2: Abuse — 57.20% confidence (top prediction matched the video's ground-truth class)
Processing time: 44.14s (CPU)
Result: PASS
```

This confirms both stages load their checkpoints successfully and produce coherent output end-to-end from the migrated project layout. No model weights, no architecture, and no training were touched during this fix or test.

## 18. CHANGE LOG

### 2026-10-06
- Created project inventory (this document).
- Clean SENTINEL-X structure established at `D:\SENTINEL-X`.
- Three authoritative model checkpoints migrated (moved, not copied) from `C:\Users\Gulabaji\ucf_crime_demo\`.
- 81 test videos migrated (moved, not copied) from `D:\2nd Try Major project\System\train_videos_sample\`.
- Public repository (`rahulgulabaji/SENTINEL-X`) established without protected assets.
- Private repository (`rahulgulabaji/SENTINEL-X-private`) established with protected assets via Git LFS.
- Public tag `v1.0.0` created.
- Private asset tag `v1.0.0-assets` created.
- Legacy `System\` and `WORKING_SYSTEM_GOLDEN_BACKUP\` explicitly excluded from the clean project; confirmed untouched.
- Fixed stale hardcoded model paths in `final_demo_inference.py` post-migration; verified both Stage 1 and Stage 2 load and run correctly via a live smoke test against `Abuse021_x264.mp4`.
- Implemented the first FastAPI backend (modular monolith: `api/`, `core/`, `schemas/`, `services/`, `inference/`) wrapping the existing inference pipeline. Minimal, documented refactor of `final_demo_inference.py` (added `InferencePipeline`/`InferenceOutput`/`get_pipeline()`, fixed a bare import that broke under package-style loading); no architecture/weights/thresholds changed. Added `JobExecutor`/`JobRepository` abstractions (in-process + in-memory/JSON for this phase, documented as swappable). Verified end-to-end via the live HTTP API against `Abuse021_x264.mp4` (97.80% anomaly, 57.20% Abuse — matching the CLI smoke test). See §6a for full details.
- Added the YOLO26-S supporting vision layer (object detection + ByteTrack multi-object tracking), additive to and fully independent from the anomaly pipeline. New files only under `backend/app/inference/{yolo26_service,geometry}.py`, `backend/app/schemas/yolo.py`, `backend/app/services/yolo_job_service.py`, `backend/app/api/routes/yolo.py`; reused the existing `JobRepository`/`JobExecutor` abstractions rather than forking a second job system. Pinned `ultralytics==8.4.137` (already installed, not a blind add). Verified end-to-end: real single-frame/video detection and tracking against `Abuse021_x264.mp4`, 20/20 tests passing (`backend/tests/test_yolo26.py`), benchmarked on the RTX 3050 6GB (20.87 FPS detect, 15.95 FPS track, 100MB peak VRAM), and re-ran `/api/v1/analysis` end-to-end afterward confirming zero regression (identical 97.80%/Abuse/57.20% result). Three locked checkpoints confirmed byte-identical via SHA-256 before and after. See §6b and `docs/YOLO26.md` for full details.

### Future entries go below this line.

## 19. QUICK REFERENCE

```
ACTIVE PROJECT:          D:\SENTINEL-X
PUBLIC REPO:             rahulgulabaji/SENTINEL-X
PRIVATE ASSET REPO:      rahulgulabaji/SENTINEL-X-private
AUTHORITATIVE MODELS:    D:\SENTINEL-X\backend\models\
TEST VIDEOS:             D:\SENTINEL-X\test_videos\
AUTHORITATIVE STAGE 2:   action_classifier_v2 / V2
BACKEND START COMMAND:   cd backend && uvicorn app.main:app --port 8000
API DOCS (when running): http://127.0.0.1:8000/docs

DO NOT TOUCH:
  D:\2nd Try Major project\System\
  D:\2nd Try Major project\WORKING_SYSTEM_GOLDEN_BACKUP\

PUBLIC REPO CONTAINS:    CODE ONLY
PRIVATE REPO CONTAINS:   MODELS + 81 TEST VIDEOS (via Git LFS)
```
