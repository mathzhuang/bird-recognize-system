from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DetectorConfig:
    sample_interval_seconds: float = 0.4
    input_size: int | tuple[int, int] = 640
    confidence_threshold: float = 0.25
    nms_iou_threshold: float = 0.45
    class_names: frozenset[str] = field(default_factory=lambda: frozenset({"bird"}))
    tracking_enabled: bool = False
    device: str = "auto"
    weights_path: Path | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.sample_interval_seconds) or not 0 < self.sample_interval_seconds <= 5:
            raise ValueError("sample_interval_seconds must be greater than 0 and at most 5")
        if isinstance(self.input_size, int):
            sizes = (self.input_size,)
        else:
            sizes = self.input_size
            if len(sizes) != 2:
                raise ValueError("input_size must be an integer or a (height, width) pair")
        if any(not isinstance(size, int) or size < 32 for size in sizes):
            raise ValueError("input_size dimensions must be integers of at least 32 pixels")
        for name, value in (
            ("confidence_threshold", self.confidence_threshold),
            ("nms_iou_threshold", self.nms_iou_threshold),
        ):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        names = frozenset(name.strip().casefold() for name in self.class_names if name.strip())
        if not names:
            raise ValueError("class_names must contain at least one class")
        object.__setattr__(self, "class_names", names)
        if self.device != "auto" and self.device != "cpu" and not self.device.isdigit():
            raise ValueError("device must be 'auto', 'cpu', or a CUDA device index such as '0'")
        if self.weights_path is not None:
            object.__setattr__(self, "weights_path", Path(self.weights_path).expanduser())

    def inference_metadata(self) -> dict[str, object]:
        values = asdict(self)
        values["input_size"] = list(self.input_size) if isinstance(self.input_size, tuple) else self.input_size
        values["class_names"] = sorted(self.class_names)
        values["weights_path"] = str(self.weights_path) if self.weights_path is not None else None
        return values
