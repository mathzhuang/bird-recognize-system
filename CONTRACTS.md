# API Contract

This file defines the shared data and time semantics for the frontend, backend, and detector work. The machine-readable contract is [`docs/openapi.yaml`](docs/openapi.yaml). It is the canonical API schema; frontend TypeScript declarations are generated from it with `npm run api:types` in `frontend/`. The local backend currently implements all listed HTTP routes. The front-end development mock is separate from the backend API and is enabled with `npm run dev:mock`.

## Local Service

The API listens on `127.0.0.1:8000` by default. Video bytes and analysis data stay on the local machine. Do not send source videos to external services.

## Shared Semantics

- Job states are exactly `queued`, `probing`, `running`, `completed`, `failed`, and `cancelled`.
- All media positions and durations use seconds on the video's presentation timeline. The first displayed video frame is time `0`; decoded presentation timestamps (PTS) are used, including for variable frame rate media. Do not derive media time from frame number divided by nominal FPS, request time, or the browser wall clock.
- `created_at`, `finished_at`, and `updated_at` are UTC wall-clock metadata only. They must never be used to synchronize the player, detections, events, or progress position.
- A detection timestamp is the PTS of the sampled frame, relative to the first displayed frame. Event ranges use half-open intervals `[start_seconds, end_seconds)` and are bounded by the video duration.
- A bounding box is `[x1, y1, x2, y2]`, normalized to `[0, 1]` against the displayed image after rotation metadata is applied. Origin is the top-left; x increases right and y increases down. Coordinates describe the post-rotation display dimensions, not raw coded pixels. Require `x1 < x2` and `y1 < y2`.
- `GET /api/jobs/{job_id}/detections` requires a time range and returns bounded pages. A range may cover at most 60 seconds and a page at most 1,000 sampled frames. Clients load longer videos in successive ranges; they must not expect one response to contain every frame.
- `GET /api/jobs/{job_id}/video` uses byte offsets in the stored file for the HTTP `Range` header. Those byte offsets are unrelated to video-time seconds.
- API errors use one envelope: `{"error":{"code":"...","message":"...","details":{},"request_id":"..."}}`. `details` is `null` when there is no field-level information. Error codes are stable machine identifiers; clients should display `message` and branch only on `code`.
- Backend implementations must map malformed input and validation failures to the documented status and `ErrorEnvelope`; do not expose framework-default validation bodies such as FastAPI's `{"detail": ...}` or an undocumented `422` response.

## Endpoints

| Method and path | Request | Success | Main errors |
| --- | --- | --- | --- |
| `GET /api/health` | No body | `200 HealthResponse` | None |
| `POST /api/videos` | `multipart/form-data`, required `file` | `202 JobDetail` with `Location: /api/jobs/{job_id}` | `400`, `413`, `415`, `507`, `500` |
| `GET /api/jobs` | Optional `state`, `cursor`, `limit` (1-100) | `200 JobPage` | `400`, `500` |
| `GET /api/jobs/{job_id}` | Path ID | `200 JobDetail` | `404`, `500` |
| `GET /api/jobs/{job_id}/progress` | Path ID; optional `Last-Event-ID` | `200 text/event-stream` | `404`, `500` before stream starts |
| `GET /api/jobs/{job_id}/events` | Optional `cursor`, `limit` (1-200) | `200 EventPage` | `400`, `404`, `500` |
| `GET /api/jobs/{job_id}/detections` | Required `from_seconds`, `to_seconds`; optional `cursor`, `limit` (1-1000) | `200 DetectionPage` | `400`, `404`, `409`, `500` |
| `GET /api/jobs/{job_id}/video` | Optional single byte `Range` | `200` full body or `206` partial body | `404`, `416`, `500` |
| `DELETE /api/jobs/{job_id}` | Path ID | `204` empty body | `404`, `500` |
| `POST /api/jobs/{job_id}/reanalyze` | Optional JSON `ReanalysisRequest` | `202 JobDetail` for a new job ID | `400`, `404`, `409`, `507`, `500` |

Every error response has the common `ErrorEnvelope` schema. A `400` indicates malformed input or an invalid time range/cursor, `404` an unknown job, `409` a known job whose results are not ready or cannot be reanalyzed in its current state, `413` an upload above the configured limit, `415` an unsupported video, `416` an invalid or unsatisfiable byte range, `507` insufficient local storage, and `500` an unexpected local service or storage failure. The upload extension allowlist and size limit are configuration, not trust in the multipart MIME type; the backend must probe the file contents before accepting analysis.

### Upload and Reanalysis

Uploading stores the source file locally, creates a job, and returns `202` once accepted into the queue. The initial state is `queued`. Reanalysis always creates a new `job_id`, preserving the source job and prior results. The new job's `source_job_id` points to the job used as its source. Omitted reanalysis options and omitted fields within `options` use the server's current defaults; explicit `null` values are invalid.

### Task Progress SSE

The stream is UTF-8 `text/event-stream`. It sends an initial snapshot, then `progress` events with JSON `ProgressEvent` data. Each event has a monotonically increasing job-local `id`; `Last-Event-ID` may be used as a reconnect hint, but delivery is not a durable replay guarantee. On reconnect, the initial snapshot is authoritative. A final `progress` event carries one terminal state (`completed`, `failed`, or `cancelled`) and the server then closes the stream. A stream failure after HTTP headers have been sent uses an `error` event whose data is an `ErrorEnvelope`. `updated_at` is UTC metadata; `processed_seconds` is video-timeline progress.

### Events and Detection Pages

Events may be queried while a job is running and represent the event records committed so far. Results are ordered by `start_seconds`, then `event_id`. Detection pages contain frames with timestamps in `[from_seconds, to_seconds)`, ordered by timestamp. `to_seconds` must be greater than `from_seconds`, both must be within the video's duration, and the interval cannot exceed 60 seconds. Cursors are opaque and bound to the job, query range, and ordering; use a fresh cursor when any query parameter changes. If a job has not reached `running` or `completed`, detection queries return `409 results_not_ready`.

### Video Range Playback

Without `Range`, return `200` with the full stored video and `Accept-Ranges: bytes`. A valid single range returns `206`, `Content-Range: bytes start-end/size`, and the requested bytes. Open-ended and suffix ranges are supported. Multiple ranges are not supported and return `416` with `Content-Range: bytes */size`. The response `Content-Type` is the probed media type. The browser can use this endpoint directly as the HTML video source.

### Deletion

Successful deletion cancels active work, waits for the worker to stop using the job's files, deletes only that job's local source and result files, and removes its metadata before returning `204`. Repeating deletion after the job no longer exists returns `404`.

## Schema and Type Synchronization

`docs/openapi.yaml` is the sole schema source. Generate the frontend's TypeScript declarations after changing it by running `npm run api:types` from `frontend/`, then run `npm run build`. Backend request validation and response serialization are tested against this schema; there is no separately generated Python schema. Keep Pydantic request models and API responses aligned with the OpenAPI field names and constraints, and do not invent parallel time or coordinate semantics.
