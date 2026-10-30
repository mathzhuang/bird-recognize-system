from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Header, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from app.api.errors import ApiException, ContractRoute, error_envelope
from app.api.pagination import decode_cursor, encode_cursor
from app.services.config import AnalysisOptions
from app.services.runtime import get_runtime
from app.storage.database import JobNotFound


router = APIRouter(route_class=ContractRoute)
TERMINAL_STATES = {"completed", "failed", "cancelled"}
JOB_STATES = {"queued", "probing", "running", *TERMINAL_STATES}


class ReanalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: ReanalysisOptions | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_options(cls, value: Any) -> Any:
        if isinstance(value, dict) and "options" in value and value["options"] is None:
            raise ValueError("options must be an object when provided")
        return value


class ReanalysisOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_interval_seconds: float | None = Field(default=None, gt=0, le=5)
    confidence_threshold: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def reject_null_overrides(cls, value: Any) -> Any:
        if isinstance(value, dict) and any(key in value and value[key] is None for key in cls.model_fields):
            raise ValueError("analysis option overrides must be numbers when provided")
        return value


def serialize_summary(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job["job_id"],
        "source_job_id": job["source_job_id"],
        "file_name": job["file_name"],
        "state": job["state"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "finished_at": job["finished_at"],
        "progress": {
            "processed_seconds": job["processed_seconds"],
            "duration_seconds": job["duration_seconds"],
            "processed_frames": job["processed_frames"],
            "total_frames": job["total_frames"],
        },
        "error": job["error"],
    }


def serialize_detail(job: dict[str, Any]) -> dict[str, Any]:
    runtime = get_runtime()
    source_path = runtime.store.video_path_for(job["job_id"])
    video = job["video"]
    return {
        **serialize_summary(job),
        "video": video,
        "video_url": f"/api/jobs/{job['job_id']}/video" if source_path.is_file() else None,
        "analysis_options": job["analysis_options"],
        "detection_count": job["detection_count"],
        "event_count": job["event_count"],
    }


@router.get("/jobs")
def list_jobs(
    state: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    if state is not None and state not in JOB_STATES:
        raise ApiException(400, "invalid_state", "The state filter is not a supported job state.")
    scope = {"endpoint": "jobs", "state": state, "order": "created_at_desc,job_id_desc"}
    last = decode_cursor(cursor, scope, 2)
    runtime = get_runtime()
    jobs, more = runtime.store.list_jobs(state, tuple(last) if last else None, limit)
    next_cursor = encode_cursor(scope, [jobs[-1]["created_at"], jobs[-1]["job_id"]]) if more and jobs else None
    return {"items": [serialize_summary(job) for job in jobs], "next_cursor": next_cursor}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    runtime = get_runtime()
    job = runtime.store.get_job(job_id)
    if job is None:
        raise ApiException(404, "not_found", "The requested job does not exist.")
    return serialize_detail(job)


@router.get("/jobs/{job_id}/progress")
def stream_progress(job_id: str, request: Request, last_event_id: str | None = Header(default=None, alias="Last-Event-ID")) -> StreamingResponse:
    runtime = get_runtime()
    job = runtime.store.get_job(job_id)
    if job is None:
        raise ApiException(404, "not_found", "The requested job does not exist.")

    async def events():
        last_sequence = -1
        last_heartbeat = time.monotonic()
        try:
            while True:
                current = await run_in_threadpool(runtime.store.get_job, job_id)
                if current is None:
                    data = error_envelope(request, 404, "not_found", "The requested job no longer exists.")
                    yield f"event: error\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
                    return
                sequence = current["sequence"]
                if sequence != last_sequence:
                    progress = serialize_summary(current)
                    data = {"job_id": progress["job_id"], "state": progress["state"], **progress["progress"], "updated_at": progress["updated_at"], "error": progress["error"]}
                    yield f"id: {sequence}\nevent: progress\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    last_sequence = sequence
                    last_heartbeat = time.monotonic()
                if current["state"] in TERMINAL_STATES:
                    return
                await asyncio.sleep(0.4)
                if time.monotonic() - last_heartbeat >= 15:
                    yield ": keep-alive\n\n"
                    last_heartbeat = time.monotonic()
        except Exception:
            from app.api.errors import logger

            logger.exception("Progress stream failed for job %s", job_id)
            data = error_envelope(request, 500, "internal_error", "The progress stream encountered an unexpected error.")
            yield f"event: error\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/jobs/{job_id}/events")
def list_events(
    job_id: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    runtime = get_runtime()
    scope = {"endpoint": "events", "job_id": job_id, "order": "start_seconds,event_id"}
    last = decode_cursor(cursor, scope, 2)
    try:
        items, more = runtime.store.list_events(job_id, (float(last[0]), str(last[1])) if last else None, limit)
    except JobNotFound as exc:
        raise ApiException(404, "not_found", "The requested job does not exist.") from exc
    next_cursor = encode_cursor(scope, [items[-1]["start_seconds"], items[-1]["event_id"]]) if more and items else None
    return {"items": items, "next_cursor": next_cursor}


@router.get("/jobs/{job_id}/detections")
def list_detections(
    job_id: str,
    from_seconds: float = Query(ge=0),
    to_seconds: float = Query(gt=0),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, Any]:
    runtime = get_runtime()
    job = runtime.store.get_job(job_id)
    if job is None:
        raise ApiException(404, "not_found", "The requested job does not exist.")
    if job["state"] not in {"running", "completed"}:
        raise ApiException(409, "results_not_ready", "Detection results are not available until analysis starts.")
    duration = job["duration_seconds"]
    if to_seconds <= from_seconds or to_seconds - from_seconds > 60 or to_seconds > duration:
        raise ApiException(400, "invalid_time_range", "The range must be increasing, no longer than 60 seconds, and within the video duration.")
    scope = {
        "endpoint": "detections",
        "job_id": job_id,
        "from_seconds": from_seconds,
        "to_seconds": to_seconds,
        "order": "timestamp,line_number",
    }
    last = decode_cursor(cursor, scope, 1)
    after_line = int(last[0]) if last else -1
    offsets, more = runtime.store.get_frame_offsets(job_id, from_seconds, to_seconds, after_line, limit)
    frames = runtime.store.read_frames(job_id, offsets)
    next_cursor = encode_cursor(scope, [offsets[-1][1]]) if more and offsets else None
    return {"from_seconds": from_seconds, "to_seconds": to_seconds, "frames": frames, "next_cursor": next_cursor}


@router.get("/jobs/{job_id}/video")
def get_video(job_id: str, range_header: str | None = Header(default=None, alias="Range")) -> StreamingResponse:
    runtime = get_runtime()
    job = runtime.store.get_job(job_id)
    if job is None:
        raise ApiException(404, "not_found", "The requested job does not exist.")
    path = runtime.store.video_path_for(job_id)
    if not path.is_file():
        raise ApiException(404, "video_not_found", "The source video is no longer available.")
    size = path.stat().st_size
    status_code = 200
    start, end = 0, size - 1
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(size)}
    if range_header is not None:
        start, end = _parse_range(range_header, size)
        status_code = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(
        _file_chunks(path, start, end - start + 1),
        status_code=status_code,
        media_type=job["media_type"],
        headers=headers,
    )


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str) -> Response:
    runtime = get_runtime()
    if runtime.store.get_job(job_id) is None:
        raise ApiException(404, "not_found", "The requested job does not exist.")
    runtime.worker.cancel_and_wait(job_id)
    try:
        runtime.store.delete_job(job_id)
    except JobNotFound as exc:
        raise ApiException(404, "not_found", "The requested job does not exist.") from exc
    return Response(status_code=204)


@router.post("/jobs/{job_id}/reanalyze", status_code=202)
def reanalyze_job(job_id: str, body: ReanalysisRequest | None = Body(default=None)) -> JSONResponse:
    runtime = get_runtime()
    source = runtime.store.get_job(job_id)
    if source is None:
        raise ApiException(404, "not_found", "The requested job does not exist.")
    if source["state"] in {"queued", "probing", "running"}:
        raise ApiException(409, "conflict", "A job cannot be reanalyzed while it is active.")
    overrides = body.options.model_dump(exclude_unset=True) if body and body.options else {}
    options = AnalysisOptions(**(runtime.settings.default_options.model_dump() | overrides))
    try:
        job = runtime.store.create_reanalysis_job(job_id, options)
    except FileNotFoundError as exc:
        raise ApiException(409, "conflict", "The source video is no longer available.") from exc
    except OSError as exc:
        if exc.errno in {28, 112} or getattr(exc, "winerror", None) == 112:
            raise ApiException(507, "insufficient_storage", "There is not enough local disk space to create this analysis job.") from exc
        raise
    runtime.worker.enqueue(job["job_id"])
    return JSONResponse(
        status_code=202,
        content=serialize_detail(job),
        headers={"Location": f"/api/jobs/{job['job_id']}"},
    )


def _parse_range(value: str, size: int) -> tuple[int, int]:
    def invalid() -> ApiException:
        return ApiException(
            416,
            "invalid_range",
            "The requested byte range is invalid or not satisfiable.",
            headers={"Content-Range": f"bytes */{size}"},
        )

    if size <= 0 or not value.startswith("bytes=") or "," in value:
        raise invalid()
    spec = value[6:]
    if spec.count("-") != 1:
        raise invalid()
    start_text, end_text = spec.split("-", 1)
    try:
        if not start_text:
            suffix = int(end_text)
            if suffix <= 0:
                raise invalid()
            start = max(0, size - suffix)
            end = size - 1
        else:
            start = int(start_text)
            end = min(int(end_text), size - 1) if end_text else size - 1
            if start < 0 or end < start or start >= size:
                raise invalid()
    except ValueError as exc:
        raise invalid() from exc
    return start, end


def _file_chunks(path: Path, start: int, length: int):
    remaining = length
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
