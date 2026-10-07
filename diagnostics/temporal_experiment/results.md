# Temporal Localization Probe -- Results

Video: `D:\SENTINEL-X\test_videos\Abuse\Abuse021_x264.mp4`

Device: `cuda`  |  Stage1 threshold: `0.5`

n_sampled_frames=240  n_windows_total=32  approx_duration_sec=60.00

Stride mode: non-overlapping (stride = L)


**Timestamp caveat:** start/end seconds are approximations derived from sampled-frame window indices divided by FPS_SAMPLE (4); native_fps (30.000) may not divide evenly by FPS_SAMPLE, so true native-video timing may drift slightly from these values.


## Baseline (full whole-video, production path)

- Result: ANOMALY
- Anomaly probability: 97.81%
- Likely action: Abuse
- Action confidence: 57.21%
- Top-3: Abuse (57.21%), Assault (12.35%), Fighting (8.84%)


## Subsequence length L=4 (stride=4, n_subsequences=8, skipped_trailing=0)

| start_s | end_s | frac_of_video | stage1_prob | stage2_pred | stage2_conf | top3 |
|---|---|---|---|---|---|---|
| 0.00 | 13.00 | 0.217 | 0.4392 | Abuse | 0.4441 | Abuse:44.4%; Assault:13.2%; Fighting:11.6% |
| 6.75 | 19.75 | 0.217 | 0.6414 | Abuse | 0.5137 | Abuse:51.4%; Assault:13.2%; Fighting:9.3% |
| 13.50 | 26.50 | 0.217 | 0.2536 | Abuse | 0.5426 | Abuse:54.3%; Assault:11.9%; Fighting:9.6% |
| 20.25 | 33.25 | 0.217 | 0.4048 | Abuse | 0.4048 | Abuse:40.5%; Assault:16.2%; Vandalism:10.2% |
| 26.75 | 39.75 | 0.217 | 0.9961 | Assault | 0.2203 | Assault:22.0%; Vandalism:14.0%; Abuse:12.5% |
| 33.50 | 46.50 | 0.217 | 0.9978 | Assault | 0.2570 | Assault:25.7%; Abuse:21.1%; Fighting:11.4% |
| 40.25 | 53.25 | 0.217 | 0.2369 | Abuse | 0.2295 | Abuse:22.9%; Assault:21.6%; Vandalism:10.3% |
| 47.00 | 60.00 | 0.217 | 0.0430 | Abuse | 0.2125 | Abuse:21.3%; Assault:16.7%; Fighting:11.2% |

Stage1 prob: min=0.0430 max=0.9978 mean=0.5016 std=0.3289

Stage2 unique predicted classes: ['Abuse', 'Assault']

Stage2 confidence: min=0.2125 max=0.5426 mean=0.3531 std=0.1297


## Subsequence length L=8 (stride=8, n_subsequences=4, skipped_trailing=0)

| start_s | end_s | frac_of_video | stage1_prob | stage2_pred | stage2_conf | top3 |
|---|---|---|---|---|---|---|
| 0.00 | 19.75 | 0.329 | 0.5619 | Abuse | 0.5222 | Abuse:52.2%; Assault:12.8%; Fighting:10.0% |
| 13.50 | 33.25 | 0.329 | 0.3389 | Abuse | 0.5603 | Abuse:56.0%; Assault:12.1%; Fighting:9.2% |
| 26.75 | 46.50 | 0.329 | 0.9975 | Assault | 0.2650 | Assault:26.5%; Abuse:19.1%; Vandalism:12.2% |
| 40.25 | 60.00 | 0.329 | 0.1080 | Abuse | 0.2787 | Abuse:27.9%; Assault:20.3%; Fighting:9.9% |

Stage1 prob: min=0.1080 max=0.9975 mean=0.5016 std=0.3282

Stage2 unique predicted classes: ['Abuse', 'Assault']

Stage2 confidence: min=0.2650 max=0.5603 mean=0.4065 std=0.1355


## Subsequence length L=16 (stride=16, n_subsequences=2, skipped_trailing=0)

| start_s | end_s | frac_of_video | stage1_prob | stage2_pred | stage2_conf | top3 |
|---|---|---|---|---|---|---|
| 0.00 | 33.25 | 0.554 | 0.4646 | Abuse | 0.5918 | Abuse:59.2%; Assault:11.6%; Fighting:8.7% |
| 26.75 | 60.00 | 0.554 | 0.9936 | Abuse | 0.2715 | Abuse:27.1%; Assault:23.7%; Vandalism:10.8% |

Stage1 prob: min=0.4646 max=0.9936 mean=0.7291 std=0.2645

Stage2 unique predicted classes: ['Abuse']

Stage2 confidence: min=0.2715 max=0.5918 mean=0.4316 std=0.1601


## Subsequence length L=32 (stride=32, n_subsequences=1, skipped_trailing=0)

| start_s | end_s | frac_of_video | stage1_prob | stage2_pred | stage2_conf | top3 |
|---|---|---|---|---|---|---|
| 0.00 | 60.00 | 1.000 | 0.9781 | Abuse | 0.5721 | Abuse:57.2%; Assault:12.3%; Fighting:8.8% |

Stage1 prob: min=0.9781 max=0.9781 mean=0.9781 std=0.0000

Stage2 unique predicted classes: ['Abuse']

Stage2 confidence: min=0.5721 max=0.5721 mean=0.5721 std=0.0000
