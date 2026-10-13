#!/usr/bin/env python3
"""
probe.py -- READ-ONLY temporal-localization diagnostic experiment.

Does NOT modify any production file, does NOT retrain or save any model
weights. Only writes output under D:\\SENTINEL-X\\diagnostics\\temporal_experiment\\.

Reuses the exact production preprocessing / model classes / loading code
from backend/app/inference/final_demo_inference.py by importing it directly,
so feature extraction, windowing, and model forward passes are byte-for-byte
identical to production. No logic from that file is re-implemented here.

Experiment:
  For subsequence lengths L in [4, 8, 16, 32], slide a NON-OVERLAPPING
  window of L consecutive temporal-windows (stride = L) across the full
  N-window sequence of I3D features for one video, and run the REAL Stage1
  (MILClassifier) and Stage2 (ActionClassifierV2) forward passes on each
  slice to see whether anomaly probability / predicted action vary in a
  meaningful, stable way across time -- i.e. whether there is any usable
  temporal localization signal in checkpoints that were only ever trained
  on whole-video window sequences (32-256 windows), never on short slices.
"""

import os
import sys
import json
import time

import numpy as np
import torch

# ---------------------------------------------------------------------------
# Import the production module directly (no re-implementation).
# ---------------------------------------------------------------------------
BACKEND_DIR = r"D:\SENTINEL-X\backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.inference import final_demo_inference as fdi  # noqa: E402

DIAG_DIR = r"D:\SENTINEL-X\diagnostics\temporal_experiment"
VIDEO_PATH = r"D:\SENTINEL-X\test_videos\Abuse\Abuse021_x264.mp4"

SUBSEQ_LENGTHS = [4, 8, 16, 32]
STRIDE_MODE = "non-overlapping (stride = L)"  # documented choice, see module docstring


def run_stage1_on_slice(mil_model, feat_slice, device):
    """Real Stage1 MILClassifier forward on an arbitrary-length [L, 1024, 3]
    feature slice. Mirrors fdi.run_binary_detector() exactly, just generalized
    to accept a slice instead of the full N-window feature array."""
    n_windows = feat_slice.shape[0]
    features_t = torch.from_numpy(feat_slice).float().unsqueeze(0).to(device)  # [1, L, 1024, 3]
    mask = torch.ones((1, n_windows), dtype=torch.bool, device=device)
    with torch.no_grad():
        logits = mil_model(features_t, mask)
        probs = torch.softmax(logits, dim=1)
    anomaly_probability = probs[0, 1].item()
    return anomaly_probability


def run_stage2_on_slice(action_model, feat_slice, device):
    """Real Stage2 ActionClassifierV2 forward on an arbitrary-length slice.
    Mirrors fdi.run_action_classifier() exactly."""
    n_windows = feat_slice.shape[0]
    features_t = torch.from_numpy(feat_slice).float().unsqueeze(0).to(device)
    mask = torch.ones((1, n_windows), dtype=torch.bool, device=device)
    with torch.no_grad():
        logits = action_model(features_t, mask)
        probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()
    return probs


def main():
    os.makedirs(DIAG_DIR, exist_ok=True)

    log_lines = []

    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    log("=" * 70)
    log("TEMPORAL LOCALIZATION PROBE (read-only diagnostic)")
    log("=" * 70)
    log(f"Video: {VIDEO_PATH}")
    log(f"Backend dir (sys.path): {BACKEND_DIR}")
    log(f"final_demo_inference module file: {fdi.__file__}")
    log(f"FPS_SAMPLE={fdi.FPS_SAMPLE}  WINDOW_FRAMES={fdi.WINDOW_FRAMES}  "
        f"DEFAULT_THRESHOLD={fdi.DEFAULT_THRESHOLD}")
    log(f"ACTION_CLASSES={fdi.ACTION_CLASSES}")
    log("")

    assert os.path.isfile(VIDEO_PATH), f"Video not found: {VIDEO_PATH}"

    # -----------------------------------------------------------------
    # 1. Load models exactly as production does (InferencePipeline.load())
    # -----------------------------------------------------------------
    t_load0 = time.time()
    pipeline = fdi.InferencePipeline()
    pipeline.load()
    t_load1 = time.time()
    log(f"Loaded I3D + Stage1 + Stage2 checkpoints in {t_load1 - t_load0:.2f}s "
        f"on device={pipeline.device}")
    log(f"Stage1 threshold in use: {pipeline.threshold}")
    log("")

    # -----------------------------------------------------------------
    # 2. Baseline: full, unmodified whole-video pipeline (production path)
    # -----------------------------------------------------------------
    log("-" * 70)
    log("BASELINE: full whole-video InferencePipeline.analyze() (production path)")
    log("-" * 70)
    t0 = time.time()
    baseline_output = pipeline.analyze(VIDEO_PATH)
    t1 = time.time()
    log(f"Result: {'ANOMALY' if baseline_output.is_anomaly else 'NORMAL'}")
    log(f"Anomaly probability: {baseline_output.anomaly_probability * 100:.2f}%")
    if baseline_output.is_anomaly:
        log(f"Likely action: {baseline_output.likely_action}")
        log(f"Action confidence: {baseline_output.action_confidence * 100:.2f}%")
        log("Top-3 action candidates:")
        for rank, (cname, p) in enumerate(baseline_output.action_candidates[:3], start=1):
            log(f"  {rank}. {cname:<14s} {p * 100:.2f}%")
    log(f"Sampled frames: {baseline_output.n_sampled_frames}")
    log(f"Temporal windows (N): {baseline_output.n_windows}")
    log(f"I3D feature shape: {baseline_output.feature_shape}")
    log(f"Attention sum (sanity check, should be ~1.0): {baseline_output.attention_sum:.6f}")
    log(f"Elapsed: {t1 - t0:.2f}s")
    log("")

    baseline_record = {
        "video": VIDEO_PATH,
        "anomaly_probability": baseline_output.anomaly_probability,
        "is_anomaly": baseline_output.is_anomaly,
        "likely_action": baseline_output.likely_action,
        "action_confidence": baseline_output.action_confidence,
        "action_candidates": baseline_output.action_candidates,
        "n_sampled_frames": baseline_output.n_sampled_frames,
        "n_windows": baseline_output.n_windows,
        "feature_shape": list(baseline_output.feature_shape),
        "attention_sum": baseline_output.attention_sum,
        "elapsed_seconds": t1 - t0,
    }

    # -----------------------------------------------------------------
    # 3. Reproduce the same sampling / windowing / feature extraction
    #    manually (reusing the exact production functions) so we have
    #    direct access to window_starts and the raw [N,1024,3] feature
    #    array for slicing. This duplicates work the baseline call above
    #    already did internally, but InferencePipeline.analyze() doesn't
    #    expose intermediate window_starts/features, and we are forbidden
    #    from editing final_demo_inference.py to add that -- so we just
    #    call the same free functions again, standalone, exactly as
    #    analyze() does internally.
    # -----------------------------------------------------------------
    log("-" * 70)
    log("Recomputing sampled frames / window_starts / I3D features "
        "(same production functions, standalone call, for slicing)")
    log("-" * 70)

    frames, native_fps, total_native_frames = fdi.sample_video_frames_sequential(VIDEO_PATH)
    n_sampled = len(frames)
    log(f"native_fps={native_fps:.4f}  total_native_frames={total_native_frames}  "
        f"n_sampled_frames={n_sampled}")

    window_starts = fdi.build_window_starts(n_sampled)
    n_windows = len(window_starts)
    log(f"n_windows={n_windows}  window_starts[:5]={window_starts[:5]} "
        f"... window_starts[-5:]={window_starts[-5:]}")

    assert n_windows == baseline_output.n_windows, (
        "Mismatch between standalone recompute and baseline analyze() window "
        "count -- preprocessing is not reproducing identically."
    )

    i3d_features = fdi.extract_i3d_features(
        pipeline.i3d_model, frames, window_starts, pipeline.device
    )
    log(f"i3d_features.shape={i3d_features.shape}")
    assert i3d_features.shape == tuple(baseline_output.feature_shape), (
        "Mismatch between standalone recompute and baseline analyze() feature "
        "shape -- preprocessing is not reproducing identically."
    )
    log("Standalone recompute matches baseline analyze() exactly (n_windows, feature_shape).")
    log("")

    # Approximate per-window center/start/end timestamps.
    # NOTE: window_starts are indices into the SAMPLED-frame sequence
    # (sampled at FPS_SAMPLE), not native-video frame indices. Converting
    # to seconds via start/FPS_SAMPLE is therefore an APPROXIMATION:
    #  - native_fps may not divide evenly by FPS_SAMPLE, so the true
    #    native-frame-time of each sampled frame drifts slightly from
    #    index/FPS_SAMPLE.
    #  - the "step" used in sampling is round(native_fps / FPS_SAMPLE),
    #    which is itself a rounded ratio.
    # This is stated explicitly and only used for human-readable
    # approximate timing in the report, never as ground truth.
    def window_start_seconds(start_idx):
        return start_idx / fdi.FPS_SAMPLE

    def window_end_seconds(start_idx):
        return (start_idx + fdi.WINDOW_FRAMES) / fdi.FPS_SAMPLE

    video_duration_approx_sec = n_sampled / fdi.FPS_SAMPLE
    log(f"Approx. video duration from sampled frames: {video_duration_approx_sec:.2f}s "
        f"(= n_sampled_frames / FPS_SAMPLE, itself approximate)")
    log("")

    # -----------------------------------------------------------------
    # 4. Sliding-subsequence experiment
    # -----------------------------------------------------------------
    log("-" * 70)
    log(f"SLIDING SUBSEQUENCE EXPERIMENT  (stride mode: {STRIDE_MODE})")
    log("-" * 70)

    all_results = {}  # L -> list of subsequence result dicts

    for L in SUBSEQ_LENGTHS:
        stride = L
        subseq_results = []
        n_skipped_trailing = 0

        i = 0
        while i < n_windows:
            j = i + L
            if j > n_windows:
                # Trailing subsequence shorter than L -- skip it and note.
                n_skipped_trailing += 1
                break

            feat_slice = i3d_features[i:j]  # [L, 1024, 3]
            start_window_idx = window_starts[i]
            end_window_idx = window_starts[j - 1]

            t_start_sec = window_start_seconds(start_window_idx)
            t_end_sec = window_end_seconds(end_window_idx)

            anomaly_prob = run_stage1_on_slice(pipeline.mil_model, feat_slice, pipeline.device)
            action_probs = run_stage2_on_slice(pipeline.action_model, feat_slice, pipeline.device)

            top3_idx = np.argsort(action_probs)[::-1][:3]
            top3 = [(fdi.ACTION_CLASSES[idx], float(action_probs[idx])) for idx in top3_idx]
            pred_idx = int(top3_idx[0])

            frac_of_video = (t_end_sec - t_start_sec) / video_duration_approx_sec if video_duration_approx_sec > 0 else None

            subseq_results.append({
                "window_index_range": [int(i), int(j - 1)],
                "approx_start_sec": round(t_start_sec, 3),
                "approx_end_sec": round(t_end_sec, 3),
                "approx_duration_sec": round(t_end_sec - t_start_sec, 3),
                "fraction_of_video": round(frac_of_video, 4) if frac_of_video is not None else None,
                "stage1_anomaly_probability": anomaly_prob,
                "stage2_predicted_class": fdi.ACTION_CLASSES[pred_idx],
                "stage2_top3": top3,
            })

            i += stride

        all_results[L] = {
            "stride": stride,
            "n_subsequences": len(subseq_results),
            "n_skipped_trailing": n_skipped_trailing,
            "subsequences": subseq_results,
        }

        log(f"\nL={L}  stride={stride}  n_subsequences={len(subseq_results)}  "
            f"skipped_trailing={n_skipped_trailing}")
        log(f"{'start_s':>8} {'end_s':>8} {'stage1_p':>9} {'pred_class':>14} {'conf':>7}")
        for r in subseq_results:
            log(f"{r['approx_start_sec']:>8.2f} {r['approx_end_sec']:>8.2f} "
                f"{r['stage1_anomaly_probability']:>9.4f} "
                f"{r['stage2_predicted_class']:>14} "
                f"{r['stage2_top3'][0][1]:>7.4f}")

        probs = [r["stage1_anomaly_probability"] for r in subseq_results]
        classes = [r["stage2_predicted_class"] for r in subseq_results]
        confs = [r["stage2_top3"][0][1] for r in subseq_results]
        if probs:
            log(f"  Stage1 prob: min={min(probs):.4f} max={max(probs):.4f} "
                f"mean={np.mean(probs):.4f} std={np.std(probs):.4f}")
            log(f"  Stage2 unique predicted classes: {sorted(set(classes))}")
            log(f"  Stage2 confidence: min={min(confs):.4f} max={max(confs):.4f} "
                f"mean={np.mean(confs):.4f} std={np.std(confs):.4f}")

    log("")
    log("=" * 70)
    log("DONE")
    log("=" * 70)

    # -----------------------------------------------------------------
    # 5. Write raw results to JSON + Markdown
    # -----------------------------------------------------------------
    results_payload = {
        "video_path": VIDEO_PATH,
        "device": str(pipeline.device),
        "stage1_threshold": pipeline.threshold,
        "fps_sample": fdi.FPS_SAMPLE,
        "window_frames": fdi.WINDOW_FRAMES,
        "n_sampled_frames": n_sampled,
        "native_fps": native_fps,
        "total_native_frames": total_native_frames,
        "n_windows_total": n_windows,
        "video_duration_approx_sec": video_duration_approx_sec,
        "timestamp_note": (
            "approx_start_sec / approx_end_sec are APPROXIMATIONS: window_starts "
            "are indices into the sampled-frame sequence (sampled at FPS_SAMPLE), "
            "not native-video frame indices, and native_fps may not divide evenly "
            "by FPS_SAMPLE. Treat these as rough timing only."
        ),
        "stride_mode": STRIDE_MODE,
        "subsequence_lengths_tested": SUBSEQ_LENGTHS,
        "baseline_whole_video": baseline_record,
        "subsequence_experiment": all_results,
    }

    results_json_path = os.path.join(DIAG_DIR, "results.json")
    with open(results_json_path, "w") as f:
        json.dump(results_payload, f, indent=2)
    log(f"\nWrote {results_json_path}")

    # Markdown table
    md_lines = []
    md_lines.append("# Temporal Localization Probe -- Results\n")
    md_lines.append(f"Video: `{VIDEO_PATH}`\n")
    md_lines.append(f"Device: `{pipeline.device}`  |  Stage1 threshold: `{pipeline.threshold}`\n")
    md_lines.append(f"n_sampled_frames={n_sampled}  n_windows_total={n_windows}  "
                     f"approx_duration_sec={video_duration_approx_sec:.2f}\n")
    md_lines.append(f"Stride mode: {STRIDE_MODE}\n")
    md_lines.append(
        "\n**Timestamp caveat:** start/end seconds are approximations derived "
        "from sampled-frame window indices divided by FPS_SAMPLE "
        f"({fdi.FPS_SAMPLE}); native_fps ({native_fps:.3f}) may not divide "
        "evenly by FPS_SAMPLE, so true native-video timing may drift slightly "
        "from these values.\n"
    )

    md_lines.append("\n## Baseline (full whole-video, production path)\n")
    md_lines.append(f"- Result: {'ANOMALY' if baseline_output.is_anomaly else 'NORMAL'}")
    md_lines.append(f"- Anomaly probability: {baseline_output.anomaly_probability * 100:.2f}%")
    if baseline_output.is_anomaly:
        md_lines.append(f"- Likely action: {baseline_output.likely_action}")
        md_lines.append(f"- Action confidence: {baseline_output.action_confidence * 100:.2f}%")
        md_lines.append("- Top-3: " + ", ".join(
            f"{c} ({p*100:.2f}%)" for c, p in baseline_output.action_candidates[:3]
        ))
    md_lines.append("")

    for L in SUBSEQ_LENGTHS:
        data = all_results[L]
        md_lines.append(f"\n## Subsequence length L={L} (stride={data['stride']}, "
                         f"n_subsequences={data['n_subsequences']}, "
                         f"skipped_trailing={data['n_skipped_trailing']})\n")
        md_lines.append("| start_s | end_s | frac_of_video | stage1_prob | stage2_pred | stage2_conf | top3 |")
        md_lines.append("|---|---|---|---|---|---|---|")
        for r in data["subsequences"]:
            top3_str = "; ".join(f"{c}:{p*100:.1f}%" for c, p in r["stage2_top3"])
            md_lines.append(
                f"| {r['approx_start_sec']:.2f} | {r['approx_end_sec']:.2f} | "
                f"{r['fraction_of_video']:.3f} | {r['stage1_anomaly_probability']:.4f} | "
                f"{r['stage2_predicted_class']} | {r['stage2_top3'][0][1]:.4f} | {top3_str} |"
            )

        probs = [r["stage1_anomaly_probability"] for r in data["subsequences"]]
        classes = [r["stage2_predicted_class"] for r in data["subsequences"]]
        confs = [r["stage2_top3"][0][1] for r in data["subsequences"]]
        if probs:
            md_lines.append(
                f"\nStage1 prob: min={min(probs):.4f} max={max(probs):.4f} "
                f"mean={np.mean(probs):.4f} std={np.std(probs):.4f}\n"
            )
            md_lines.append(f"Stage2 unique predicted classes: {sorted(set(classes))}\n")
            md_lines.append(
                f"Stage2 confidence: min={min(confs):.4f} max={max(confs):.4f} "
                f"mean={np.mean(confs):.4f} std={np.std(confs):.4f}\n"
            )

    results_md_path = os.path.join(DIAG_DIR, "results.md")
    with open(results_md_path, "w") as f:
        f.write("\n".join(md_lines))
    log(f"Wrote {results_md_path}")

    # Also persist the full console log
    log_path = os.path.join(DIAG_DIR, "run_log.txt")
    with open(log_path, "w") as f:
        f.write("\n".join(log_lines))
    log(f"Wrote {log_path}")


if __name__ == "__main__":
    main()
