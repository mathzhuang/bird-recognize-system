from __future__ import annotations

import threading
from dataclasses import dataclass

from app.services.analysis import AnalysisWorker
from app.services.config import Settings
from app.storage.database import LocalStore


@dataclass
class Runtime:
    settings: Settings
    store: LocalStore
    worker: AnalysisWorker


_lock = threading.Lock()
_runtime: Runtime | None = None


def start_runtime() -> None:
    global _runtime
    with _lock:
        if _runtime is not None:
            return
        settings = Settings.from_environment()
        store = LocalStore(settings)
        worker = AnalysisWorker(store, merge_gap_seconds=settings.event_merge_gap_seconds)
        worker.start()
        _runtime = Runtime(settings, store, worker)


def stop_runtime() -> None:
    global _runtime
    with _lock:
        runtime = _runtime
        _runtime = None
    if runtime is not None:
        runtime.worker.stop()


def get_runtime() -> Runtime:
    runtime = _runtime
    if runtime is None:
        raise RuntimeError("The local analysis service has not started.")
    return runtime
