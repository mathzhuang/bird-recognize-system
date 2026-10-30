from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.detectors import Detection, DetectorConfig, DetectorUnavailable, MockBirdDetector, create_detector
from app.detectors.pipeline import iter_video_detections
from app.detectors import yolo as yolo_module
from app.detectors.yolo import YOLOBirdDetector, normalize_xyxy
from app.services.video import VideoSample


def _sample(timestamp: float = 1.25) -> VideoSample:
    image = np.zeros((80, 120, 3), dtype=np.uint8)
    return VideoSample(timestamp=timestamp, image=image, width=120, height=80)


def test_detector_config_validates_sampling_and_normalizes_class_filters() -> None:
    config = DetectorConfig(sample_interval_seconds=0.2, class_names={" Bird ", "BIRD"})

    assert config.sample_interval_seconds == 0.2
    assert config.class_names == frozenset({"bird"})
    assert config.inference_metadata()["input_size"] == 640

    with pytest.raises(ValueError, match="sample_interval_seconds"):
        DetectorConfig(sample_interval_seconds=0)
    with pytest.raises(ValueError, match="input_size"):
        DetectorConfig(input_size=16)


def test_mock_detector_emits_pts_and_only_contract_coordinates() -> None:
    template = Detection(0, (0.1, 0.2, 0.8, 0.9), 0.91, "bird", 4)
    detector = MockBirdDetector([template])

    detections = detector.detect(_sample(3.75), DetectorConfig())

    assert len(detections) == 1
    assert detections[0].timestamp == 3.75
    assert detections[0].class_name == "bird"
    assert detections[0].contract_dict() == {
        "track_id": 4,
        "confidence": 0.91,
        "bbox": [0.1, 0.2, 0.8, 0.9],
    }
    assert "class_name" not in detections[0].contract_dict()


def test_mock_detector_applies_confidence_and_class_filter() -> None:
    detector = MockBirdDetector(
        [
            Detection(0, (0.1, 0.1, 0.2, 0.2), 0.2, "bird"),
            Detection(0, (0.3, 0.3, 0.4, 0.4), 0.9, "person"),
        ]
    )

    assert detector.detect(_sample(), DetectorConfig(confidence_threshold=0.25)) == []


def test_video_pipeline_uses_configured_pts_sampling(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    samples = [_sample(0.0), _sample(0.42), _sample(0.91)]
    seen: dict[str, object] = {}

    def fake_sampler(path: Path, interval: float):
        seen["path"] = path
        seen["interval"] = interval
        yield from samples

    monkeypatch.setattr("app.detectors.pipeline.iter_sampled_frames", fake_sampler)
    detector = MockBirdDetector([Detection(0, (0.1, 0.1, 0.4, 0.4), 0.8, "bird")])
    config = DetectorConfig(sample_interval_seconds=0.5)

    frames = list(iter_video_detections(tmp_path / "local.mp4", detector, config))

    assert seen == {"path": tmp_path / "local.mp4", "interval": 0.5}
    assert [frame.timestamp for frame in frames] == [0.0, 0.42, 0.91]
    assert [frame.contract_dict()["timestamp"] for frame in frames] == [0.0, 0.42, 0.91]


def test_normalize_xyxy_clamps_then_normalizes_post_rotation_dimensions() -> None:
    assert normalize_xyxy((-10, 20, 120, 80), width=120, height=80) == (0.0, 0.25, 1.0, 1.0)
    assert normalize_xyxy((30, 20, 10, 40), width=120, height=80) is None
    assert normalize_xyxy((0, 0, 0, 20), width=120, height=80) is None


def test_yolo_adapter_filters_classes_and_maps_normalized_boxes_and_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTensor:
        def __init__(self, values):
            self.values = values

        def detach(self):
            return self

        def cpu(self):
            return self

        def tolist(self):
            return self.values

    class FakeBoxes:
        def __init__(self):
            self.xyxy = FakeTensor([[10, 20, 100, 60], [20, 20, 80, 60]])
            self.conf = FakeTensor([0.9, 0.95])
            self.cls = FakeTensor([14, 0])
            self.id = None

        def __len__(self):
            return 2

    class FakeModel:
        names = {0: "person", 14: "bird"}

        def __init__(self):
            self.boxes = FakeBoxes()
            self.call = None

        def predict(self, **kwargs):
            self.call = ("predict", kwargs)
            return [SimpleNamespace(boxes=self.boxes)]

        def track(self, **kwargs):
            self.call = ("track", kwargs)
            self.boxes.id = FakeTensor([7, 8])
            return [SimpleNamespace(boxes=self.boxes)]

    detector = object.__new__(YOLOBirdDetector)
    detector.config = DetectorConfig()
    detector._device = "cpu"
    detector._model = FakeModel()
    monkeypatch.setattr(yolo_module, "_require_bytetrack_dependency", lambda: None)
    detections = detector.detect(_sample(2.5))

    assert len(detections) == 1
    assert detections[0].timestamp == 2.5
    assert detections[0].class_name == "bird"
    assert detections[0].track_id is None
    assert detections[0].bbox == pytest.approx((10 / 120, 20 / 80, 100 / 120, 60 / 80))
    assert detector._model.call[0] == "predict"
    assert detector._model.call[1]["classes"] == [14]
    assert detector._model.call[1]["imgsz"] == 640

    tracked = detector.detect(_sample(2.9), DetectorConfig(tracking_enabled=True))
    assert len(tracked) == 1
    assert tracked[0].track_id == 7
    assert detector._model.call[0] == "track"
    assert detector._model.call[1]["tracker"] == "bytetrack.yaml"


def test_tracking_reports_missing_optional_dependency_without_installing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yolo_module.importlib.util, "find_spec", lambda _name: None)

    with pytest.raises(RuntimeError, match="runtime dependency installation is disabled"):
        yolo_module._require_bytetrack_dependency()


def test_factory_defaults_to_mock_and_real_detector_needs_local_weights(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BIRD_DETECTOR", raising=False)
    assert isinstance(create_detector(), MockBirdDetector)

    missing = tmp_path / "missing.pt"
    with pytest.raises(DetectorUnavailable, match="weights are missing"):
        create_detector(DetectorConfig(weights_path=missing), backend="ultralytics")
