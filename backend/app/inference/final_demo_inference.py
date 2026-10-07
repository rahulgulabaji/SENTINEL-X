#!/usr/bin/env python3
"""
final_demo_inference.py

Local, CPU-based demo inference script for the UCF-Crime two-stage pipeline:

    video
      -> 4 FPS sampling, Strategy B temporal windowing
      -> I3D (rgb_imagenet backbone) feature extraction
      -> locked final_binary_detector_v1 (ONE joint MIL forward pass over all windows)
      -> if ANOMALY: locked action_classifier_v2 on the SAME [N, 1024, 3] feature tensor
      -> print a clean, final report

This script is a read-only inference wrapper around two already-trained,
locked checkpoints. It does NOT train or fine-tune anything, and it never
writes to any checkpoint file. Architectures below are copied verbatim from
the original locked training/inference scripts (21_infer_video.py and
19_train_action_classifier_v2.py / 22_test_integrated_v2.py) -- they are not
reinvented or "simplified" here.

Usage:
    python final_demo_inference.py /path/to/video.mp4
    python final_demo_inference.py /path/to/video.mp4 Abuse   # optional expected class, display only
"""

import os
import sys
import json
import math
import time

import numpy as np
import cv2
import torch
import torch.nn as nn

# ---------------------------------------------------------------------------
# Paths (all relative to this script's own folder, so the demo folder is
# self-contained and relocatable)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# REFACTOR NOTE: SCRIPT_DIR is added to sys.path (rather than using a relative
# `from .pytorch_i3d import ...`) so this module keeps working both when run
# directly as a CLI script (`python final_demo_inference.py video.mp4`, where
# there is no enclosing package) and when imported as part of the `app`
# package by the FastAPI backend.
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from pytorch_i3d import InceptionI3d  # noqa: E402

MODELS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "models"))
I3D_WEIGHTS_PATH = os.path.join(MODELS_DIR, "i3d", "rgb_imagenet.pt")
BINARY_MODEL_PATH = os.path.join(MODELS_DIR, "stage1_binary", "best_model.pt")
CALIBRATION_PATH = os.path.join(MODELS_DIR, "stage1_binary", "threshold_calibration.json")
ACTION_V2_MODEL_PATH = os.path.join(MODELS_DIR, "stage2_action", "best_model.pt")

# ---------------------------------------------------------------------------
# Preprocessing constants ("Strategy B" temporal sampling)
# ---------------------------------------------------------------------------
FPS_SAMPLE = 4
IMG_SIZE = 224
WINDOW_FRAMES = 32

BASE_SEGMENTS = 32
MAX_SPAN_FRAMES = 80
MAX_SEGMENTS_CAP = 256

I3D_BATCH_SIZE = 16  # auto-reduced on CPU memory errors, see extract_i3d_features()

DEFAULT_THRESHOLD = 0.50

# ---------------------------------------------------------------------------
# Binary detector (final_binary_detector_v1) dims
# ---------------------------------------------------------------------------
BIN_WINDOW_EMB_DIM = 256
BIN_ATTN_HIDDEN_DIM = 128
BIN_NUM_CLASSES = 2

# ---------------------------------------------------------------------------
# Action classifier (action_classifier_v2) dims
# ---------------------------------------------------------------------------
ACT_WINDOW_EMB_DIM = 256
ACT_GRU_HIDDEN_DIM = 128
ACT_ATTN_HIDDEN_DIM = 128

ACTION_CLASSES = [
    "Abuse", "Arrest", "Arson", "Assault", "Burglary", "Explosion",
    "Fighting", "RoadAccidents", "Robbery", "Shooting", "Shoplifting",
    "Stealing", "Vandalism",
]
ACT_NUM_CLASSES = len(ACTION_CLASSES)


# ===========================================================================
# Binary detector architecture (locked, verbatim from final_binary_detector_v1
# training / 21_infer_video.py / 22_test_integrated_v2.py)
# ===========================================================================

class BinWindowEncoder(nn.Module):
    def __init__(self, in_channels=1024, conv_out_channels=512, emb_dim=BIN_WINDOW_EMB_DIM):
        super().__init__()
        self.conv = nn.Conv1d(in_channels, conv_out_channels, kernel_size=3)
        self.relu1 = nn.ReLU()
        self.linear = nn.Linear(conv_out_channels, emb_dim)
        self.relu2 = nn.ReLU()

    def forward(self, x):
        x = self.conv(x)
        x = self.relu1(x)
        x = x.squeeze(-1)
        x = self.linear(x)
        x = self.relu2(x)
        return x


class GatedAttentionMIL(nn.Module):
    def __init__(self, emb_dim=BIN_WINDOW_EMB_DIM, hidden_dim=BIN_ATTN_HIDDEN_DIM):
        super().__init__()
        self.V = nn.Linear(emb_dim, hidden_dim)
        self.U = nn.Linear(emb_dim, hidden_dim)
        self.attn = nn.Linear(hidden_dim, 1)

    def forward(self, window_embeddings, mask):
        v = torch.tanh(self.V(window_embeddings))
        u = torch.sigmoid(self.U(window_embeddings))
        attention_logits = self.attn(v * u)
        mask_f = mask.unsqueeze(-1)
        attention_logits = attention_logits.masked_fill(~mask_f, -1e9)
        attention_weights = torch.softmax(attention_logits, dim=1)
        video_embedding = torch.sum(attention_weights * window_embeddings, dim=1)
        return video_embedding, attention_weights


class MILClassifier(nn.Module):
    """Binary (Normal vs Anomaly) joint multi-instance-learning classifier."""

    def __init__(self, num_classes=BIN_NUM_CLASSES):
        super().__init__()
        self.window_encoder = BinWindowEncoder()
        self.attention_pool = GatedAttentionMIL()
        self.classifier = nn.Sequential(
            nn.Linear(BIN_WINDOW_EMB_DIM, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, padded_features, mask):
        B, N_max, feat_dim, temporal_dim = padded_features.shape
        x = padded_features.view(B * N_max, feat_dim, temporal_dim)
        window_embeddings = self.window_encoder(x)
        window_embeddings = window_embeddings.view(B, N_max, BIN_WINDOW_EMB_DIM)
        video_embedding, attention_weights = self.attention_pool(window_embeddings, mask)
        logits = self.classifier(video_embedding)
        return logits


# ===========================================================================
# Action classifier architecture (locked, verbatim from action_classifier_v2
# training / 19_train_action_classifier_v2.py / 22_test_integrated_v2.py)
# Separate weights from the binary detector -- nothing is shared.
# ===========================================================================

class ActWindowEncoder(nn.Module):
    def __init__(self, in_channels=1024, conv_out_channels=512, emb_dim=ACT_WINDOW_EMB_DIM):
        super().__init__()
        self.conv = nn.Conv1d(in_channels, conv_out_channels, kernel_size=3)
        self.relu1 = nn.ReLU()
        self.linear = nn.Linear(conv_out_channels, emb_dim)
        self.relu2 = nn.ReLU()

    def forward(self, x):
        x = self.conv(x)
        x = self.relu1(x)
        x = x.squeeze(-1)
        x = self.linear(x)
        x = self.relu2(x)
        return x


class TemporalAttention(nn.Module):
    def __init__(self, emb_dim=ACT_WINDOW_EMB_DIM, hidden_dim=ACT_ATTN_HIDDEN_DIM):
        super().__init__()
        self.fc1 = nn.Linear(emb_dim, hidden_dim)
        self.tanh = nn.Tanh()
        self.fc2 = nn.Linear(hidden_dim, 1)

    def forward(self, gru_output, mask):
        attention_logits = self.fc2(self.tanh(self.fc1(gru_output)))
        mask_f = mask.unsqueeze(-1)
        attention_logits = attention_logits.masked_fill(~mask_f, -1e9)
        attention_weights = torch.softmax(attention_logits, dim=1)
        video_embedding = torch.sum(attention_weights * gru_output, dim=1)
        return video_embedding, attention_weights


class ActionClassifierV2(nn.Module):
    """13-class action classifier (Normal excluded), run only when ANOMALY."""

    def __init__(self, num_classes=ACT_NUM_CLASSES):
        super().__init__()
        self.window_encoder = ActWindowEncoder()
        self.gru = nn.GRU(
            input_size=ACT_WINDOW_EMB_DIM,
            hidden_size=ACT_GRU_HIDDEN_DIM,
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )
        self.attention_pool = TemporalAttention()
        self.classifier = nn.Sequential(
            nn.Linear(ACT_WINDOW_EMB_DIM, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, padded_features, mask):
        B, N_max, feat_dim, temporal_dim = padded_features.shape
        x = padded_features.view(B * N_max, feat_dim, temporal_dim)
        window_embeddings = self.window_encoder(x)
        window_embeddings = window_embeddings.view(B, N_max, ACT_WINDOW_EMB_DIM)
        gru_output, _ = self.gru(window_embeddings)
        video_embedding, attention_weights = self.attention_pool(gru_output, mask)
        logits = self.classifier(video_embedding)
        return logits


# ===========================================================================
# Preprocessing: frame sampling + Strategy B temporal windowing
# ===========================================================================

def sample_video_frames_sequential(video_path, fps_sample=FPS_SAMPLE, img_size=IMG_SIZE):
    """Open the video, keep every step-th native frame (by running native-frame
    index), resize to img_size x img_size, convert BGR -> RGB."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(native_fps / fps_sample))

    frames = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            frame = cv2.resize(frame, (img_size, img_size))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame)
        idx += 1
    cap.release()

    return frames, native_fps, idx


def build_window_tensor(frames, start, window_frames=WINDOW_FRAMES):
    """32 consecutive sampled frames starting at `start`. If the window runs
    past the end of the sampled-frame list, pad by repeating the LAST
    available sampled frame (no wraparound, no black frames)."""
    F = len(frames)
    window = []
    for t in range(window_frames):
        idx = start + t
        if idx < F:
            window.append(frames[idx])
        else:
            window.append(frames[F - 1])
    window = np.stack(window)
    window = window.astype(np.float32) / 255.0
    window = (window - 0.5) / 0.5
    window = np.transpose(window, (3, 0, 1, 2))  # -> [3, 32, 224, 224]
    return window


def build_window_starts(n_frames, window_frames=WINDOW_FRAMES,
                         base_segments=BASE_SEGMENTS,
                         max_span_frames=MAX_SPAN_FRAMES,
                         max_segments_cap=MAX_SEGMENTS_CAP):
    """Strategy B window start indices, given F sampled frames."""
    F = n_frames
    if F <= 0:
        return []

    if F < window_frames:
        return [0]

    n_windows = max(base_segments, math.ceil(F / max_span_frames))
    n_windows = min(max_segments_cap, n_windows)

    max_start = F - window_frames
    starts = np.linspace(0, max_start, n_windows)
    starts = np.rint(starts).astype(np.int64)
    starts = sorted(set(starts.tolist()))
    return starts


def extract_i3d_features(i3d_model, frames, window_starts, device, batch_size=I3D_BATCH_SIZE):
    """Batch the window tensors through I3D's extract_features(), squeeze the
    two trailing spatial singleton dims, concatenate along dim 0 to get the
    final [N, 1024, 3] tensor for the whole video. Batch size is reduced
    automatically if a memory error is hit (CPU-only, so keep it modest)."""
    n_windows = len(window_starts)
    current_batch_size = max(1, batch_size)

    while True:
        try:
            all_feats = []
            i = 0
            while i < n_windows:
                batch_starts = window_starts[i:i + current_batch_size]
                batch_windows = np.stack([build_window_tensor(frames, s) for s in batch_starts])
                batch_tensor = torch.from_numpy(batch_windows).float().to(device)
                with torch.no_grad():
                    feats = i3d_model.extract_features(batch_tensor)
                    feats = feats.squeeze(-1).squeeze(-1)
                all_feats.append(feats.cpu().numpy())
                i += len(batch_starts)
            return np.concatenate(all_feats, axis=0)
        except (RuntimeError, MemoryError) as e:
            if current_batch_size <= 1:
                raise
            new_batch_size = max(1, current_batch_size // 2)
            print(f"  WARNING: hit memory error at batch_size={current_batch_size} "
                  f"({e}); retrying with batch_size={new_batch_size}", flush=True)
            current_batch_size = new_batch_size


# ===========================================================================
# Model forward passes
# ===========================================================================

@torch.no_grad()
def run_binary_detector(mil_model, i3d_features, device):
    """ONE joint MIL forward pass across ALL temporal windows at once."""
    n_windows = i3d_features.shape[0]
    features_t = torch.from_numpy(i3d_features).float().unsqueeze(0).to(device)  # [1, N, 1024, 3]
    mask = torch.ones((1, n_windows), dtype=torch.bool, device=device)  # all windows real

    logits = mil_model(features_t, mask)
    probs = torch.softmax(logits, dim=1)
    anomaly_probability = probs[0, 1].item()

    # Recompute attention weights for the sanity-check diagnostic (forward()
    # only returns logits, so run the same path manually to get them too).
    B, N_max, feat_dim, temporal_dim = features_t.shape
    x = features_t.view(B * N_max, feat_dim, temporal_dim)
    window_embeddings = mil_model.window_encoder(x)
    window_embeddings = window_embeddings.view(B, N_max, BIN_WINDOW_EMB_DIM)
    _, attention_weights = mil_model.attention_pool(window_embeddings, mask)
    attn = attention_weights.squeeze(0).squeeze(-1).cpu().numpy()

    return anomaly_probability, attn


@torch.no_grad()
def run_action_classifier(action_model, i3d_features, device):
    """Reuses the SAME [N, 1024, 3] feature tensor computed for the binary
    detector -- features are never re-extracted for this second model."""
    n_windows = i3d_features.shape[0]
    features_t = torch.from_numpy(i3d_features).float().unsqueeze(0).to(device)
    mask = torch.ones((1, n_windows), dtype=torch.bool, device=device)

    logits = action_model(features_t, mask)
    probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()

    # Recompute attention weights for temporal-evidence diagnostics (same
    # workaround as run_binary_detector: forward() only returns logits, so
    # run the same path manually to also recover TemporalAttention's
    # per-window weights). This does NOT change the model's prediction --
    # `probs` above is untouched and remains the authoritative whole-video
    # result. These weights describe how much each window contributed to
    # that single whole-video action embedding, not a per-window class.
    B, N_max, feat_dim, temporal_dim = features_t.shape
    x = features_t.view(B * N_max, feat_dim, temporal_dim)
    window_embeddings = action_model.window_encoder(x)
    window_embeddings = window_embeddings.view(B, N_max, ACT_WINDOW_EMB_DIM)
    gru_output, _ = action_model.gru(window_embeddings)
    _, attention_weights = action_model.attention_pool(gru_output, mask)
    attn = attention_weights.squeeze(0).squeeze(-1).cpu().numpy()

    return probs, attn


# ===========================================================================
# InferencePipeline — reusable, framework-agnostic entry point
# ===========================================================================
#
# REFACTOR NOTE (added when wrapping this script in a FastAPI backend):
# The model-loading and per-video analysis logic that used to live inline in
# main() has been extracted into InferencePipeline.load() / .analyze() below,
# unchanged in order and content -- same calls, same arguments, same control
# flow (sample frames -> build window starts -> extract I3D features -> run
# binary detector -> conditionally run action classifier). No architecture,
# preprocessing, threshold, or checkpoint-loading code was changed; this is
# pure control-flow extraction so the pipeline can be called from a long-lived
# process (an API server) instead of only from a one-shot CLI invocation.
# main() below is kept as a thin CLI wrapper that builds a pipeline, calls
# load() + analyze(), and prints the same report as before.
# ===========================================================================

from dataclasses import dataclass, field


def build_temporal_evidence(window_starts, stage1_attn, stage2_attn):
    """Builds the temporal-evidence structure from REAL attention weights
    already produced by the existing whole-video attention-pooling modules
    (GatedAttentionMIL for stage1, TemporalAttention for stage2).

    IMPORTANT: this is NOT per-window classification. Both models were
    trained end-to-end as whole-video sequence classifiers; the single
    `anomaly_probability` / `likely_action` / `action_confidence` produced
    elsewhere remain the only authoritative results. These per-window
    weights only describe how much each window's embedding contributed to
    that one whole-video result (softmax-normalized attention over windows,
    sums to ~1.0 per stage) -- useful as "where did the model look", not
    "what did the model decide about this window".

    stage2_attn is None whenever stage2 did not run (video judged not
    anomalous) -- its per-window fields are then left as None, never
    fabricated.
    """
    n_windows = len(window_starts)
    window_duration_seconds = WINDOW_FRAMES / FPS_SAMPLE

    if n_windows == 0 or stage1_attn is None:
        return {"available": False, "window_duration_seconds": window_duration_seconds, "windows": []}

    stage1_max = float(stage1_attn.max()) if len(stage1_attn) > 0 else 0.0
    stage2_max = float(stage2_attn.max()) if stage2_attn is not None and len(stage2_attn) > 0 else 0.0

    windows = []
    for i, start_idx in enumerate(window_starts):
        start_time_seconds = float(start_idx) / FPS_SAMPLE
        end_time_seconds = float(start_idx + WINDOW_FRAMES) / FPS_SAMPLE

        stage1_weight = float(stage1_attn[i])
        stage1_norm = (stage1_weight / stage1_max) if stage1_max > 0 else 0.0

        stage2_weight = float(stage2_attn[i]) if stage2_attn is not None else None
        stage2_norm = (float(stage2_attn[i]) / stage2_max) if (stage2_attn is not None and stage2_max > 0) else None

        windows.append({
            "window_index": i,
            "start_time_seconds": start_time_seconds,
            "end_time_seconds": end_time_seconds,
            "stage1_attention": stage1_weight,
            "stage1_attention_normalized": stage1_norm,
            "stage2_attention": stage2_weight,
            "stage2_attention_normalized": stage2_norm,
        })

    return {
        "available": True,
        "window_duration_seconds": window_duration_seconds,
        "windows": windows,
    }


@dataclass
class InferenceOutput:
    """Plain dataclass (not a Pydantic schema) so this module stays
    framework-agnostic -- the API layer is responsible for converting this
    into whatever response schema it needs."""

    anomaly_probability: float
    is_anomaly: bool
    attention_sum: float
    likely_action: str | None
    action_confidence: float | None
    action_candidates: list[tuple[str, float]] = field(default_factory=list)
    n_sampled_frames: int = 0
    n_windows: int = 0
    feature_shape: tuple[int, ...] = ()
    elapsed_seconds: float = 0.0
    # Real per-window attention weights from the two existing whole-video
    # attention-pooling modules (GatedAttentionMIL for stage1, TemporalAttention
    # for stage2), mapped to real source-video timestamps. NOT a per-window
    # classification -- see build_temporal_evidence() docstring.
    temporal_evidence: dict | None = None


class InferencePipeline:
    """Loads the I3D backbone + both locked checkpoints once, then runs the
    full two-stage pipeline against a video on demand via analyze().

    Constructing this object does nothing but set attributes to None -- no
    file I/O, no GPU/CPU memory use happens until load() is called. This lets
    a module-level singleton be created at import time safely, with load()
    deferred to an explicit startup hook (FastAPI's lifespan).
    """

    def __init__(self):
        self.device: torch.device | None = None
        self.i3d_model: InceptionI3d | None = None
        self.mil_model: MILClassifier | None = None
        self.action_model: ActionClassifierV2 | None = None
        self.threshold: float = DEFAULT_THRESHOLD
        self.is_loaded: bool = False

    def load(self) -> None:
        """Loads all 3 checkpoints onto self.device. Safe to call once;
        calling again would reload from disk, so callers (the lifespan hook)
        should only call this a single time at startup."""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.threshold = DEFAULT_THRESHOLD
        if os.path.isfile(CALIBRATION_PATH):
            with open(CALIBRATION_PATH) as f:
                calib = json.load(f)
            self.threshold = float(calib.get("selected_threshold", DEFAULT_THRESHOLD))

        i3d_model = InceptionI3d(400, in_channels=3)
        i3d_model.load_state_dict(torch.load(I3D_WEIGHTS_PATH, map_location="cpu"))
        i3d_model.to(self.device)
        i3d_model.eval()
        self.i3d_model = i3d_model

        assert os.path.isfile(BINARY_MODEL_PATH), f"Checkpoint not found: {BINARY_MODEL_PATH}"
        mil_model = MILClassifier(num_classes=BIN_NUM_CLASSES).to(self.device)
        mil_state_dict = torch.load(BINARY_MODEL_PATH, map_location=self.device, weights_only=True)
        mil_model.load_state_dict(mil_state_dict)
        mil_model.eval()
        self.mil_model = mil_model

        assert os.path.isfile(ACTION_V2_MODEL_PATH), f"Checkpoint not found: {ACTION_V2_MODEL_PATH}"
        action_model = ActionClassifierV2(num_classes=ACT_NUM_CLASSES).to(self.device)
        action_state_dict = torch.load(ACTION_V2_MODEL_PATH, map_location=self.device, weights_only=True)
        action_model.load_state_dict(action_state_dict)
        action_model.eval()
        self.action_model = action_model

        self.is_loaded = True

    def analyze(self, video_path: str) -> InferenceOutput:
        """Runs the full pipeline against one video. Raises if load() has not
        been called yet, or if the video can't be opened/sampled."""
        if not self.is_loaded:
            raise RuntimeError("InferencePipeline.analyze() called before load()")

        t0 = time.time()

        frames, native_fps, total_native_frames = sample_video_frames_sequential(video_path)
        n_sampled = len(frames)
        if n_sampled == 0:
            raise RuntimeError("No frames could be sampled from this video.")

        window_starts = build_window_starts(n_sampled)
        n_windows = len(window_starts)

        i3d_features = extract_i3d_features(self.i3d_model, frames, window_starts, self.device)

        anomaly_probability, stage1_attn = run_binary_detector(self.mil_model, i3d_features, self.device)
        attn_sum = float(stage1_attn.sum())
        is_anomaly = anomaly_probability >= self.threshold

        likely_action = None
        action_confidence = None
        action_candidates: list[tuple[str, float]] = []
        stage2_attn = None
        if is_anomaly:
            action_probs, stage2_attn = run_action_classifier(self.action_model, i3d_features, self.device)
            pred_idx = int(np.argmax(action_probs))
            likely_action = ACTION_CLASSES[pred_idx]
            action_confidence = float(action_probs[pred_idx])
            action_candidates = [
                (ACTION_CLASSES[i], float(p)) for i, p in enumerate(action_probs)
            ]
            action_candidates.sort(key=lambda pair: pair[1], reverse=True)

        temporal_evidence = build_temporal_evidence(window_starts, stage1_attn, stage2_attn)

        elapsed = time.time() - t0

        return InferenceOutput(
            anomaly_probability=anomaly_probability,
            is_anomaly=is_anomaly,
            attention_sum=attn_sum,
            likely_action=likely_action,
            action_confidence=action_confidence,
            action_candidates=action_candidates,
            n_sampled_frames=n_sampled,
            n_windows=n_windows,
            feature_shape=tuple(i3d_features.shape),
            elapsed_seconds=elapsed,
            temporal_evidence=temporal_evidence,
        )


_pipeline: InferencePipeline | None = None


def get_pipeline() -> InferencePipeline:
    """Module-level singleton accessor used by the service layer. The
    instance is created on first access (empty, unloaded) and load() is
    expected to be called exactly once by the FastAPI lifespan hook."""
    global _pipeline
    if _pipeline is None:
        _pipeline = InferencePipeline()
    return _pipeline


# ===========================================================================
# Main (CLI entrypoint -- unchanged behavior, now backed by InferencePipeline)
# ===========================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python final_demo_inference.py /path/to/video.mp4 [ExpectedClass]", flush=True)
        sys.exit(1)

    video_path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    expected_class = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(video_path):
        print(f"ERROR: video file not found: {video_path}", flush=True)
        sys.exit(1)

    pipeline = InferencePipeline()
    pipeline.load()
    output = pipeline.analyze(video_path)

    result = "ANOMALY" if output.is_anomaly else "NORMAL"

    # --- Report (same format as before the refactor) ---
    print("=" * 60, flush=True)
    print("VIDEO ANALYSIS", flush=True)
    print("=" * 60, flush=True)
    print(f"Video: {os.path.basename(video_path)}", flush=True)
    print(f"Expected class (if supplied): {expected_class if expected_class else 'N/A'}", flush=True)
    print("", flush=True)
    print(f"Result: {result}", flush=True)
    print(f"Anomaly probability: {output.anomaly_probability * 100:.2f}%", flush=True)
    print("", flush=True)

    if output.is_anomaly:
        print(f"Likely action: {output.likely_action.upper()}", flush=True)
        print(f"Action confidence: {output.action_confidence * 100:.2f}%", flush=True)
        print("", flush=True)
        print("Top predictions:", flush=True)
        for rank, (class_name, prob) in enumerate(output.action_candidates[:3], start=1):
            print(f"{rank}. {class_name:<14s} {prob * 100:.2f}%", flush=True)
    else:
        print("Action classifier: SKIPPED", flush=True)

    print("", flush=True)
    print("-" * 60, flush=True)
    print(f"Sampled frames: {output.n_sampled_frames}", flush=True)
    print(f"Temporal windows: {output.n_windows}", flush=True)
    print(f"I3D feature shape: {output.feature_shape}", flush=True)
    print(f"Binary attention sum (sanity check, should be ~1.0): {output.attention_sum:.6f}", flush=True)
    print(f"Processing time: {output.elapsed_seconds:.2f} sec", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
