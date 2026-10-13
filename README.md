# SENTINEL-X

A tactical video intelligence platform for surveillance footage: a two-stage anomaly detection
pipeline, a YOLO object-tracking layer, officer dispatch with SMS alerts and live GPS, an
AI incident copilot, and a full audit trail — wrapped in a FastAPI backend and a React frontend.

```
video
  -> 4 FPS sampling, temporal windowing
  -> I3D (rgb_imagenet backbone) feature extraction
  -> Stage 1: binary MIL attention detector (Normal / Anomaly)
  -> if Anomaly: Stage 2: action subtype classifier (13 classes)
  -> if Anomaly: incident auto-created, dispatch + AI summary available
  -> result
```

A second, independent computer-vision layer (YOLO26-S object detection + multi-object tracking)
runs alongside the anomaly pipeline — additive only, never merged with it, never affects its
output. See [`docs/YOLO26.md`](docs/YOLO26.md).

## Features

**Anomaly detection pipeline**
- Two-stage video classification: binary anomaly detector, then a 13-class action/subtype
  classifier that only runs on clips flagged anomalous.
- Per-window temporal evidence (attention-weighted timeline of *when* in the clip the model's
  confidence rose), surfaced in the frontend's video timeline, not just a single clip-level score.
- Full ranked action-candidate distribution computed per job (not just the top-1 guess).

**YOLO26 vision layer**
- Independent object detection + ByteTrack multi-object tracking (track IDs, movement direction,
  per-track duration) over the same uploaded video.
- Zone and line-crossing event schemas for dwell-time/crossing analytics.

**Incident response**
- Anomaly-flagged jobs auto-create an incident record (open/acknowledged/resolved status).
- Officer dispatch: send an SMS alert (via an Android SMS-gateway bridge, see
  `backend/app/services/sms_gateway.py`) to a specific responder for a given incident, with a
  dispatch preview step before sending.
- Field personnel management: responder roster, duty-session join/resume/end tracking, live GPS
  location feed per on-duty responder, phone-based duty link for officers to self-report location.
- A read-only "live GPS tracker" view plots on-duty responders alongside incident locations on a
  CartoDB Voyager map.

**AI Copilot**
- Grok-backed natural-language incident summarization (`backend/app/services/grok_summary_service.py`),
  with an honest fallback summary when Grok is unavailable/unconfigured — the frontend always
  discloses which source produced a given summary.
- A chat-style AI Copilot panel in the Analysis Workspace for querying the latest incident.

**Audit trail**
- Every dispatch send/preview, responder change, SMS config change, and analysis job
  completion/failure is durably logged (not just kept in browser memory) via a real backend audit
  log, queryable by event type / actor / correlation ID.
- A single, merged, clickable Audit Trail view: click any event for full details (incident
  location with a Maps link, responding officer with a tap-to-call number, confidence, and the
  source clip when it's still available in that browser session) plus the raw JSON record.

**Notifications**
- SMS is the only outbound channel today (gateway config is user-editable at runtime, not just
  via env var) — see `GET/PUT /api/v1/notifications/sms/config`.

**Secure sharing**
- Signed, expiring share links/tokens for handing a responder a scoped duty session without a
  full login (`backend/app/core/share_tokens.py`, `backend/app/api/routes/share.py`).

## Pipeline stages (anomaly detector)

| Stage | Role | Architecture |
|---|---|---|
| I3D | Feature extraction | Inflated 3D ConvNet, ImageNet-pretrained RGB backbone (Carreira & Zisserman, "Quo Vadis") |
| Stage 1 | Binary anomaly detection | I3D features → Conv1d window encoder → Gated Attention MIL → MLP classifier |
| Stage 2 | Action subtype classification (runs only on flagged clips) | I3D features → Conv1d window encoder → BiGRU → Attention pooling → MLP classifier |

Classes recognized by Stage 2: Abuse, Arrest, Arson, Assault, Burglary, Explosion, Fighting, RoadAccidents, Robbery, Shooting, Shoplifting, Stealing, Vandalism.

## Architecture

```
backend/
├── app/
│   ├── main.py                    FastAPI app: lifespan, routers, CORS, exception handling
│   ├── inference/
│   │   ├── final_demo_inference.py   anomaly pipeline entrypoint (I3D + Stage 1 + Stage 2)
│   │   ├── pytorch_i3d.py            I3D backbone architecture
│   │   └── yolo26_service.py         YOLO26 detection + tracking service
│   ├── api/routes/                   health, analysis, yolo, notifications, responders,
│   │                                  dispatch, incidents, audit, share
│   ├── core/                         config, Mongo client, rate limiting, geo helpers,
│   │                                  responder auth/store, share tokens, SMS config store
│   ├── repositories/                  Mongo-backed persistence: jobs, incidents, detection
│   │                                  events, dispatch history, responders, audit log, shares
│   ├── schemas/                       Pydantic request/response models per domain
│   └── services/                      job execution, analysis orchestration, duty sessions,
│                                       Grok/incident summarization, SMS gateway
├── models/                           trained weights — NOT included, see models/README.md
└── requirements.txt

frontend/
└── src/
    ├── App.jsx                       main shell: landing, analysis workspace, duty/GPS
    │                                  tracker, field personnel, audit trail, settings
    ├── components/                   dashboard panel (AI Copilot / detection data tabs),
    │                                  incident-assistant results panel
    ├── hooks/                        useIncidentAssistant (AI summary fetch/refresh)
    └── services/api.js               typed API client

test_videos/                          local evaluation clips — NOT included, see test_videos/README.md
```

## Running it locally

**Backend**
```bash
cd backend
pip install -r requirements.txt
# obtain the three required checkpoints (see backend/models/README.md) and place them
# under backend/models/ as documented there
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

**One-off CLI inference** (no API, just the anomaly pipeline against a single file):
```bash
python backend/app/inference/final_demo_inference.py /path/to/video.mp4
```

The inference pipeline is CPU-capable but considerably faster with a CUDA GPU (developed/tested
on an RTX 3050 6GB laptop GPU). Both the anomaly pipeline and the YOLO26 layer auto-detect CUDA
and fall back to CPU automatically; YOLO's device can also be forced via `YOLO_DEVICE=cpu` in
`backend/.env`.

**Exposing both servers over the internet (zrok tunnels, optional):**
```bash
bash start_tunnels.sh
```
Starts a zrok tunnel for each of the backend (8000) and frontend (5173) dev servers (both must
already be running) and rewrites `backend/.env`, `frontend/.env`, and `frontend/vite.config.ts`
with the new URLs. Restart both dev servers afterward so they pick up the new values.

## API reference

Interactive docs are generated automatically: `http://127.0.0.1:8000/docs` (Swagger) or `/redoc`.

| Router | Prefix | Covers |
|---|---|---|
| Health | `/api/health` | Liveness, model-load status |
| Analysis | `/api/v1/analysis` | Upload a video, poll job status, fetch the anomaly result |
| YOLO26 | `/api/v1/yolo` | Object detection + tracking jobs |
| Notifications | `/api/v1/notifications` | SMS gateway config and connection status |
| Responders | `/api/v1/responders` | Officer roster, duty sessions, GPS location, duty links |
| Dispatch | `/api/v1/dispatch` | Preview/send an SMS alert to a responder for an incident |
| Incidents | `/api/v1/incidents` | Incident records, status, per-job detection events, AI summary |
| Audit | `/api/v1/audit` | Queryable backend audit log |
| Share | `/api/v1/share` | Signed, expiring responder share links |

## Evaluation results

Results below are as reported by the original training runs for each stage. They have not yet been independently re-verified from this repository's checkpoints and are presented for context, not as a guaranteed reproduction.

**Stage 1 — binary anomaly detector**

| Metric | Value |
|---|---|
| Accuracy | 0.807 |
| Precision | 0.753 |
| Recall | 0.893 |
| F1 | 0.817 |
| ROC-AUC | 0.893 |

**Stage 2 — action subtype classifier** (13-class, experimental/secondary signal)

| Metric | Value |
|---|---|
| Accuracy | 0.357 |
| Macro F1 | 0.263 |
| Macro ROC-AUC | 0.744 |

Stage 2's low accuracy reflects both class imbalance and visual similarity between some anomaly subtypes (e.g. Fighting vs. Assault, Shoplifting vs. Stealing); it is intended to surface a "likely action" with a confidence score, not a guaranteed classification.

YOLO26 benchmark (RTX 3050 6GB): 20.87 FPS detect, 15.95 FPS track — see [`docs/YOLO26.md`](docs/YOLO26.md) for full detail.

## Status

Active portfolio project. Backend and frontend are both implemented and wired end-to-end
(anomaly pipeline, YOLO vision layer, dispatch/responders, AI Copilot, audit trail). Persistence
is MongoDB-backed. Planned next: expanded architecture diagrams and demo screenshots.

## License

TBD.
