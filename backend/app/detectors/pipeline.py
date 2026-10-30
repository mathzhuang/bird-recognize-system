from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.detectors.base import Detection, DetectorAdapter
from app.detectors.config import DetectorConfig
from app.services.video import iter_sampled_frames


@dataclass(frozen=True)
class DetectionFrame:
    timestamp: float
    detections: tuple[Detection, ...]

    def contract_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "detections": [detection.contract_dict() for detection in self.detections],
        }


def iter_video_detections(
    video_path: Path,
    detector: DetectorAdapter,
    config: DetectorConfig,
) -> Iterator[DetectionFrame]:
    """Stream PTS-sampled frames and detector outputs without retaining the video."""
    for sample in iter_sampled_frames(video_path, config.sample_interval_seconds):
        yield DetectionFrame(sample.timestamp, tuple(detector.detect(sample, config)))
