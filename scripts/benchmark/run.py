from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any
from ctypes import wintypes


BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.detectors import DetectorConfig, create_detector  # noqa: E402
from app.services.video import InvalidVideo, iter_sampled_frames, probe_video  # noqa: E402


def run_benchmark(video_path: Path, config: DetectorConfig, backend: str) -> dict[str, Any]:
    probe = probe_video(video_path, video_path.suffix.casefold())
    started = time.perf_counter()
    model_load_seconds = 0.0
    inference_seconds = 0.0
    sample_processing_seconds: list[float] = []
    sample_count = 0
    detected_frames = 0
    detection_count = 0
    error_count = 0
    error_messages: list[str] = []
    detector = None
    try:
        detector = create_detector(config, backend=backend)
        model_load_seconds = time.perf_counter() - started
        samples = iter(iter_sampled_frames(video_path, config.sample_interval_seconds))
        while True:
            sample_started = time.perf_counter()
            try:
                sample = next(samples)
            except StopIteration:
                break
            except Exception as exc:
                sample_processing_seconds.append(time.perf_counter() - sample_started)
                error_count += 1
                if len(error_messages) < 5:
                    error_messages.append(f"{type(exc).__name__}: {exc}")
                break
            sample_count += 1
            try:
                detections = detector.detect(sample, config)
            except Exception as exc:
                sample_processing_seconds.append(time.perf_counter() - sample_started)
                error_count += 1
                if len(error_messages) < 5:
                    error_messages.append(f"{type(exc).__name__}: {exc}")
                continue
            sample_processing_seconds.append(time.perf_counter() - sample_started)
            if detections:
                detected_frames += 1
                detection_count += len(detections)
        inference_seconds = sum(sample_processing_seconds)
    except Exception as exc:
        if detector is not None:
            inference_seconds = sum(sample_processing_seconds)
        else:
            model_load_seconds = time.perf_counter() - started
        error_count += 1
        if len(error_messages) < 5:
            error_messages.append(f"{type(exc).__name__}: {exc}")
    processing_seconds = time.perf_counter() - started
    video = probe.video
    metadata = detector.metadata if detector is not None else {
        "model_id": f"{backend}-unavailable",
        "model_version": "unavailable",
        "device": config.device,
        "inference_config": config.inference_metadata(),
    }
    steady_sample_seconds = sum(sample_processing_seconds[1:])
    return {
        "video": str(video_path.resolve()),
        "video_duration_seconds": video["duration_seconds"],
        "video_resolution": [video["display_width"], video["display_height"]],
        "sample_interval_seconds": config.sample_interval_seconds,
        "target_sampling_rate_fps": 1.0 / config.sample_interval_seconds,
        "measured_sampling_rate_fps": sample_count / float(video["duration_seconds"]),
        "device": metadata.get("device", config.device),
        "processing_seconds": processing_seconds,
        "model_load_seconds": model_load_seconds,
        "inference_processing_seconds": inference_seconds,
        "first_sample_seconds": sample_processing_seconds[0] if sample_processing_seconds else 0.0,
        "steady_sample_processing_seconds": steady_sample_seconds,
        "steady_samples_per_second": max(0, sample_count - 1) / max(steady_sample_seconds, 1e-9),
        "steady_video_seconds_per_processing_second": config.sample_interval_seconds
        * max(0, sample_count - 1)
        / max(steady_sample_seconds, 1e-9),
        "video_seconds_per_processing_second": float(video["duration_seconds"]) / max(processing_seconds, 1e-9),
        "peak_memory_mb": _peak_memory_bytes() / (1024 * 1024),
        "sampled_frames": sample_count,
        "detection_frames": detected_frames,
        "detection_count": detection_count,
        "error_count": error_count,
        "errors": error_messages[:5],
        "model": metadata,
    }


def _peak_memory_bytes() -> int:
    if os.name == "nt":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        get_memory_info.restype = wintypes.BOOL
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if get_memory_info(process, ctypes.byref(counters), counters.cb):
            return int(counters.PeakWorkingSetSize)
        return 0
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak if platform.system() == "Darwin" else peak * 1024)
    except (ImportError, AttributeError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark local bird-video inference")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--detector", choices=("mock", "ultralytics"), default="mock")
    parser.add_argument("--sample-interval", type=float, default=0.4)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--class-name", action="append", dest="class_names")
    parser.add_argument("--device", default="auto", help="auto, cpu, or CUDA index (for example 0)")
    parser.add_argument("--tracking", action="store_true", help="enable Ultralytics ByteTrack")
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    if not args.video.is_file():
        parser.error(f"video does not exist: {args.video}")
    if args.video.suffix.casefold() not in {".mp4", ".m4v", ".mov", ".mkv", ".webm"}:
        parser.error("video extension must be MP4, M4V, MOV, MKV, or WebM")
    try:
        config = DetectorConfig(
            sample_interval_seconds=args.sample_interval,
            input_size=args.input_size,
            confidence_threshold=args.confidence,
            class_names=frozenset(args.class_names or ["bird"]),
            tracking_enabled=args.tracking,
            device=args.device,
            weights_path=args.weights,
        )
        report = run_benchmark(args.video, config, args.detector)
    except (InvalidVideo, OSError, ValueError) as exc:
        parser.error(str(exc))
    report_json = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report_json + "\n", encoding="utf-8")
    print(report_json)
    return 2 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
