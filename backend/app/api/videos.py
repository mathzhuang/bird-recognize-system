from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from app.api.errors import ApiException, ContractRoute
from app.api.jobs import serialize_detail
from app.services.runtime import get_runtime
from app.services.video import InvalidVideo, probe_video


router = APIRouter(route_class=ContractRoute)
UPLOAD_CHUNK_SIZE = 1024 * 1024


@router.post("/videos", status_code=202)
async def upload_video(file: UploadFile = File(...)):
    runtime = get_runtime()
    file_name = _safe_file_name(file.filename or "")
    extension = Path(file_name).suffix.lower()
    if extension not in runtime.settings.allowed_extensions:
        raise ApiException(415, "unsupported_media_type", "The file extension is not in the configured video allowlist.")
    if file.size is not None and file.size > runtime.settings.max_upload_bytes:
        raise ApiException(413, "payload_too_large", "The uploaded file exceeds the configured size limit.")
    staging_path = runtime.store.new_staging_path()
    size = 0
    try:
        try:
            with staging_path.open("xb") as destination:
                while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                    size += len(chunk)
                    if size > runtime.settings.max_upload_bytes:
                        raise ApiException(413, "payload_too_large", "The uploaded file exceeds the configured size limit.")
                    _require_free_space(runtime.settings.data_dir, len(chunk), runtime.settings.upload_reserve_bytes)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
        except ClientDisconnect as exc:
            raise ApiException(400, "upload_interrupted", "The upload ended before the video was completely received.") from exc
        except OSError as exc:
            if _is_disk_full(exc):
                raise ApiException(507, "insufficient_storage", "There is not enough local disk space to store this video.") from exc
            raise
        if size == 0:
            raise ApiException(400, "empty_upload", "The uploaded file is empty.")
        try:
            probe = await run_in_threadpool(probe_video, staging_path, extension)
        except InvalidVideo as exc:
            raise ApiException(415, "unsupported_media_type", str(exc)) from exc
        try:
            job = await run_in_threadpool(
                runtime.store.create_uploaded_job,
                staging_path,
                file_name,
                extension,
                probe.media_type,
                probe.video,
                probe.total_frames,
                runtime.settings.default_options,
            )
        except OSError as exc:
            if _is_disk_full(exc):
                raise ApiException(507, "insufficient_storage", "There is not enough local disk space to store this video.") from exc
            raise
        runtime.worker.enqueue(job["job_id"])
        return JSONResponse(
            status_code=202,
            content=serialize_detail(job),
            headers={"Location": f"/api/jobs/{job['job_id']}"},
        )
    finally:
        try:
            staging_path.unlink(missing_ok=True)
        finally:
            await file.close()


def _safe_file_name(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    file_name = normalized.rsplit("/", 1)[-1].strip()
    if not file_name or file_name in {".", ".."}:
        raise ApiException(400, "invalid_file_name", "A video file name is required.")
    return file_name


def _require_free_space(directory: Path, incoming_bytes: int, reserve_bytes: int) -> None:
    try:
        free_bytes = shutil.disk_usage(directory).free
    except OSError as exc:
        raise ApiException(507, "insufficient_storage", "Local storage availability could not be checked.") from exc
    if free_bytes < incoming_bytes + reserve_bytes:
        raise ApiException(507, "insufficient_storage", "There is not enough local disk space to store this video.")


def _is_disk_full(exc: OSError) -> bool:
    return exc.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)} or getattr(exc, "winerror", None) == 112
