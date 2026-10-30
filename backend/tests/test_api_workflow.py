from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.detectors import Detection, DetectorUnavailable, MockBirdDetector
from app.main import app
from app.services.runtime import get_runtime
from video_helpers import make_video


@pytest.fixture
def api_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "bird-data"
    monkeypatch.setenv("BIRD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("BIRD_UPLOAD_RESERVE_BYTES", "0")
    monkeypatch.setenv("BIRD_MAX_UPLOAD_BYTES", str(1024 * 1024))
    monkeypatch.setenv("BIRD_SAMPLE_INTERVAL_SECONDS", "0.4")
    return data_dir


def upload(client: TestClient, path: Path, filename: str = "birds.mp4"):
    return client.post(
        "/api/videos",
        files={"file": (filename, path.read_bytes(), "application/octet-stream")},
    )


def wait_for_state(client: TestClient, job_id: str, expected: str, timeout: float = 5) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["state"] in {"completed", "failed", "cancelled"}:
            assert job["state"] == expected, job
            return job
        time.sleep(0.02)
    pytest.fail(f"job {job_id} did not reach {expected} in time")


def test_upload_analysis_queries_range_reanalysis_restart_and_delete(api_environment: Path, tmp_path: Path) -> None:
    sample = make_video(tmp_path / "sample.mp4")
    with TestClient(app) as client:
        get_runtime().worker.detector_factory = lambda _options: MockBirdDetector(
            [Detection(0, (0.25, 0.25, 0.75, 0.75), 0.95, "bird", 1)]
        )
        accepted = upload(client, sample)
        assert accepted.status_code == 202
        assert accepted.headers["location"].startswith("/api/jobs/")
        initial = accepted.json()
        assert initial["state"] == "queued"
        job_id = initial["job_id"]
        completed = wait_for_state(client, job_id, "completed")
        assert completed["video"]["coded_width"] == 32
        assert completed["video"]["coded_height"] == 24
        assert completed["video"]["average_frame_rate"] == pytest.approx(10)
        assert completed["video"]["variable_frame_rate"] is False
        assert completed["video"]["rotation_degrees"] == 0
        assert completed["video"]["video_codec"] == "mpeg4"
        assert completed["video"]["has_audio"] is False
        assert completed["progress"]["processed_frames"] == 3
        assert completed["progress"]["total_frames"] == 3
        assert completed["detection_count"] == 3

        jobs = client.get("/api/jobs", params={"limit": 1})
        assert jobs.status_code == 200
        assert jobs.json()["items"][0]["job_id"] == job_id
        assert client.get(f"/api/jobs/{job_id}").json()["state"] == "completed"

        event_page = client.get(f"/api/jobs/{job_id}/events", params={"limit": 1})
        assert len(event_page.json()["items"]) == 1
        event = event_page.json()["items"][0]
        assert event["start_seconds"] == pytest.approx(0)
        assert event["end_seconds"] == pytest.approx(1)
        assert event["detection_count"] == 3

        first_page = client.get(
            f"/api/jobs/{job_id}/detections",
            params={"from_seconds": 0, "to_seconds": 1, "limit": 2},
        )
        assert first_page.status_code == 200
        assert [frame["timestamp"] for frame in first_page.json()["frames"]] == pytest.approx([0, 0.4])
        cursor = first_page.json()["next_cursor"]
        second_page = client.get(
            f"/api/jobs/{job_id}/detections",
            params={"from_seconds": 0, "to_seconds": 1, "limit": 2, "cursor": cursor},
        )
        assert [frame["timestamp"] for frame in second_page.json()["frames"]] == pytest.approx([0.8])
        invalid_range = client.get(
            f"/api/jobs/{job_id}/detections", params={"from_seconds": 0, "to_seconds": 61}
        )
        assert invalid_range.status_code == 400
        assert invalid_range.json()["error"]["code"] == "invalid_time_range"

        stream = client.get(f"/api/jobs/{job_id}/progress")
        assert stream.status_code == 200
        assert "event: progress" in stream.text
        assert '"state":"completed"' in stream.text

        video_path = Path(get_runtime().store.video_path_for(job_id))
        raw = video_path.read_bytes()
        full = client.get(f"/api/jobs/{job_id}/video")
        assert full.status_code == 200
        assert full.headers["accept-ranges"] == "bytes"
        assert full.content == raw
        partial = client.get(f"/api/jobs/{job_id}/video", headers={"Range": "bytes=0-3"})
        assert partial.status_code == 206
        assert partial.headers["content-range"] == f"bytes 0-3/{len(raw)}"
        assert partial.content == raw[:4]
        suffix = client.get(f"/api/jobs/{job_id}/video", headers={"Range": "bytes=-4"})
        assert suffix.status_code == 206
        assert suffix.content == raw[-4:]
        bad_range = client.get(f"/api/jobs/{job_id}/video", headers={"Range": "bytes=0-1,4-5"})
        assert bad_range.status_code == 416
        assert bad_range.headers["content-range"] == f"bytes */{len(raw)}"
        assert "error" in bad_range.json()

        rerun = client.post(
            f"/api/jobs/{job_id}/reanalyze",
            json={"options": {"sample_interval_seconds": 0.5, "confidence_threshold": 0.2}},
        )
        assert rerun.status_code == 202
        new_job_id = rerun.json()["job_id"]
        assert new_job_id != job_id
        assert rerun.json()["source_job_id"] == job_id
        rerun_job = wait_for_state(client, new_job_id, "completed")
        assert rerun_job["analysis_options"]["sample_interval_seconds"] == pytest.approx(0.5)
        detections_file = api_environment / "videos" / job_id / "detections.jsonl"
        first_record = json.loads(detections_file.read_text(encoding="utf-8").splitlines()[0])
        assert first_record["model_id"] == "mock-bird-detector"
        assert first_record["model_version"] == "1"
        assert first_record["processed_at"].endswith("Z")

    with TestClient(app) as restarted_client:
        reopened = restarted_client.get(f"/api/jobs/{job_id}")
        assert reopened.status_code == 200
        assert reopened.json()["state"] == "completed"
        deleted = restarted_client.delete(f"/api/jobs/{job_id}")
        assert deleted.status_code == 204
        assert deleted.content == b""
        assert not (api_environment / "videos" / job_id).exists()
        assert restarted_client.get(f"/api/jobs/{job_id}").status_code == 404
        assert restarted_client.get(f"/api/jobs/{new_job_id}").json()["source_job_id"] == job_id


def test_no_detection_job_completes_with_empty_events(api_environment: Path, tmp_path: Path) -> None:
    sample = make_video(tmp_path / "quiet.mp4", frame_count=3)
    with TestClient(app) as client:
        get_runtime().worker.detector_factory = lambda _options: MockBirdDetector()
        accepted = upload(client, sample, "quiet.mp4")
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]

        completed = wait_for_state(client, job_id, "completed")
        assert completed["detection_count"] == 0
        assert completed["event_count"] == 0
        assert client.get(f"/api/jobs/{job_id}/events").json()["items"] == []

        detections = client.get(
            f"/api/jobs/{job_id}/detections",
            params={"from_seconds": 0, "to_seconds": completed["video"]["duration_seconds"]},
        )
        assert detections.status_code == 200
        assert detections.json()["frames"]
        assert all(frame["detections"] == [] for frame in detections.json()["frames"])


def test_upload_rejects_extension_size_and_cleans_staging(api_environment: Path, tmp_path: Path) -> None:
    sample = make_video(tmp_path / "sample.mp4")
    with TestClient(app) as client:
        unsupported = upload(client, sample, "birds.avi")
        assert unsupported.status_code == 415
        assert unsupported.json()["error"]["code"] == "unsupported_media_type"
        oversized = client.post("/api/videos", files={"file": ("birds.mp4", b"x" * (1024 * 1024 + 1))})
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "payload_too_large"
        assert list((api_environment / ".staging").iterdir()) == []


def test_variable_frame_rate_metadata_and_detection_timestamps_use_pts(api_environment: Path, tmp_path: Path) -> None:
    sample = make_video(tmp_path / "variable.mp4", frame_count=5, pts_values=[0, 1, 4, 5, 9])
    with TestClient(app) as client:
        get_runtime().worker.detector_factory = lambda _options: MockBirdDetector(
            [Detection(0, (0.2, 0.2, 0.7, 0.7), 0.9, "bird", 2)]
        )
        accepted = upload(client, sample)
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]
        assert accepted.json()["video"]["variable_frame_rate"] is True
        completed = wait_for_state(client, job_id, "completed")
        assert completed["progress"]["duration_seconds"] == pytest.approx(1.0)
        frames = client.get(
            f"/api/jobs/{job_id}/detections",
            params={"from_seconds": 0, "to_seconds": 1.0},
        ).json()["frames"]
        assert [frame["timestamp"] for frame in frames] == pytest.approx([0.0, 0.4, 0.9])


def test_invalid_video_and_disk_full_have_error_envelopes(api_environment: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    invalid = tmp_path / "invalid.mp4"
    invalid.write_bytes(b"not a video")
    with TestClient(app) as client:
        unsupported = upload(client, invalid)
        assert unsupported.status_code == 415
        assert unsupported.json()["error"]["details"] is None
        assert list((api_environment / ".staging").iterdir()) == []

        from app.api import videos
        from app.api.errors import ApiException

        def no_space(*_args, **_kwargs):
            raise ApiException(507, "insufficient_storage", "There is not enough local disk space.")

        monkeypatch.setattr(videos, "_require_free_space", no_space)
        sample = make_video(tmp_path / "small.mp4", frame_count=2)
        unavailable = upload(client, sample)
        assert unavailable.status_code == 507
        assert unavailable.json()["error"]["code"] == "insufficient_storage"
        assert list((api_environment / ".staging").iterdir()) == []


def test_interrupted_upload_removes_partial_staging_file(api_environment: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.datastructures import UploadFile as StarletteUploadFile
    from starlette.requests import ClientDisconnect

    sample = make_video(tmp_path / "sample.mp4", frame_count=2)
    original_read = StarletteUploadFile.read
    read_count = 0

    async def interrupted_read(file, size=-1):
        nonlocal read_count
        read_count += 1
        if read_count > 1:
            raise ClientDisconnect()
        return await original_read(file, size)

    monkeypatch.setattr(StarletteUploadFile, "read", interrupted_read)
    with TestClient(app) as client:
        response = upload(client, sample)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "upload_interrupted"
        assert list((api_environment / ".staging").iterdir()) == []


def test_worker_failure_is_persisted_and_reanalysis_requires_inactive_job(api_environment: Path, tmp_path: Path) -> None:
    class BrokenDetector:
        model_id = "test-broken"
        model_version = "1"

        @property
        def metadata(self):
            return {"model_id": self.model_id, "model_version": self.model_version}

        def detect(self, sample, options):
            raise RuntimeError("detector failed")

    sample = make_video(tmp_path / "sample.mp4", frame_count=2)
    with TestClient(app) as client:
        runtime = get_runtime()
        runtime.worker.detector_factory = lambda _options: BrokenDetector()
        accepted = upload(client, sample)
        job_id = accepted.json()["job_id"]
        failed = wait_for_state(client, job_id, "failed")
        assert failed["error"]["code"] == "analysis_failed"
        assert client.get(f"/api/jobs/{job_id}/detections", params={"from_seconds": 0, "to_seconds": 0.1}).status_code == 409
        assert client.post(f"/api/jobs/{job_id}/reanalyze", json={"invalid": True}).status_code == 400
        partial_rerun = client.post(
            f"/api/jobs/{job_id}/reanalyze",
            json={"options": {"sample_interval_seconds": 0.5}},
        )
        assert partial_rerun.status_code == 202
        assert partial_rerun.json()["analysis_options"] == {
            "sample_interval_seconds": pytest.approx(0.5),
            "confidence_threshold": pytest.approx(0.25),
        }
        null_override = client.post(
            f"/api/jobs/{job_id}/reanalyze",
            json={"options": {"confidence_threshold": None}},
        )
        assert null_override.status_code == 400


def test_missing_detector_model_exposes_setup_guidance(api_environment: Path, tmp_path: Path) -> None:
    sample = make_video(tmp_path / "sample.mp4", frame_count=2)
    with TestClient(app) as client:
        runtime = get_runtime()
        runtime.worker.detector_factory = lambda _options: (_ for _ in ()).throw(
            DetectorUnavailable("YOLO11n weights are missing. Run scripts/setup.ps1 -WithDetector.")
        )
        accepted = upload(client, sample)
        failed = wait_for_state(client, accepted.json()["job_id"], "failed")

        assert failed["error"]["code"] == "detector_unavailable"
        assert "scripts/setup.ps1 -WithDetector" in failed["error"]["message"]


def test_duplicate_filenames_get_independent_jobs(api_environment: Path, tmp_path: Path) -> None:
    sample = make_video(tmp_path / "sample.mp4", frame_count=2)
    with TestClient(app) as client:
        first = upload(client, sample, "same.mp4").json()
        second = upload(client, sample, "same.mp4").json()
        assert first["job_id"] != second["job_id"]
        assert first["file_name"] == second["file_name"] == "same.mp4"
        assert wait_for_state(client, first["job_id"], "completed", timeout=15)["state"] == "completed"
        assert wait_for_state(client, second["job_id"], "completed", timeout=15)["state"] == "completed"


def test_delete_waits_for_active_worker_before_removing_job(
    api_environment: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIRD_SAMPLE_INTERVAL_SECONDS", "0.1")
    entered = threading.Event()

    class SlowDetector:
        model_id = "slow-test"
        model_version = "1"

        @property
        def metadata(self):
            return {"model_id": self.model_id, "model_version": self.model_version}

        def detect(self, sample, config):
            entered.set()
            time.sleep(0.15)
            return []

    sample = make_video(tmp_path / "sample.mp4", frame_count=30)
    with TestClient(app) as client:
        runtime = get_runtime()
        runtime.worker.detector_factory = lambda _options: SlowDetector()
        accepted = upload(client, sample)
        job_id = accepted.json()["job_id"]
        assert entered.wait(3)
        deleted = client.delete(f"/api/jobs/{job_id}")
        assert deleted.status_code == 204
        assert runtime.store.get_job(job_id) is None
        assert not (api_environment / "videos" / job_id).exists()
