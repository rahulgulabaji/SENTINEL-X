# SENTINEL-X

A two-stage video anomaly detection pipeline for surveillance footage. Every clip is run through an I3D feature extractor, then a binary anomaly detector (Normal vs. Anomaly), and — only when flagged as anomalous — a 13-class action/subtype classifier.

```
video
  -> 4 FPS sampling, temporal windowing
  -> I3D (rgb_imagenet backbone) feature extraction
  -> Stage 1: binary MIL attention detector (Normal / Anomaly)
  -> if Anomaly: Stage 2: action subtype classifier (13 classes)
  -> result
```

## Pipeline stages

| Stage | Role | Architecture |
|---|---|---|
| I3D | Feature extraction | Inflated 3D ConvNet, ImageNet-pretrained RGB backbone (Carreira & Zisserman, "Quo Vadis") |
| Stage 1 | Binary anomaly detection | I3D features → Conv1d window encoder → Gated Attention MIL → MLP classifier |
| Stage 2 | Action subtype classification (runs only on flagged clips) | I3D features → Conv1d window encoder → BiGRU → Attention pooling → MLP classifier |

Classes recognized by Stage 2: Abuse, Arrest, Arson, Assault, Burglary, Explosion, Fighting, RoadAccidents, Robbery, Shooting, Shoplifting, Stealing, Vandalism.

## Repository layout

```
backend/
├── app/
│   └── inference/
│       ├── final_demo_inference.py   # end-to-end inference entrypoint (I3D + Stage 1 + Stage 2)
│       └── pytorch_i3d.py            # I3D backbone architecture
├── models/                           # trained weights — NOT included, see models/README.md
└── requirements.txt
test_videos/                          # local evaluation clips — NOT included, see test_videos/README.md
```

## Running inference locally

1. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
2. Obtain the three required checkpoints (see [backend/models/README.md](backend/models/README.md)) and place them under `backend/models/` as documented there.
3. Run against a single video:
   ```bash
   python backend/app/inference/final_demo_inference.py /path/to/video.mp4
   ```

The script is CPU-capable but considerably faster with a CUDA GPU (developed/tested on an RTX 3050 6GB laptop GPU).

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

## Status

This is an active portfolio project. A FastAPI backend, a web frontend, and expanded documentation (architecture diagrams, demo assets) are planned next.

## License

TBD.
