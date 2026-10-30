import type { JobSummary } from "../api/client";
import { formatTime, stateLabel } from "../ui";

export function JobList({ jobs, selectedId, loading, error, hasMore, onSelect, onLoadMore, onRetry }: {
  jobs: JobSummary[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  onSelect: (id: string) => void;
  onLoadMore: () => void;
  onRetry: () => void;
}) {
  return <section className="job-list-section" aria-labelledby="jobs-heading">
    <div className="list-heading"><h2 id="jobs-heading">Recent tasks</h2><button type="button" className="text-button" onClick={onRetry} disabled={loading}>Refresh</button></div>
    {error && <p className="inline-error" role="alert">{error} <button type="button" className="text-button" onClick={onRetry}>Retry</button></p>}
    {!error && !jobs.length && !loading && <p className="list-empty">Uploaded videos will appear here.</p>}
    <ul className="job-list">
      {jobs.map((job) => <li key={job.job_id}>
        <button type="button" className={`job-item ${selectedId === job.job_id ? "selected" : ""}`} aria-current={selectedId === job.job_id ? "page" : undefined} onClick={() => onSelect(job.job_id)}>
          <span className={`state-indicator state-${job.state}`} aria-hidden="true" />
          <span className="job-copy"><span className="job-name" title={job.file_name}>{job.file_name}</span><span className="job-meta">{stateLabel(job.state)} · {formatTime(job.progress.duration_seconds ?? 0)}</span></span>
          <span className="job-percent">{job.progress.duration_seconds && job.state === "running" ? `${Math.min(100, Math.round(job.progress.processed_seconds / job.progress.duration_seconds * 100))}%` : ""}</span>
        </button>
      </li>)}
    </ul>
    {loading && !jobs.length && <p className="list-empty">Loading tasks…</p>}
    {hasMore && <button type="button" className="load-more" onClick={onLoadMore} disabled={loading}>{loading ? "Loading…" : "Load more tasks"}</button>}
  </section>;
}
