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

sys.path.insert(0, os.path.join(SCRIPT_DIR, "pytorch-i3d"))
from pytorch_i3d import InceptionI3d  # noqa: E402

I3D_WEIGHTS_PATH = os.path.join(SCRIPT_DIR, "pytorch-i3d", "models", "rgb_imagenet.pt")
BINARY_MODEL_PATH = os.path.join(SCRIPT_DIR, "final_binary_detector_v1", "best_model.pt")
CALIBRATION_PATH = os.path.join(SCRIPT_DIR, "final_binary_detector_v1", "threshold_calibration.json")
ACTION_V2_MODEL_PATH = os.path.join(SCRIPT_DIR, "action_classifier_v2", "best_model.pt")

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
    return probs


# ===========================================================================
# Main
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

    # Decision threshold: from threshold_calibration.json if present, else 0.50
    threshold = DEFAULT_THRESHOLD
    if os.path.isfile(CALIBRATION_PATH):
        with open(CALIBRATION_PATH) as f:
            calib = json.load(f)
        threshold = float(calib.get("selected_threshold", DEFAULT_THRESHOLD))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    t0 = time.time()

    # --- Load models (strictly read-only; checkpoints are never modified) ---
    i3d_model = InceptionI3d(400, in_channels=3)
    i3d_model.load_state_dict(torch.load(I3D_WEIGHTS_PATH, map_location="cpu"))
    i3d_model.to(device)
    i3d_model.eval()

    assert os.path.isfile(BINARY_MODEL_PATH), f"Checkpoint not found: {BINARY_MODEL_PATH}"
    mil_model = MILClassifier(num_classes=BIN_NUM_CLASSES).to(device)
    mil_state_dict = torch.load(BINARY_MODEL_PATH, map_location=device, weights_only=True)
    mil_model.load_state_dict(mil_state_dict)
    mil_model.eval()

    assert os.path.isfile(ACTION_V2_MODEL_PATH), f"Checkpoint not found: {ACTION_V2_MODEL_PATH}"
    action_model = ActionClassifierV2(num_classes=ACT_NUM_CLASSES).to(device)
    action_state_dict = torch.load(ACTION_V2_MODEL_PATH, map_location=device, weights_only=True)
    action_model.load_state_dict(action_state_dict)
    action_model.eval()

    # --- Preprocessing ---
    frames, native_fps, total_native_frames = sample_video_frames_sequential(video_path)
    n_sampled = len(frames)

    if n_sampled == 0:
        print("ERROR: no frames could be sampled from this video.", flush=True)
        sys.exit(1)

    window_starts = build_window_starts(n_sampled)
    n_windows = len(window_starts)

    # --- I3D feature extraction (shared by both models) ---
    i3d_features = extract_i3d_features(i3d_model, frames, window_starts, device)

    # --- Binary detector (single joint MIL forward pass) ---
    anomaly_probability, attn = run_binary_detector(mil_model, i3d_features, device)
    attn_sum = float(attn.sum())
    result = "ANOMALY" if anomaly_probability >= threshold else "NORMAL"

    # --- Action classifier (only if ANOMALY; reuses the same feature tensor) ---
    action_probs = None
    if result == "ANOMALY":
        action_probs = run_action_classifier(action_model, i3d_features, device)

    elapsed = time.time() - t0

    # --- Report ---
    print("=" * 60, flush=True)
    print("VIDEO ANALYSIS", flush=True)
    print("=" * 60, flush=True)
    print(f"Video: {os.path.basename(video_path)}", flush=True)
    print(f"Expected class (if supplied): {expected_class if expected_class else 'N/A'}", flush=True)
    print("", flush=True)
    print(f"Result: {result}", flush=True)
    print(f"Anomaly probability: {anomaly_probability * 100:.2f}%", flush=True)
    print("", flush=True)

    if result == "ANOMALY":
        pred_idx = int(np.argmax(action_probs))
        pred_class = ACTION_CLASSES[pred_idx]
        pred_conf = float(action_probs[pred_idx])

        top3_idx = np.argsort(action_probs)[::-1][:3]

        print(f"Likely action: {pred_class.upper()}", flush=True)
        print(f"Action confidence: {pred_conf * 100:.2f}%", flush=True)
        print("", flush=True)
        print("Top predictions:", flush=True)
        for rank, idx in enumerate(top3_idx, start=1):
            print(f"{rank}. {ACTION_CLASSES[idx]:<14s} {float(action_probs[idx]) * 100:.2f}%", flush=True)
    else:
        print("Action classifier: SKIPPED", flush=True)

    print("", flush=True)
    print("-" * 60, flush=True)
    print(f"Sampled frames: {n_sampled}", flush=True)
    print(f"Temporal windows: {n_windows}", flush=True)
    print(f"I3D feature shape: {tuple(i3d_features.shape)}", flush=True)
    print(f"Binary attention sum (sanity check, should be ~1.0): {attn_sum:.6f}", flush=True)
    print(f"Processing time: {elapsed:.2f} sec", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
