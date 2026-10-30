import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type JobState = components["schemas"]["JobState"];
export type ApiError = components["schemas"]["ApiError"];
export type JobSummary = components["schemas"]["JobSummary"];
export type JobDetail = components["schemas"]["JobDetail"];
export type JobPage = components["schemas"]["JobPage"];
export type EventPage = components["schemas"]["EventPage"];
export type DetectionPage = components["schemas"]["DetectionPage"];
export type ProgressEvent = components["schemas"]["ProgressEvent"];

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiError["details"];

  constructor(status: number, error: ApiError) {
    super(error.message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = error.code;
    this.details = error.details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let body: { error?: ApiError } | undefined;
    try { body = await response.json() as { error?: ApiError }; } catch { /* response may be empty */ }
    throw new ApiClientError(response.status, body?.error ?? {
      code: "http_error", message: `Local API returned HTTP ${response.status}.`, details: null, request_id: "",
    });
  }
  return response.status === 204 ? undefined as T : await response.json() as T;
}

export interface ApiAdapter {
  getHealth(signal?: AbortSignal): Promise<HealthResponse>;
  listJobs(signal?: AbortSignal, cursor?: string | null): Promise<JobPage>;
  getJob(jobId: string, signal?: AbortSignal): Promise<JobDetail>;
  uploadVideo(file: File, signal?: AbortSignal, onProgress?: (percent: number) => void): Promise<JobDetail>;
  getEvents(jobId: string, signal?: AbortSignal): Promise<EventPage>;
  getDetections(jobId: string, fromSeconds: number, toSeconds: number, signal?: AbortSignal): Promise<DetectionPage>;
  subscribeProgress(jobId: string, onProgress: (event: ProgressEvent) => void, onError: (error: Error) => void): () => void;
}

const realAdapter: ApiAdapter = {
  getHealth: (signal) => request<HealthResponse>("/api/health", { signal }),
  listJobs: (signal, cursor) => { const query = new URLSearchParams({ limit: "50" }); if (cursor) query.set("cursor", cursor); return request<JobPage>(`/api/jobs?${query}`, { signal }); },
  getJob: (jobId, signal) => request<JobDetail>(`/api/jobs/${encodeURIComponent(jobId)}`, { signal }),
  uploadVideo: (file, signal, onProgress) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    xhr.open("POST", "/api/videos"); xhr.responseType = "json";
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress?.(Math.round(event.loaded / event.total * 100)); };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) { resolve(xhr.response as JobDetail); return; }
      const body = xhr.response as { error?: ApiError } | null;
      reject(new ApiClientError(xhr.status, body?.error ?? { code: "http_error", message: `Local API returned HTTP ${xhr.status}.`, details: null, request_id: "" }));
    };
    xhr.onerror = () => reject(new Error("The local API could not be reached."));
    xhr.onabort = () => reject(new DOMException("Upload cancelled.", "AbortError"));
    if (signal?.aborted) { reject(new DOMException("Upload cancelled.", "AbortError")); return; }
    signal?.addEventListener("abort", abort, { once: true });
    xhr.onloadend = () => signal?.removeEventListener("abort", abort);
    const form = new FormData(); form.append("file", file); xhr.send(form);
  }),
  getEvents: async (jobId, signal) => {
    const items: EventPage["items"] = []; let cursor: string | null = null;
    do {
      const query = new URLSearchParams({ limit: "200" }); if (cursor) query.set("cursor", cursor);
      const page = await request<EventPage>(`/api/jobs/${encodeURIComponent(jobId)}/events?${query}`, { signal });
      items.push(...page.items); cursor = page.next_cursor;
    } while (cursor);
    return { items, next_cursor: null };
  },
  getDetections: async (jobId, fromSeconds, toSeconds, signal) => {
    const frames: DetectionPage["frames"] = []; let cursor: string | null = null;
    do {
      const query = new URLSearchParams({ from_seconds: String(fromSeconds), to_seconds: String(toSeconds), limit: "1000" }); if (cursor) query.set("cursor", cursor);
      const page = await request<DetectionPage>(`/api/jobs/${encodeURIComponent(jobId)}/detections?${query}`, { signal });
      frames.push(...page.frames); cursor = page.next_cursor;
    } while (cursor);
    return { from_seconds: fromSeconds, to_seconds: toSeconds, frames, next_cursor: null };
  },
  subscribeProgress: (jobId, onProgress, onError) => {
    const source = new EventSource(`/api/jobs/${encodeURIComponent(jobId)}/progress`);
    const handler = (event: Event) => {
      try {
        const progress = JSON.parse((event as MessageEvent<string>).data) as ProgressEvent;
        onProgress(progress);
        if (["completed", "failed", "cancelled"].includes(progress.state)) source.close();
      } catch { onError(new Error("The progress stream returned invalid data.")); }
    };
    source.addEventListener("progress", handler);
    source.onerror = () => onError(new Error("The progress stream is unavailable."));
    return () => { source.removeEventListener("progress", handler); source.close(); };
  },
};

function mockDetail(jobId: string, fileName: string, state: JobState = "completed"): JobDetail {
  const duration = 3;
  return {
    job_id: jobId, source_job_id: null, file_name: fileName, state,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(), finished_at: state === "completed" ? new Date().toISOString() : null,
    progress: { processed_seconds: state === "completed" ? duration : 0, duration_seconds: duration, processed_frames: state === "completed" ? 8 : 0, total_frames: 8 }, error: null,
    video: { duration_seconds: duration, coded_width: 1280, coded_height: 720, display_width: 1280, display_height: 720, rotation_degrees: 0, average_frame_rate: 25, variable_frame_rate: false, video_codec: "h264", has_audio: true },
    video_url: null, analysis_options: { sample_interval_seconds: 0.4, confidence_threshold: 0.25 }, detection_count: 8, event_count: 2,
  };
}

const mockDemoJob = mockDetail("mock-demo", "demo-bird-video.webm");
const mockJobs: JobDetail[] = [mockDemoJob];
const mockFrames: DetectionPage["frames"] = [
  { timestamp: 0.35, detections: [{ track_id: 1, confidence: 0.92, bbox: [0.42, 0.24, 0.62, 0.58] }] },
  { timestamp: 0.8, detections: [{ track_id: 1, confidence: 0.88, bbox: [0.48, 0.27, 0.68, 0.63] }] },
  { timestamp: 1.1, detections: [{ track_id: 1, confidence: 0.86, bbox: [0.51, 0.28, 0.7, 0.64] }] },
  { timestamp: 1.6, detections: [{ track_id: 2, confidence: 0.82, bbox: [0.16, 0.34, 0.36, 0.7] }, { track_id: 3, confidence: 0.78, bbox: [0.69, 0.17, 0.87, 0.48] }] },
  { timestamp: 1.85, detections: [{ track_id: 2, confidence: 0.84, bbox: [0.18, 0.32, 0.39, 0.69] }, { track_id: 3, confidence: 0.79, bbox: [0.7, 0.16, 0.88, 0.47] }] },
  { timestamp: 2.35, detections: [{ track_id: 2, confidence: 0.81, bbox: [0.22, 0.3, 0.43, 0.68] }] },
  { timestamp: 2.65, detections: [] },
  { timestamp: 2.9, detections: [] },
];
const mockAdapter: ApiAdapter = {
  getHealth: async () => ({ status: "ok", service: "bird-video-analyzer", version: "0.1.0", mode: "local" }),
  listJobs: async () => ({ items: mockJobs, next_cursor: null }),
  getJob: async (jobId) => mockJobs.find((job) => job.job_id === jobId) ?? (() => { throw new ApiClientError(404, { code: "not_found", message: "The requested job does not exist.", details: null, request_id: "mock" }); })(),
  uploadVideo: async (file, _signal, onProgress) => {
    onProgress?.(100);
    const job = mockDetail(`mock-${Date.now()}`, file.name, "completed");
    job.video_url = URL.createObjectURL(file); mockJobs.unshift(job); return job;
  },
  getEvents: async () => ({ items: [{ event_id: "mock-e1", start_seconds: 0.3, end_seconds: 1.2, track_ids: [1], max_confidence: 0.92, detection_count: 3 }, { event_id: "mock-e2", start_seconds: 1.5, end_seconds: 2.8, track_ids: [2, 3], max_confidence: 0.84, detection_count: 5 }], next_cursor: null }),
  getDetections: async (_jobId, fromSeconds, toSeconds) => ({ from_seconds: fromSeconds, to_seconds: toSeconds, next_cursor: null, frames: mockFrames.filter((frame) => frame.timestamp >= fromSeconds && frame.timestamp < toSeconds) }),
  subscribeProgress: (_jobId, onProgress) => { onProgress({ job_id: _jobId, state: "completed", processed_seconds: 3, duration_seconds: 3, processed_frames: 8, total_frames: 8, updated_at: new Date().toISOString(), error: null }); return () => undefined; },
};

export const api: ApiAdapter = import.meta.env.VITE_USE_MOCK === "true" ? mockAdapter : realAdapter;
