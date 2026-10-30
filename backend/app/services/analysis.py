from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from typing import Callable

from app.detectors.base import DetectorAdapter, DetectorUnavailable
from app.detectors.config import DetectorConfig
from app.detectors.factory import create_detector
from app.detectors.pipeline import iter_video_detections
from app.services.config import AnalysisOptions
from app.services.video import InvalidVideo, probe_video
from app.storage.database import JobNotFound, LocalStore, StateConflict
from app.tracking import EventBuilder


class AnalysisWorker:
    def __init__(
        self,
        store: LocalStore,
        detector_factory: Callable[[AnalysisOptions], DetectorAdapter] | None = None,
        merge_gap_seconds: float = 0.8,
    ):
        self.store = store
        self.detector_factory = detector_factory or _default_detector
        self.merge_gap_seconds = merge_gap_seconds
        self._condition = threading.Condition()
        self._queue: deque[str] = deque()
        self._active_job: str | None = None
        self._cancel_event: threading.Event | None = None
        self._stopping = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.store.recover_interrupted_jobs()
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stopping = False
            self._queue.extend(self.store.list_queued_jobs())
            self._thread = threading.Thread(target=self._run, name="bird-analysis-worker", daemon=True)
            self._thread.start()

    def enqueue(self, job_id: str) -> None:
        with self._condition:
            if job_id == self._active_job or job_id in self._queue:
                return
            self._queue.append(job_id)
            self._condition.notify_all()

    def cancel_and_wait(self, job_id: str) -> None:
        with self._condition:
            if job_id == self._active_job and self._cancel_event is not None:
                self._cancel_event.set()
                while self._active_job == job_id:
                    self._condition.wait()
                return
            try:
                self._queue.remove(job_id)
            except ValueError:
                pass

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            if self._cancel_event is not None:
                self._cancel_event.set()
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=10)

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._queue and not self._stopping:
                    self._condition.wait()
                if self._stopping:
                    return
                job_id = self._queue.popleft()
                self._active_job = job_id
                self._cancel_event = threading.Event()
                cancel_event = self._cancel_event
            try:
                self._process(job_id, cancel_event)
            finally:
                with self._condition:
                    self._active_job = None
                    self._cancel_event = None
                    self._condition.notify_all()

    def _process(self, job_id: str, cancel_event: threading.Event) -> None:
        try:
            job = self.store.get_job(job_id)
            if job is None or job["state"] != "queued":
                return
            if cancel_event.is_set():
                self.store.transition(job_id, "cancelled")
                return
            self.store.transition(job_id, "probing")
            source_path = self.store.video_path_for(job_id)
            probe = probe_video(source_path, source_path.suffix.lower())
            self.store.update_video(job_id, probe.video, probe.total_frames)
            if cancel_event.is_set():
                self.store.transition(job_id, "cancelled")
                return
            self.store.transition(job_id, "running")
            self.store.reset_results(job_id)
            options = AnalysisOptions(**job["analysis_options"])
            detector_config = DetectorConfig(
                sample_interval_seconds=options.sample_interval_seconds,
                confidence_threshold=options.confidence_threshold,
            )
            detector = self.detector_factory(options)
            detector_metadata = dict(detector.metadata)
            self.store.update_detector_metadata(job_id, detector_metadata)
            started_at = time.monotonic()
            events = EventBuilder(
                duration_seconds=float(probe.video["duration_seconds"]),
                sample_interval_seconds=options.sample_interval_seconds,
                max_detection_gap_seconds=self.merge_gap_seconds,
            )
            for frame in iter_video_detections(source_path, detector, detector_config):
                if cancel_event.is_set():
                    self.store.transition(job_id, "cancelled")
                    return
                detections = list(frame.detections)
                contract_detections = [detection.contract_dict() for detection in detections]
                self.store.append_frame(
                    job_id,
                    frame.timestamp,
                    contract_detections,
                    {
                        "model_id": detector.model_id,
                        "model_version": detector.model_version,
                        "sample_interval_seconds": options.sample_interval_seconds,
                    },
                )
                for event in events.observe(frame.timestamp, detections):
                    self.store.put_event(job_id, event.contract_dict())
            if cancel_event.is_set():
                self.store.transition(job_id, "cancelled")
                return
            for event in events.finish():
                self.store.put_event(job_id, event.contract_dict())
            self.store.update_progress(job_id, float(probe.video["duration_seconds"]))
            processing_seconds = time.monotonic() - started_at
            self.store.update_detector_metadata(
                job_id,
                detector_metadata,
                processing_seconds,
            )
            self.store.transition(job_id, "completed")
        except JobNotFound:
            return
        except StateConflict:
            return
        except Exception as exc:
            job = self.store.get_job(job_id)
            if job is None or job["state"] in {"completed", "failed", "cancelled"}:
                return
            if isinstance(exc, InvalidVideo):
                code, message = "invalid_video", str(exc)
            elif isinstance(exc, DetectorUnavailable):
                code, message = "detector_unavailable", str(exc)
            else:
                code, message = "analysis_failed", "The analysis worker could not process this video."
            error = {
                "code": code,
                "message": message,
                "details": None,
                "request_id": uuid.uuid4().hex,
            }
            try:
                self.store.transition(job_id, "failed", error)
            except (JobNotFound, StateConflict):
                return


def _default_detector(options: AnalysisOptions) -> DetectorAdapter:
    config = DetectorConfig(
        sample_interval_seconds=options.sample_interval_seconds,
        confidence_threshold=options.confidence_threshold,
    )
    return create_detector(config)
