from __future__ import annotations

from pathlib import Path

import pytest

from app.services.config import AnalysisOptions, Settings
from app.storage.database import LocalStore, StateConflict


VIDEO = {
    "duration_seconds": 2.0,
    "coded_width": 320,
    "coded_height": 240,
    "display_width": 320,
    "display_height": 240,
    "rotation_degrees": 0.0,
    "average_frame_rate": 25.0,
    "variable_frame_rate": False,
    "video_codec": "mpeg4",
    "has_audio": False,
}


def create_job(store: LocalStore, directory: Path):
    staging = store.new_staging_path()
    staging.write_bytes(b"video")
    return store.create_uploaded_job(staging, "sample.mp4", ".mp4", "video/mp4", VIDEO, 50, AnalysisOptions())


def test_state_machine_rejects_skipping_probing(tmp_path: Path) -> None:
    store = LocalStore(Settings(data_dir=tmp_path / "data", upload_reserve_bytes=0))
    job = create_job(store, tmp_path)

    with pytest.raises(StateConflict):
        store.transition(job["job_id"], "running")
    assert store.transition(job["job_id"], "probing")["state"] == "probing"
    assert store.transition(job["job_id"], "running")["state"] == "running"
    assert store.transition(job["job_id"], "cancelled")["finished_at"] is not None


def test_restart_requeues_interrupted_job_and_clears_partial_results(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    store = LocalStore(Settings(data_dir=data_dir, upload_reserve_bytes=0))
    job = create_job(store, tmp_path)
    job_id = job["job_id"]
    store.transition(job_id, "probing")
    store.transition(job_id, "running")
    store.append_frame(job_id, 0.5, [{"track_id": 1, "confidence": 0.9, "bbox": [0.1, 0.1, 0.3, 0.3]}])
    store.put_event(
        job_id,
        {
            "event_id": "event-1",
            "start_seconds": 0.5,
            "end_seconds": 1.0,
            "track_ids": [1],
            "max_confidence": 0.9,
            "detection_count": 1,
        },
    )

    restarted = LocalStore(Settings(data_dir=data_dir, upload_reserve_bytes=0))
    restarted.recover_interrupted_jobs()
    recovered = restarted.require_job(job_id)
    assert recovered["state"] == "queued"
    assert recovered["processed_seconds"] == 0
    assert recovered["processed_frames"] == 0
    assert recovered["detection_count"] == 0
    assert recovered["event_count"] == 0
    assert restarted.read_frames(job_id, []) == []
    assert restarted.video_path_for(job_id).read_bytes() == b"video"


def test_reanalysis_lineage_survives_source_deletion(tmp_path: Path) -> None:
    store = LocalStore(Settings(data_dir=tmp_path / "data", upload_reserve_bytes=0))
    source = create_job(store, tmp_path)
    source_id = source["job_id"]
    store.transition(source_id, "probing")
    store.transition(source_id, "running")
    store.transition(source_id, "completed")
    child = store.create_reanalysis_job(source_id, AnalysisOptions())

    store.delete_job(source_id)

    remaining = store.require_job(child["job_id"])
    assert remaining["source_job_id"] == source_id
    assert store.video_path_for(child["job_id"]).read_bytes() == b"video"
