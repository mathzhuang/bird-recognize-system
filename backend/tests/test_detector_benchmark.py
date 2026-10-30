from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.detectors import DetectorConfig  # noqa: E402
from scripts.benchmark import run as benchmark  # noqa: E402
from video_helpers import make_video  # noqa: E402


def test_benchmark_counts_and_continues_after_per_frame_errors(monkeypatch, tmp_path: Path) -> None:
    class BrokenDetector:
        model_id = "broken-test"
        model_version = "1"
        metadata = {"model_id": model_id, "model_version": model_version, "device": "cpu"}

        def detect(self, _sample, _config):
            raise RuntimeError("synthetic inference failure")

    video = make_video(tmp_path / "empty.mp4", frame_count=4, rate=10)
    monkeypatch.setattr(benchmark, "create_detector", lambda *_args, **_kwargs: BrokenDetector())

    report = benchmark.run_benchmark(
        video,
        DetectorConfig(sample_interval_seconds=0.1),
        backend="mock",
    )

    assert report["sampled_frames"] == 4
    assert report["detection_frames"] == 0
    assert report["error_count"] == 4
    assert report["errors"] == ["RuntimeError: synthetic inference failure"] * 4
