from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.services.config import AnalysisOptions, Settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class JobNotFound(Exception):
    pass


class StateConflict(Exception):
    pass


class LocalStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.data_dir
        self.videos_dir = self.root / "videos"
        self.staging_dir = self.root / ".staging"
        self.database_path = self.root / "app.db"
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._remove_stale_uploads()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    source_job_id TEXT,
                    file_name TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('queued','probing','running','completed','failed','cancelled')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT,
                    processed_seconds REAL NOT NULL DEFAULT 0,
                    duration_seconds REAL,
                    processed_frames INTEGER NOT NULL DEFAULT 0,
                    total_frames INTEGER,
                    sampled_count INTEGER NOT NULL DEFAULT 0,
                    detection_count INTEGER NOT NULL DEFAULT 0,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    sequence INTEGER NOT NULL DEFAULT 1,
                    error_json TEXT,
                    video_json TEXT,
                    analysis_options_json TEXT NOT NULL,
                    detector_json TEXT,
                    source_path TEXT NOT NULL,
                    detections_path TEXT NOT NULL,
                    metadata_path TEXT NOT NULL,
                    media_type TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created_at DESC, job_id DESC);
                CREATE INDEX IF NOT EXISTS jobs_state_created ON jobs(state, created_at DESC, job_id DESC);
                CREATE TABLE IF NOT EXISTS frames (
                    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                    line_number INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    byte_offset INTEGER NOT NULL,
                    PRIMARY KEY(job_id, line_number)
                );
                CREATE INDEX IF NOT EXISTS frames_timestamp ON frames(job_id, timestamp, line_number);
                CREATE TABLE IF NOT EXISTS events (
                    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                    event_id TEXT NOT NULL,
                    start_seconds REAL NOT NULL,
                    end_seconds REAL NOT NULL,
                    track_ids_json TEXT NOT NULL,
                    max_confidence REAL NOT NULL,
                    detection_count INTEGER NOT NULL,
                    PRIMARY KEY(job_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS events_order ON events(job_id, start_seconds, event_id);
                """
            )
            self._remove_source_job_foreign_key(connection)

    @staticmethod
    def _remove_source_job_foreign_key(connection: sqlite3.Connection) -> None:
        foreign_keys = connection.execute("PRAGMA foreign_key_list(jobs)").fetchall()
        if not any(row["from"] == "source_job_id" for row in foreign_keys):
            return
        connection.execute("PRAGMA foreign_keys = OFF")
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE jobs_replacement (
                    job_id TEXT PRIMARY KEY,
                    source_job_id TEXT,
                    file_name TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('queued','probing','running','completed','failed','cancelled')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT,
                    processed_seconds REAL NOT NULL DEFAULT 0,
                    duration_seconds REAL,
                    processed_frames INTEGER NOT NULL DEFAULT 0,
                    total_frames INTEGER,
                    sampled_count INTEGER NOT NULL DEFAULT 0,
                    detection_count INTEGER NOT NULL DEFAULT 0,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    sequence INTEGER NOT NULL DEFAULT 1,
                    error_json TEXT,
                    video_json TEXT,
                    analysis_options_json TEXT NOT NULL,
                    detector_json TEXT,
                    source_path TEXT NOT NULL,
                    detections_path TEXT NOT NULL,
                    metadata_path TEXT NOT NULL,
                    media_type TEXT NOT NULL
                )"""
            )
            columns = "job_id, source_job_id, file_name, state, created_at, updated_at, finished_at, processed_seconds, duration_seconds, processed_frames, total_frames, sampled_count, detection_count, event_count, sequence, error_json, video_json, analysis_options_json, detector_json, source_path, detections_path, metadata_path, media_type"
            connection.execute(f"INSERT INTO jobs_replacement ({columns}) SELECT {columns} FROM jobs")
            connection.execute("DROP TABLE jobs")
            connection.execute("ALTER TABLE jobs_replacement RENAME TO jobs")
            connection.execute("CREATE INDEX jobs_created ON jobs(created_at DESC, job_id DESC)")
            connection.execute("CREATE INDEX jobs_state_created ON jobs(state, created_at DESC, job_id DESC)")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")

    def _remove_stale_uploads(self) -> None:
        for path in self.staging_dir.iterdir():
            if path.is_file() or path.is_symlink():
                try:
                    path.unlink()
                except OSError:
                    pass

    def new_staging_path(self) -> Path:
        return self.staging_dir / f"{uuid.uuid4().hex}.part"

    def job_directory(self, job_id: str) -> Path:
        return self.videos_dir / job_id

    def create_uploaded_job(
        self,
        staging_path: Path,
        file_name: str,
        extension: str,
        media_type: str,
        video: dict[str, Any],
        total_frames: int | None,
        options: AnalysisOptions,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        directory = self.job_directory(job_id)
        directory.mkdir(parents=False)
        source = directory / f"source{extension}"
        detections = directory / "detections.jsonl"
        metadata_path = directory / "metadata.json"
        try:
            os.replace(staging_path, source)
            detections.touch()
            self._atomic_json(
                metadata_path,
                {
                    "video": video,
                    "source_frame_count": total_frames,
                    "analysis": {"options": options.model_dump(), "model_id": None, "model_version": None},
                },
            )
            now = utc_now()
            with self.connect() as connection:
                connection.execute(
                    """INSERT INTO jobs (
                        job_id, file_name, state, created_at, updated_at, duration_seconds,
                        video_json, analysis_options_json, source_path,
                        detections_path, metadata_path, media_type
                    ) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        job_id,
                        file_name,
                        now,
                        now,
                        video["duration_seconds"],
                        self._json(video),
                        self._json(options.model_dump()),
                        self._relative(source),
                        self._relative(detections),
                        self._relative(metadata_path),
                        media_type,
                    ),
                )
            return self.get_job(job_id)  # type: ignore[return-value]
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def create_reanalysis_job(
        self,
        source_job_id: str,
        options: AnalysisOptions,
    ) -> dict[str, Any]:
        source_job = self.get_job(source_job_id)
        if source_job is None:
            raise JobNotFound(source_job_id)
        original_path = self._path(source_job["source_path"])
        if not original_path.is_file():
            raise FileNotFoundError(original_path)
        video = source_job.get("video")
        job_id = uuid.uuid4().hex
        directory = self.job_directory(job_id)
        directory.mkdir(parents=False)
        source = directory / original_path.name
        try:
            try:
                os.link(original_path, source)
            except OSError:
                free_bytes = shutil.disk_usage(self.root).free
                if free_bytes < original_path.stat().st_size + self.settings.upload_reserve_bytes:
                    raise OSError(28, "insufficient local storage")
                with original_path.open("rb") as source_handle, source.open("xb") as target_handle:
                    shutil.copyfileobj(source_handle, target_handle, 1024 * 1024)
            detections = directory / "detections.jsonl"
            detections.touch()
            metadata_path = directory / "metadata.json"
            self._atomic_json(
                metadata_path,
                {
                    "video": video,
                    "source_frame_count": None,
                    "analysis": {"options": options.model_dump(), "model_id": None, "model_version": None},
                },
            )
            now = utc_now()
            with self.connect() as connection:
                connection.execute(
                    """INSERT INTO jobs (
                        job_id, source_job_id, file_name, state, created_at, updated_at,
                        duration_seconds, video_json, analysis_options_json,
                        source_path, detections_path, metadata_path, media_type
                    ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        job_id,
                        source_job_id,
                        source_job["file_name"],
                        now,
                        now,
                        (video or {}).get("duration_seconds"),
                        self._json(video) if video is not None else None,
                        self._json(options.model_dump()),
                        self._relative(source),
                        self._relative(detections),
                        self._relative(metadata_path),
                        source_job["media_type"],
                    ),
                )
            return self.get_job(job_id)  # type: ignore[return-value]
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._job_dict(row) if row else None

    def require_job(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job is None:
            raise JobNotFound(job_id)
        return job

    def list_queued_jobs(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute("SELECT job_id FROM jobs WHERE state = 'queued' ORDER BY created_at, job_id").fetchall()
        return [row["job_id"] for row in rows]

    def recover_interrupted_jobs(self) -> None:
        now = utc_now()
        with self.connect() as connection:
            rows = connection.execute("SELECT job_id, detections_path FROM jobs WHERE state IN ('probing','running')").fetchall()
            for row in rows:
                detections = self._path(row["detections_path"])
                detections.parent.mkdir(parents=True, exist_ok=True)
                detections.write_bytes(b"")
                connection.execute("DELETE FROM frames WHERE job_id = ?", (row["job_id"],))
                connection.execute("DELETE FROM events WHERE job_id = ?", (row["job_id"],))
                connection.execute(
                    """UPDATE jobs SET state='queued', updated_at=?, finished_at=NULL,
                       processed_seconds=0, processed_frames=0, sampled_count=0,
                       total_frames=NULL, detection_count=0, event_count=0, sequence=sequence+1, error_json=NULL
                       WHERE job_id=?""",
                    (now, row["job_id"]),
                )

    def transition(self, job_id: str, target: str, error: dict[str, Any] | None = None) -> dict[str, Any]:
        allowed = {
            "queued": {"probing", "cancelled", "failed"},
            "probing": {"running", "cancelled", "failed"},
            "running": {"completed", "cancelled", "failed"},
            "completed": set(),
            "failed": set(),
            "cancelled": set(),
        }
        with self.connect() as connection:
            row = connection.execute("SELECT state FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise JobNotFound(job_id)
            current = row["state"]
            if target not in allowed[current]:
                raise StateConflict(f"cannot transition job from {current} to {target}")
            now = utc_now()
            connection.execute(
                """UPDATE jobs SET state=?, updated_at=?, finished_at=?, error_json=?, sequence=sequence+1,
                   total_frames=CASE WHEN ?='completed' THEN processed_frames ELSE total_frames END
                   WHERE job_id=?""",
                (
                    target,
                    now,
                    now if target in {"completed", "failed", "cancelled"} else None,
                    self._json(error) if error else None,
                    target,
                    job_id,
                ),
            )
        return self.require_job(job_id)

    def update_video(self, job_id: str, video: dict[str, Any], total_frames: int | None) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET video_json=?, duration_seconds=?, total_frames=NULL WHERE job_id=?",
                (self._json(video), video["duration_seconds"], job_id),
            )
        job = self.require_job(job_id)
        metadata_path = self._path(job["metadata_path"])
        try:
            current = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {"analysis": {"options": job["analysis_options"]}}
        current["video"] = video
        current["source_frame_count"] = total_frames
        self._atomic_json(metadata_path, current)

    def reset_results(self, job_id: str) -> None:
        job = self.require_job(job_id)
        path = self._path(job["detections_path"])
        path.write_bytes(b"")
        with self.connect() as connection:
            connection.execute("DELETE FROM frames WHERE job_id=?", (job_id,))
            connection.execute("DELETE FROM events WHERE job_id=?", (job_id,))
            connection.execute(
                """UPDATE jobs SET sampled_count=0, detection_count=0, event_count=0,
                   processed_seconds=0, processed_frames=0, total_frames=NULL, sequence=sequence+1 WHERE job_id=?""",
                (job_id,),
            )

    def append_frame(
        self,
        job_id: str,
        timestamp: float,
        detections: list[dict[str, Any]],
        provenance: dict[str, Any] | None = None,
    ) -> None:
        job = self.require_job(job_id)
        path = self._path(job["detections_path"])
        record = {"timestamp": timestamp, "detections": detections, **(provenance or {})}
        record.setdefault("processed_at", utc_now())
        line = (self._json(record) + "\n").encode("utf-8")
        with path.open("ab") as handle:
            offset = handle.tell()
            handle.write(line)
            handle.flush()
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute("SELECT sampled_count FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise JobNotFound(job_id)
            line_number = row["sampled_count"]
            connection.execute(
                "INSERT INTO frames(job_id,line_number,timestamp,byte_offset) VALUES(?,?,?,?)",
                (job_id, line_number, timestamp, offset),
            )
            connection.execute(
                """UPDATE jobs SET sampled_count=sampled_count+1, detection_count=detection_count+?,
                   processed_frames=processed_frames+1, processed_seconds=?, updated_at=?, sequence=sequence+1
                   WHERE job_id=?""",
                (len(detections), timestamp, now, job_id),
            )

    def update_progress(self, job_id: str, processed_seconds: float) -> None:
        with self.connect() as connection:
            connection.execute(
                """UPDATE jobs SET processed_seconds=MAX(processed_seconds, ?), updated_at=?, sequence=sequence+1
                   WHERE job_id=? AND state='running'""",
                (processed_seconds, utc_now(), job_id),
            )

    def put_event(self, job_id: str, event: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO events(job_id,event_id,start_seconds,end_seconds,track_ids_json,max_confidence,detection_count)
                   VALUES(?,?,?,?,?,?,?) ON CONFLICT(job_id,event_id) DO UPDATE SET
                   end_seconds=excluded.end_seconds, track_ids_json=excluded.track_ids_json,
                   max_confidence=excluded.max_confidence, detection_count=excluded.detection_count""",
                (
                    job_id,
                    event["event_id"],
                    event["start_seconds"],
                    event["end_seconds"],
                    self._json(event["track_ids"]),
                    event["max_confidence"],
                    event["detection_count"],
                ),
            )
            connection.execute("UPDATE jobs SET event_count=(SELECT COUNT(*) FROM events WHERE job_id=?) WHERE job_id=?", (job_id, job_id))

    def update_detector_metadata(self, job_id: str, detector: dict[str, Any], processing_seconds: float | None = None) -> None:
        job = self.require_job(job_id)
        details_path = self._path(job["metadata_path"])
        try:
            current = json.loads(details_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {"video": job.get("video"), "analysis": {"options": job["analysis_options"]}}
        current.setdefault("analysis", {}).update(detector)
        if processing_seconds is not None:
            current["analysis"]["processing_seconds"] = processing_seconds
        self._atomic_json(details_path, current)
        with self.connect() as connection:
            connection.execute("UPDATE jobs SET detector_json=? WHERE job_id=?", (self._json(detector), job_id))

    def list_jobs(
        self,
        state: str | None,
        after: tuple[str, str] | None,
        limit: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        clauses: list[str] = []
        params: list[Any] = []
        if state:
            clauses.append("state=?")
            params.append(state)
        if after:
            clauses.append("(created_at < ? OR (created_at = ? AND job_id < ?))")
            params.extend((after[0], after[0], after[1]))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM jobs {where} ORDER BY created_at DESC, job_id DESC LIMIT ?",
                (*params, limit + 1),
            ).fetchall()
        more = len(rows) > limit
        return [self._job_dict(row) for row in rows[:limit]], more

    def list_events(self, job_id: str, after: tuple[float, str] | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
        self.require_job(job_id)
        clause = " AND (start_seconds > ? OR (start_seconds = ? AND event_id > ?))" if after else ""
        params: tuple[Any, ...] = (job_id, after[0], after[0], after[1], limit + 1) if after else (job_id, limit + 1)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE job_id=?" + clause + " ORDER BY start_seconds,event_id LIMIT ?", params
            ).fetchall()
        more = len(rows) > limit
        items = [
            {
                "event_id": row["event_id"],
                "start_seconds": row["start_seconds"],
                "end_seconds": row["end_seconds"],
                "track_ids": json.loads(row["track_ids_json"]),
                "max_confidence": row["max_confidence"],
                "detection_count": row["detection_count"],
            }
            for row in rows[:limit]
        ]
        return items, more

    def get_frame_offsets(
        self,
        job_id: str,
        from_seconds: float,
        to_seconds: float,
        after_line: int,
        limit: int,
    ) -> tuple[list[tuple[int, float]], bool]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT line_number,byte_offset FROM frames
                   WHERE job_id=? AND timestamp>=? AND timestamp<? AND line_number>?
                   ORDER BY timestamp,line_number LIMIT ?""",
                (job_id, from_seconds, to_seconds, after_line, limit + 1),
            ).fetchall()
        more = len(rows) > limit
        return [(row["byte_offset"], row["line_number"]) for row in rows[:limit]], more

    def read_frames(self, job_id: str, offsets: list[tuple[int, float]]) -> list[dict[str, Any]]:
        job = self.require_job(job_id)
        path = self._path(job["detections_path"])
        frames: list[dict[str, Any]] = []
        with path.open("rb") as handle:
            for offset, _line_number in offsets:
                handle.seek(offset)
                record = json.loads(handle.readline().decode("utf-8"))
                frames.append({"timestamp": record["timestamp"], "detections": record["detections"]})
        return frames

    def video_path_for(self, job_id: str) -> Path:
        job = self.require_job(job_id)
        return self._path(job["source_path"])

    def delete_job(self, job_id: str) -> None:
        self.require_job(job_id)
        directory = self.job_directory(job_id)
        trash: Path | None = None
        if directory.is_symlink():
            directory.unlink()
        elif directory.exists():
            trash = self.videos_dir / f".deleting-{uuid.uuid4().hex}"
            directory.rename(trash)
        try:
            with self.connect() as connection:
                connection.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
            if trash is not None:
                shutil.rmtree(trash)
        except Exception:
            if trash is not None and trash.exists() and not directory.exists():
                trash.rename(directory)
            raise

    def _job_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        job = dict(row)
        job["video"] = json.loads(job["video_json"]) if job["video_json"] else None
        job["error"] = json.loads(job["error_json"]) if job["error_json"] else None
        job["analysis_options"] = json.loads(job["analysis_options_json"])
        job["detector"] = json.loads(job["detector_json"]) if job["detector_json"] else None
        return job

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def _path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("stored path escapes the configured data directory")
        return path

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

    def _atomic_json(self, path: Path, value: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(self._json(value), encoding="utf-8")
        os.replace(temporary, path)

    def write_metadata(self, job_id: str, metadata: dict[str, Any]) -> None:
        job = self.require_job(job_id)
        self._atomic_json(self._path(job["metadata_path"]), metadata)
