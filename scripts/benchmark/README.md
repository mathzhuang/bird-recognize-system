# Local Detector Baseline

## Model and License

The optional baseline is Ultralytics YOLO11n (`yolo11n.pt`), pretrained on COCO 2017. COCO class `bird` is filtered by default. The reference artifact is published at [Ultralytics assets v8.3.0](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt); its code package is [Ultralytics](https://github.com/ultralytics/ultralytics), whose [published licensing](https://www.ultralytics.com/license) offers AGPL-3.0 or an Enterprise License. The asset itself does not expose separately verifiable license metadata. Treat the baseline as AGPL-3.0 governed unless Ultralytics confirms otherwise; downloading it does not grant commercial redistribution rights. Review the intended deployment with the rights holder or use a separately licensed detector before closed-source commercial distribution.

The adapter records model and package versions, local weight path, SHA-256, source, license note, device, and inference settings in its metadata. No weights are committed and the application does not download them automatically.

From the repository root, install the optional runtime and fetch the reference weights explicitly:

```powershell
backend/.venv/Scripts/python -m pip install ultralytics==8.4.193
New-Item -ItemType Directory -Force backend/models | Out-Null
Invoke-WebRequest https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt -OutFile backend/models/yolo11n.pt
```

Set `BIRD_MODEL_PATH` to use a different local weight file. The detector defaults to CPU unless PyTorch reports CUDA availability; Intel integrated graphics are not selected by this CUDA-only path.

ByteTrack is optional. Install it before enabling `--tracking`; runtime dependency installation is disabled.

```powershell
backend/.venv/Scripts/python -m pip install "lap>=0.5.12"
```

## Benchmark

The script decodes local video frames using PTS, samples at the configured interval, and reports media duration, displayed resolution, target and measured sample rate, device, end-to-end wall time, model-load time, first-sample time, steady per-sample processing time and rate, process peak working set, sampled frames, frames containing detections, detection count, errors, and model metadata. Peak memory includes model load and process startup. It never sends video to a remote service.

```powershell
backend/.venv/Scripts/python scripts/benchmark/run.py --video D:\data\birds.mp4 --detector ultralytics --device auto --sample-interval 0.4 --input-size 640 --confidence 0.25 --output benchmark.json
```

Use `--tracking` to enable the framework's ByteTrack integration. Tracking is off by default because this repository has no labeled multi-bird or occlusion footage to validate identity stability. Event grouping remains available through `app.tracking.EventBuilder` with tracking disabled; it joins detections only while their presentation-time gap stays within the configured maximum.

## Contract Note

The detector adapter keeps `class_name` on each internal result as required for category filtering. The shared `Detection` schema in `CONTRACTS.md` and `docs/openapi.yaml` contains only `track_id`, `confidence`, and normalized `bbox`; frame time belongs to the enclosing `DetectionFrame.timestamp`. Serialization therefore projects detector results to those shared fields. If consumers need class names in saved/API results, the minimal contract change is to add an optional `class_name` field to OpenAPI `Detection`, update `CONTRACTS.md`, regenerate frontend declarations, and add response tests. This adapter does not change the shared API contract.

Rotation is applied to decoded RGB frames before they reach the adapter. Ultralytics maps its letterboxed model output back to the submitted frame; the adapter then divides by the displayed frame width and height, clamps coordinates to `[0, 1]`, and discards degenerate boxes. This follows the contract's post-rotation coordinate system.

## Validation Limits

No representative bird video is checked into this workspace. Use locally owned, labeled static-bird, flight, distant-bird, multi-bird, and no-bird clips before drawing recall, false-positive, or ByteTrack-stability conclusions. The synthetic blank-video smoke result validates decode, timestamp sampling, and runtime only; it is not an accuracy evaluation.

## Local Smoke Result (2026-10-30)

- Machine: Windows 11, Intel Core i7-1165G7 (4 cores), Intel Iris Xe; installed runtime was PyTorch 2.7.1+cpu, `torch.cuda.is_available() == False`. The integrated GPU was not available to this CUDA-only baseline.
- Video: locally generated blank gray MP4, 20.0 seconds, 320x240, 200 source frames at 10 FPS; no real bird footage was present.
- Configuration: YOLO11n COCO, input size 640, bird class, confidence 0.25, PTS interval 0.4 seconds (target 2.5 samples/second), tracking disabled.
- Result without tracking: 50 sampled frames at 2.5 samples/second, 0 detection frames, 0 detections, 0 errors; end-to-end 15.94 seconds, including 6.14 seconds model load and 5.32 seconds for the first sample. The remaining 49 samples took 4.49 seconds total (10.92 samples/second, about 4.37 video-seconds per processing-second at this sample interval). End-to-end throughput was 1.25 video-seconds per processing-second. Peak working set was 400.3 MB.
- ByteTrack enabled: 50 sampled frames, 0 detections, 0 errors; end-to-end 19.02 seconds, including 5.53 seconds model load and 6.23 seconds for the first sample. The remaining 49 samples took 7.26 seconds total (6.75 samples/second, about 2.70 video-seconds per processing-second). End-to-end throughput was 1.05 video-seconds per processing-second. Peak working set was 402.5 MB. This checks tracker startup only, not association quality.
- Weight SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` (5,613,764 bytes, ignored by Git).

The timing is a synthetic smoke measurement, not a stable performance estimate. With no labeled bird clip, recall and bird-class false negatives are unknown. The blank sample produced no false detections. ByteTrack initialized successfully after its optional `lap` dependency was installed; identity continuity and multi-bird association remain unvalidated.
