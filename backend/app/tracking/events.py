from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Iterable

from app.detectors.base import Detection


@dataclass(frozen=True)
class BirdEvent:
    event_id: str
    start_seconds: float
    end_seconds: float
    track_ids: tuple[int, ...]
    max_confidence: float
    detection_count: int

    def contract_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "track_ids": list(self.track_ids),
            "max_confidence": self.max_confidence,
            "detection_count": self.detection_count,
        }


@dataclass
class _ActiveEvent:
    first_timestamp: float
    last_timestamp: float
    track_ids: set[int] = field(default_factory=set)
    max_confidence: float = 0.0
    detection_count: int = 0

    def add(self, timestamp: float, detections: Iterable[Detection]) -> None:
        self.last_timestamp = timestamp
        for detection in detections:
            self.detection_count += 1
            self.max_confidence = max(self.max_confidence, detection.confidence)
            if detection.track_id is not None:
                self.track_ids.add(detection.track_id)


class EventBuilder:
    """Merge detections by presentation-time distance, with a no-tracker fallback."""

    def __init__(
        self,
        duration_seconds: float,
        sample_interval_seconds: float,
        max_detection_gap_seconds: float = 0.8,
        min_event_duration_seconds: float = 0.3,
        boundary_padding_seconds: float = 0.1,
    ) -> None:
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("duration_seconds must be a positive finite value")
        if not math.isfinite(sample_interval_seconds) or sample_interval_seconds <= 0:
            raise ValueError("sample_interval_seconds must be a positive finite value")
        if not math.isfinite(max_detection_gap_seconds) or max_detection_gap_seconds <= 0:
            raise ValueError("max_detection_gap_seconds must be a positive finite value")
        if not math.isfinite(min_event_duration_seconds) or min_event_duration_seconds < 0:
            raise ValueError("min_event_duration_seconds must be a finite non-negative value")
        if not math.isfinite(boundary_padding_seconds) or boundary_padding_seconds < 0:
            raise ValueError("boundary_padding_seconds must be a finite non-negative value")
        self.duration_seconds = duration_seconds
        self.sample_interval_seconds = sample_interval_seconds
        self.max_detection_gap_seconds = max_detection_gap_seconds
        self.min_event_duration_seconds = min_event_duration_seconds
        self.boundary_padding_seconds = boundary_padding_seconds
        self._active: _ActiveEvent | None = None
        self._last_observation = -math.inf
        self._finished = False

    def observe(self, timestamp: float, detections: Iterable[Detection]) -> tuple[BirdEvent, ...]:
        if self._finished:
            raise RuntimeError("cannot add observations after finish()")
        if not math.isfinite(timestamp) or not 0 <= timestamp <= self.duration_seconds:
            raise ValueError("timestamp must be within the video presentation duration")
        if timestamp < self._last_observation:
            raise ValueError("observations must be ordered by presentation timestamp")
        self._last_observation = timestamp
        detections = tuple(detections)
        emitted: list[BirdEvent] = []
        if self._active is not None and timestamp - self._active.last_timestamp > self.max_detection_gap_seconds:
            event = self._flush()
            if event is not None:
                emitted.append(event)
        if not detections:
            return tuple(emitted)
        if self._active is None:
            self._active = _ActiveEvent(timestamp, timestamp)
        self._active.add(timestamp, detections)
        return tuple(emitted)

    def finish(self) -> tuple[BirdEvent, ...]:
        if self._finished:
            return ()
        self._finished = True
        event = self._flush()
        return (event,) if event is not None else ()

    def _flush(self) -> BirdEvent | None:
        active = self._active
        self._active = None
        if active is None:
            return None
        start = max(0.0, active.first_timestamp - self.boundary_padding_seconds)
        unbounded_end = active.last_timestamp + self.sample_interval_seconds + self.boundary_padding_seconds
        if unbounded_end - start < self.min_event_duration_seconds:
            return None
        end = min(self.duration_seconds, unbounded_end)
        if end <= start:
            return None
        return BirdEvent(
            event_id=uuid.uuid4().hex,
            start_seconds=start,
            end_seconds=end,
            track_ids=tuple(sorted(active.track_ids)),
            max_confidence=active.max_confidence,
            detection_count=active.detection_count,
        )
