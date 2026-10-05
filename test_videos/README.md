# Test videos (excluded from this repository)

This project's local evaluation set — 81 UCF-Crime clips, organized by class — is intentionally **not** committed to this public repository. The clips are backed up privately and are not required to read or evaluate the code here.

## Expected layout

```
test_videos/
├── Abuse/          (7 videos)
├── Arrest/         (7 videos)
├── Arson/          (7 videos)
├── Burglary/       (7 videos)
├── Explosion/      (7 videos)
├── Fighting/       (7 videos)
├── Normal/         (7 videos)
├── RoadAccidents/  (7 videos)
├── Robbery/        (7 videos)
├── Shooting/       (4 videos)
├── Shoplifting/    (7 videos)
└── Vandalism/      (7 videos)
```

Total: 81 `.mp4` files.

## Why they're excluded

These clips come from the UCF-Crime dataset's train split, used here as a local sanity-check set rather than a measure of generalization (the model saw this data during training). They're sizable (~1.6 GB combined) and are kept in a private backup alongside the model weights rather than in this public portfolio repository.
