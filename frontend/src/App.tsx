import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClientError, DetectionPage, JobDetail, JobSummary, ProgressEvent } from "./api/client";
import type { components } from "./api/schema";
import { api } from "./api/client";
import { DetectionOverlay } from "./components/DetectionOverlay";
import { EventTimeline } from "./components/EventTimeline";
import { JobList } from "./components/JobList";
import { formatTime, nearestFrame, stateLabel, validateVideoFile } from "./ui";

type LoadState = "idle" | "loading" | "ready" | "error";
type BirdEvent = components["schemas"]["BirdEvent"];

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "The local API returned an unexpected error.";
}

function UploadPanel({ onUploaded }: { onUploaded: (job: JobDetail) => void }) {
  const [file, setFile] = useState<File | null>(null); const [error, setError] = useState<string | null>(null); const [status, setStatus] = useState<"idle" | "uploading" | "done">("idle"); const [percent, setPercent] = useState(0);
  const submit = async () => {
    const validation = validateVideoFile(file); if (validation) { setError(validation); return; }
    setError(null); setStatus("uploading"); setPercent(0);
    try { const job = await api.uploadVideo(file!, undefined, setPercent); setStatus("done"); onUploaded(job); }
    catch (uploadError) { setStatus("idle"); setError(errorMessage(uploadError)); }
  };
  return <section className="upload-panel" aria-labelledby="upload-heading">
    <div><p className="eyebrow">LOCAL VIDEO</p><h2 id="upload-heading">Analyze a video</h2><p className="panel-copy">Select a video stored on this computer. Analysis and results stay local.</p></div>
    <div className="upload-controls">
      <label className="file-picker"><input type="file" accept="video/mp4,video/quicktime,video/x-m4v,video/x-matroska,video/webm,.mp4,.mov,.m4v,.mkv,.webm" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setError(null); setStatus("idle"); }} /> <span>{file ? file.name : "Choose video"}</span></label>
      <button type="button" className="primary-button" disabled={status === "uploading"} onClick={submit}>{status === "uploading" ? `Uploading ${percent}%` : "Start analysis"}</button>
    </div>
    {status === "uploading" && <div className="progress-bar" aria-label={`Upload ${percent}%`}><span style={{ width: `${percent}%` }} /></div>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {status === "done" && <p className="inline-success">Video accepted and added to tasks.</p>}
  </section>;
}

function ProgressBanner({ job, progress, onRetry }: { job: JobDetail; progress: ProgressEvent | null; onRetry: () => void }) {
  const current = progress ?? { ...job.progress, state: job.state, error: job.error };
  const duration = current.duration_seconds ?? job.video?.duration_seconds ?? 0;
  const percent = duration > 0 ? Math.min(100, Math.round(current.processed_seconds / duration * 100)) : 0;
  if (current.state === "completed" && !current.error) return null;
  return <div className={`progress-banner banner-${current.state}`} role={current.state === "failed" ? "alert" : "status"}>
    <div><strong>{stateLabel(current.state)}</strong><span>{current.state === "failed" ? (current.error?.message ?? "Analysis failed.") : current.state === "cancelled" ? "This task was cancelled." : `${formatTime(current.processed_seconds)} of ${formatTime(duration)} processed`}</span></div>
    {(current.state === "running" || current.state === "queued" || current.state === "probing") && <div className="task-progress"><span style={{ width: `${percent}%` }} /></div>}
    {current.state === "failed" && <button type="button" className="text-button" onClick={onRetry}>Retry status</button>}
  </div>;
}

function AnalysisView({ job, onStatusError, onProgress }: { job: JobDetail; onStatusError: (message: string) => void; onProgress: (event: ProgressEvent) => void }) {
  const videoRef = useRef<HTMLVideoElement | null>(null); const pendingSeek = useRef<number | null>(null); const [container, setContainer] = useState<HTMLElement | null>(null); const [currentTime, setCurrentTime] = useState(0); const [events, setEvents] = useState<BirdEvent[]>([]); const [eventsState, setEventsState] = useState<LoadState>("loading"); const [framePage, setFramePage] = useState<DetectionPage | null>(null); const [frameState, setFrameState] = useState<LoadState>("idle"); const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const duration = job.video?.duration_seconds ?? 0;
  const activeState = progress?.state ?? job.state;
  const windowStart = duration > 0 ? Math.min(Math.max(0, Math.floor(currentTime / 5) * 5), Math.max(0, duration - 0.01)) : 0;
  const windowEnd = Math.min(duration, windowStart + 5);
  const videoUrl = job.video_url ?? undefined;

  const fetchEvents = useCallback(async (signal?: AbortSignal) => {
    setEventsState("loading");
    try {
      const page = await api.getEvents(job.job_id, signal);
      if (!signal?.aborted) { setEvents(page.items); setEventsState("ready"); }
    } catch (error) {
      if (!signal?.aborted) { setEventsState("error"); onStatusError(errorMessage(error)); }
    }
  }, [job.job_id, onStatusError]);
  useEffect(() => {
    const controller = new AbortController();
    setCurrentTime(0); setFramePage(null); setFrameState("idle"); setEvents([]); setProgress(null);
    void fetchEvents(controller.signal);
    return () => controller.abort();
  }, [job.job_id, fetchEvents]);
  useEffect(() => {
    const stop = api.subscribeProgress(job.job_id, (event) => { setProgress(event); onProgress(event); }, (error) => onStatusError(error.message));
    return stop;
  }, [job.job_id, onProgress, onStatusError]);
  useEffect(() => {
    if (!["completed", "failed", "cancelled"].includes(activeState)) return;
    const controller = new AbortController();
    void fetchEvents(controller.signal);
    return () => controller.abort();
  }, [activeState, fetchEvents]);
  useEffect(() => {
    if (!duration || (activeState !== "completed" && activeState !== "running")) return;
    const controller = new AbortController();
    setFrameState("loading");
    const timer = window.setTimeout(() => api.getDetections(job.job_id, windowStart, windowEnd, controller.signal).then((page) => { if (!controller.signal.aborted) { setFramePage(page); setFrameState("ready"); } }).catch((error) => { if (!controller.signal.aborted) { setFrameState("error"); if ((error as ApiClientError).code !== "results_not_ready") onStatusError(errorMessage(error)); } }), 120);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [activeState, duration, job.job_id, onStatusError, windowEnd, windowStart]);

  const currentPage = framePage?.from_seconds === windowStart ? framePage : null;
  const frame = nearestFrame(currentPage, currentTime, Math.max(0.65, job.analysis_options.sample_interval_seconds * 1.5));
  const seek = (time: number) => { const video = videoRef.current; const target = Math.max(0, Math.min(duration || (video && Number.isFinite(video.duration) ? video.duration : 0), time)); if (!video) { setCurrentTime(target); return; } if (video.readyState === 0) pendingSeek.current = target; try { video.currentTime = target; setCurrentTime(target); } catch { pendingSeek.current = target; } };
  const metadata = job.video;
  return <section className="analysis-panel" aria-labelledby="analysis-heading">
    <div className="analysis-heading"><div><p className="eyebrow">ANALYSIS</p><h2 id="analysis-heading">{job.file_name}</h2></div><span className={`state-pill pill-${activeState}`}><span className="state-indicator" />{stateLabel(activeState)}</span></div>
    <ProgressBanner job={job} progress={progress} onRetry={fetchEvents} />
    {activeState === "failed" ? <div className="result-empty error-empty"><strong>Analysis failed</strong><p>{progress?.error?.message ?? job.error?.message ?? "The local service could not finish this task."}</p></div> : <>
      <div className="player-shell" ref={setContainer}>
        {videoUrl ? <video ref={videoRef} src={videoUrl} controls playsInline preload="metadata" onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)} onLoadedMetadata={(event) => { const pending = pendingSeek.current; if (pending !== null) { pendingSeek.current = null; event.currentTarget.currentTime = Math.min(event.currentTarget.duration, pending); } setCurrentTime(event.currentTarget.currentTime); }} /> : <div className="video-placeholder">{job.job_id === "mock-demo" ? "Demo preview · no source video" : "Video playback will be available when the local file is ready."}</div>}
        {frame && metadata && <DetectionOverlay container={container} detections={frame.detections} displayWidth={metadata.display_width} displayHeight={metadata.display_height} />}
        {frameState === "loading" && <span className="frame-loading">Loading detections</span>}
      </div>
      <div className="video-info"><span>{formatTime(currentTime)} / {formatTime(duration)}</span><span>{metadata ? `${metadata.display_width} × ${metadata.display_height}` : "Metadata unavailable"}{metadata?.rotation_degrees ? ` · ${metadata.rotation_degrees}°` : ""}</span><span>{metadata?.variable_frame_rate ? "Variable frame rate" : metadata?.average_frame_rate ? `${metadata.average_frame_rate} fps` : "Frame rate unavailable"}</span></div>
      <EventTimeline duration={duration} currentTime={currentTime} events={events} onSeek={seek} />
      <div className="results-heading"><div><h3>Bird events</h3><p>{events.length ? "Select an event to jump to its start." : eventsState === "error" ? "Event results could not be loaded." : eventsState === "loading" ? "Loading event results…" : activeState === "completed" ? "No bird events were found in this video." : "Events will appear as analysis commits results."}</p></div><span>{events.length} {events.length === 1 ? "event" : "events"}</span></div>
      {events.length > 0 && <ul className="event-list">{events.map((event) => <li key={event.event_id}><button type="button" onClick={() => seek(event.start_seconds)}><span className="event-swatch" /><span><strong>{formatTime(event.start_seconds)} – {formatTime(event.end_seconds)}</strong><small>{event.track_ids.length ? `${event.track_ids.length} tracked bird${event.track_ids.length === 1 ? "" : "s"}` : `${event.detection_count} bird detection${event.detection_count === 1 ? "" : "s"}`} · {Math.round(event.max_confidence * 100)}% confidence</small></span><span className="event-arrow">→</span></button></li>)}</ul>}
      {eventsState === "error" && <button type="button" className="text-button" onClick={() => fetchEvents()}>Retry event results</button>}
      {activeState === "completed" && job.detection_count > 0 && (!frame || frame.detections.length === 0) && frameState === "ready" && <p className="frame-empty">No detections near {formatTime(currentTime)}.</p>}
      {activeState === "completed" && job.detection_count === 0 && <p className="frame-empty">No birds detected in this video.</p>}
      {frameState === "error" && <p className="inline-error">Detection frames are unavailable for this time range.</p>}
    </>}
  </section>;
}

export default function App() {
  const [health, setHealth] = useState<"checking" | "ready" | "offline">("checking"); const [jobs, setJobs] = useState<JobSummary[]>([]); const [jobsCursor, setJobsCursor] = useState<string | null>(null); const [selected, setSelected] = useState<JobDetail | null>(null); const [jobLoad, setJobLoad] = useState<LoadState>("loading"); const [jobError, setJobError] = useState<string | null>(null); const [apiError, setApiError] = useState<string | null>(null);
  const loadJobs = useCallback(async () => { setJobLoad("loading"); setJobError(null); try { const page = await api.listJobs(); setJobs(page.items); setJobsCursor(page.next_cursor); setJobLoad("ready"); } catch (error) { setJobLoad("error"); setJobError(errorMessage(error)); } }, []);
  const loadMoreJobs = useCallback(async () => { if (!jobsCursor) return; setJobLoad("loading"); setJobError(null); try { const page = await api.listJobs(undefined, jobsCursor); setJobs((current) => [...current, ...page.items]); setJobsCursor(page.next_cursor); setJobLoad("ready"); } catch (error) { setJobLoad("error"); setJobError(errorMessage(error)); } }, [jobsCursor]);
  const chooseJob = useCallback(async (jobId: string) => { setApiError(null); try { setSelected(await api.getJob(jobId)); } catch (error) { setApiError(errorMessage(error)); } }, []);
  const onProgress = useCallback((progress: ProgressEvent) => {
    setSelected((current) => current?.job_id === progress.job_id ? { ...current, state: progress.state, updated_at: progress.updated_at, finished_at: ["completed", "failed", "cancelled"].includes(progress.state) ? progress.updated_at : null, progress: { processed_seconds: progress.processed_seconds, duration_seconds: progress.duration_seconds, processed_frames: progress.processed_frames, total_frames: progress.total_frames }, error: progress.error ?? null } : current);
    setJobs((current) => current.map((job) => job.job_id === progress.job_id ? { ...job, state: progress.state, updated_at: progress.updated_at, finished_at: ["completed", "failed", "cancelled"].includes(progress.state) ? progress.updated_at : null, progress: { processed_seconds: progress.processed_seconds, duration_seconds: progress.duration_seconds, processed_frames: progress.processed_frames, total_frames: progress.total_frames }, error: progress.error ?? null } : job));
    if (["completed", "failed", "cancelled"].includes(progress.state)) {
      void api.getJob(progress.job_id).then((detail) => {
        setSelected((current) => current?.job_id === detail.job_id ? detail : current);
        setJobs((current) => current.map((job) => job.job_id === detail.job_id ? detail : job));
      }).catch((error) => setApiError(errorMessage(error)));
    }
  }, []);
  useEffect(() => { api.getHealth().then(() => setHealth("ready")).catch(() => setHealth("offline")); loadJobs(); }, [loadJobs]);
  const uploaded = (job: JobDetail) => { setJobs((items) => [job, ...items.filter((item) => item.job_id !== job.job_id)]); setSelected(job); setApiError(null); };
  return <main className="app-shell">
    <header className="topbar"><div className="brand-mark" aria-hidden="true">B</div><div><p className="eyebrow">LOCAL BIRD ANALYSIS</p><h1>Bird video analyzer</h1></div><span className={`service-status service-${health}`}><span />{health === "ready" ? "Local service ready" : health === "offline" ? "Local service offline" : "Checking local service"}</span></header>
    <UploadPanel onUploaded={uploaded} />
    {apiError && <p className="inline-error global-error" role="alert">{apiError}</p>}
    <div className="main-grid"><JobList jobs={jobs} selectedId={selected?.job_id ?? null} loading={jobLoad === "loading"} error={jobError} hasMore={jobsCursor !== null} onSelect={chooseJob} onLoadMore={loadMoreJobs} onRetry={loadJobs} />
      {selected ? <AnalysisView job={selected} onStatusError={setApiError} onProgress={onProgress} /> : <section className="analysis-panel empty-analysis"><div className="empty-symbol" aria-hidden="true">⌁</div><h2>Select a task to inspect results</h2><p>Upload a video or choose a task from the list. Detection boxes and bird event ranges will appear here.</p></section>}
    </div>
    <footer><span>Processing stays on this computer.</span><span className={`footer-service footer-${health}`}>{health === "offline" ? "Start the local API to enable uploads" : import.meta.env.VITE_USE_MOCK === "true" ? "Synthetic UI preview" : `API ${new URL(import.meta.env.VITE_API_TARGET ?? "http://127.0.0.1:8000").host}`}</span></footer>
  </main>;
}
