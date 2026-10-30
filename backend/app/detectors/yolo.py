from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import math
import os
from pathlib import Path
from typing import Any

from app.detectors.base import Detection, DetectorUnavailable
from app.detectors.config import DetectorConfig
from app.services.video import VideoSample


YOLO11N_SOURCE = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"
YOLO11N_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
YOLO11N_LICENSE = (
    "Ultralytics identifies its code/models as AGPL-3.0 or Enterprise; see the benchmark report. "
    "The weight artifact has no separately verified license metadata."
)


def normalize_xyxy(
    xyxy: tuple[float, float, float, float] | list[float],
    width: int,
    height: int,
) -> tuple[float, float, float, float] | None:
    if width <= 0 or height <= 0 or len(xyxy) != 4:
        raise ValueError("frame dimensions and xyxy coordinates are invalid")
    x1, y1, x2, y2 = (float(value) for value in xyxy)
    if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
        return None
    x1, x2 = min(1.0, max(0.0, x1 / width)), min(1.0, max(0.0, x2 / width))
    y1, y2 = min(1.0, max(0.0, y1 / height)), min(1.0, max(0.0, y2 / height))
    if x1 >= x2 or y1 >= y2:
        return None
    return x1, y1, x2, y2


class YOLOBirdDetector:
    model_id = "ultralytics-yolo11n-coco"

    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self.weights_path = _weights_path(config.weights_path)
        if not self.weights_path.is_file():
            raise DetectorUnavailable(
                "YOLO11n weights are missing. Run .\\scripts\\setup.ps1 -WithDetector or set BIRD_MODEL_PATH. "
                "For a synthetic UI preview without model weights, run .\\scripts\\start.ps1 -Mock."
            )
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise DetectorUnavailable(
                "Ultralytics is not installed. Run .\\scripts\\setup.ps1 -WithDetector. "
                "For a synthetic UI preview without a detector, run .\\scripts\\start.ps1 -Mock."
            ) from exc

        self._device = _resolve_device(config.device)
        try:
            self._model = YOLO(str(self.weights_path))
            self._model.to(self._device)
        except Exception as exc:
            raise DetectorUnavailable("The local YOLO detector could not load its model weights.") from exc
        try:
            self._ultralytics_version = importlib.metadata.version("ultralytics")
        except importlib.metadata.PackageNotFoundError:
            self._ultralytics_version = "unknown"
        self._weights_sha256 = _sha256(self.weights_path)
        self._is_reference_weights = self._weights_sha256 == YOLO11N_SHA256
        self.model_id = "ultralytics-yolo11n-coco" if self._is_reference_weights else f"ultralytics-{self.weights_path.stem}"
        self.model_name = "Ultralytics YOLO11n COCO" if self._is_reference_weights else f"Ultralytics YOLO weights ({self.weights_path.stem})"
        model_line = "YOLO11n" if self._is_reference_weights else f"YOLO weights {self.weights_path.stem}"
        self.model_version = f"{model_line} / ultralytics {self._ultralytics_version}"

    @property
    def metadata(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "weights_source": YOLO11N_SOURCE if self._is_reference_weights else f"local:{self.weights_path.name}",
            "weights_path": str(self.weights_path.resolve()),
            "weights_sha256": self._weights_sha256,
            "license": YOLO11N_LICENSE if self._is_reference_weights else "Unknown; verify the local weight publisher's terms",
            "training_data": "COCO 2017 detection labels (bird class)" if self._is_reference_weights else "Unknown; verify the local weight publisher",
            "device": self._device,
            "inference_config": self.config.inference_metadata(),
        }

    def detect(self, sample: VideoSample, config: DetectorConfig | None = None) -> list[Detection]:
        active_config = config or self.config
        if sample.image.ndim < 2 or sample.image.shape[1] != sample.width or sample.image.shape[0] != sample.height:
            raise ValueError("VideoSample dimensions must match its displayed image array")
        class_names = _class_name_map(self._model.names)
        selected_ids = [index for index, name in class_names.items() if name.casefold() in active_config.class_names]
        if not selected_ids:
            return []
        size: int | tuple[int, int]
        size = active_config.input_size
        options: dict[str, Any] = {
            "source": sample.image,
            "imgsz": size,
            "conf": active_config.confidence_threshold,
            "iou": active_config.nms_iou_threshold,
            "classes": selected_ids,
            "device": self._device,
            "verbose": False,
        }
        if active_config.tracking_enabled:
            _require_bytetrack_dependency()
            results = self._model.track(tracker="bytetrack.yaml", persist=True, **options)
        else:
            results = self._model.predict(**options)
        if not results:
            return []
        result = results[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.detach().cpu().tolist()
        confidences = boxes.conf.detach().cpu().tolist()
        class_ids = boxes.cls.detach().cpu().tolist()
        track_values = boxes.id.detach().cpu().tolist() if active_config.tracking_enabled and boxes.id is not None else [None] * len(xyxy)
        detections = []
        for coordinates, confidence, raw_class_id, raw_track_id in zip(xyxy, confidences, class_ids, track_values):
            class_id = int(raw_class_id)
            class_name = class_names.get(class_id)
            if class_name is None or class_name.casefold() not in active_config.class_names:
                continue
            normalized = normalize_xyxy(coordinates, sample.width, sample.height)
            if normalized is None:
                continue
            detections.append(
                Detection(
                    timestamp=sample.timestamp,
                    bbox=normalized,
                    confidence=float(confidence),
                    class_name=class_name,
                    track_id=int(raw_track_id) if raw_track_id is not None else None,
                )
            )
        return detections


def _weights_path(configured_path: Path | None) -> Path:
    if configured_path is not None:
        return configured_path.resolve()
    environment_path = os.getenv("BIRD_MODEL_PATH")
    if environment_path:
        return Path(environment_path).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / "models" / "yolo11n.pt").resolve()


def _resolve_device(configured_device: str) -> str:
    try:
        import torch
    except ImportError:
        if configured_device.isdigit():
            raise RuntimeError("A CUDA device was requested, but PyTorch with CUDA is not available")
        return "cpu"
    if configured_device == "cpu":
        return "cpu"
    if configured_device.isdigit():
        if not torch.cuda.is_available():
            raise RuntimeError("A CUDA device was requested, but CUDA is not available")
        return f"cuda:{configured_device}"
    return "cuda:0" if torch.cuda.is_available() else "cpu"


def _require_bytetrack_dependency() -> None:
    if importlib.util.find_spec("lap") is None:
        raise RuntimeError(
            "ByteTrack requires the optional 'lap>=0.5.12' package. Install it before starting analysis; "
            "runtime dependency installation is disabled."
        )
    try:
        from packaging.version import Version

        installed_version = importlib.metadata.version("lap")
        if Version(installed_version) < Version("0.5.12"):
            raise RuntimeError("ByteTrack requires 'lap>=0.5.12'; upgrade it before starting analysis.")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("ByteTrack requires 'lap>=0.5.12'; install it before starting analysis.") from exc


def _class_name_map(names: Any) -> dict[int, str]:
    if isinstance(names, dict):
        return {int(index): str(name) for index, name in names.items()}
    return {index: str(name) for index, name in enumerate(names)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as weights:
        for chunk in iter(lambda: weights.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
