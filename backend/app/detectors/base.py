from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Sequence

from app.detectors.config import DetectorConfig
from app.services.video import VideoSample


class DetectorUnavailable(RuntimeError):
    """A selected detector cannot start because its local runtime is incomplete."""


@dataclass(frozen=True)
class Detection:
    timestamp: float
    bbox: tuple[float, float, float, float]
    confidence: float
    class_name: str
    track_id: int | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.timestamp) or self.timestamp < 0:
            raise ValueError("detection timestamp must be a finite non-negative video time")
        if len(self.bbox) != 4 or not all(math.isfinite(value) and 0 <= value <= 1 for value in self.bbox):
            raise ValueError("bbox must contain four normalized values between 0 and 1")
        if self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]:
            raise ValueError("bbox must have positive width and height")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.class_name.strip():
            raise ValueError("class_name must not be empty")
        if self.track_id is not None and (
            isinstance(self.track_id, bool) or not isinstance(self.track_id, int) or self.track_id < 0
        ):
            raise ValueError("track_id must be null or a non-negative integer")

    def contract_dict(self) -> dict[str, object]:
        """Project to CONTRACTS.md Detection; class_name stays detector-internal."""
        return {"track_id": self.track_id, "confidence": self.confidence, "bbox": list(self.bbox)}


class DetectorAdapter(Protocol):
    model_id: str
    model_version: str

    @property
    def metadata(self) -> dict[str, object]: ...

    def detect(self, sample: VideoSample, config: DetectorConfig | None = None) -> list[Detection]:
        """Detect objects in an already displayed (rotation-applied) RGB frame."""


class MockBirdDetector:
    model_id = "mock-bird-detector"
    model_version = "1"

    def __init__(self, detections: Sequence[Detection] = ()) -> None:
        self._templates = tuple(detections)

    @property
    def metadata(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_name": "Deterministic mock detector",
            "model_version": self.model_version,
            "weights_source": None,
            "weights_sha256": None,
            "license": "Project test fixture; no model weights",
            "device": "none",
        }

    def detect(self, sample: VideoSample, config: DetectorConfig | None = None) -> list[Detection]:
        active_config = config or DetectorConfig()
        return [
            Detection(
                timestamp=sample.timestamp,
                bbox=item.bbox,
                confidence=item.confidence,
                class_name=item.class_name,
                track_id=item.track_id,
            )
            for item in self._templates
            if item.confidence >= active_config.confidence_threshold
            and item.class_name.casefold() in active_config.class_names
        ]
