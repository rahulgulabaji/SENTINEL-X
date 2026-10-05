# Model weights (excluded from this repository)

The trained model checkpoints are intentionally **not** committed to this public repository. They are maintained separately in a private backup and are not required to read or evaluate the code here.

## Required files

The inference code expects exactly these three files, in this layout:

```
backend/models/
├── i3d/
│   └── rgb_imagenet.pt
├── stage1_binary/
│   └── best_model.pt
└── stage2_action/
    └── best_model.pt
```

| File | Role | Size |
|---|---|---|
| `i3d/rgb_imagenet.pt` | ImageNet-pretrained I3D RGB backbone used for feature extraction | ~48.5 MB |
| `stage1_binary/best_model.pt` | Stage 1 binary anomaly detector checkpoint | ~6.9 MB |
| `stage2_action/best_model.pt` | Stage 2 action/subtype classifier checkpoint | ~7.9 MB |

## How they're loaded

[`backend/app/inference/final_demo_inference.py`](../app/inference/final_demo_inference.py) resolves these paths relative to its own location and loads each checkpoint with `torch.load(..., weights_only=True)` at the start of inference. No other configuration is needed beyond placing the files at the paths above.

## Obtaining the weights

The checkpoints are kept in a private repository to protect project assets that took real GPU time and curated data to produce. If you're evaluating this project and need access to the weights, reach out directly.
