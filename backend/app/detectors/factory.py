from __future__ import annotations

import os
from collections.abc import Sequence

from app.detectors.base import Detection, DetectorAdapter, MockBirdDetector
from app.detectors.config import DetectorConfig


def create_detector(
    config: DetectorConfig | None = None,
    backend: str | None = None,
    mock_detections: Sequence[Detection] = (),
) -> DetectorAdapter:
    """Select a local detector using BIRD_DETECTOR=mock|ultralytics (mock by default)."""
    detector_config = config or DetectorConfig()
    selected = (backend or os.getenv("BIRD_DETECTOR", "mock")).strip().casefold()
    if selected == "mock":
        return MockBirdDetector(mock_detections)
    if selected in {"ultralytics", "yolo11n"}:
        from app.detectors.yolo import YOLOBirdDetector

        return YOLOBirdDetector(detector_config)
    raise ValueError("BIRD_DETECTOR must be 'mock' or 'ultralytics'")
