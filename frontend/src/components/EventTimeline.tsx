import type { components } from "../api/schema";
import { formatTime } from "../ui";

type BirdEvent = components["schemas"]["BirdEvent"];

export function EventTimeline({ duration, currentTime, events, onSeek }: {
  duration: number;
  currentTime: number;
  events: BirdEvent[];
  onSeek: (seconds: number) => void;
}) {
  if (!Number.isFinite(duration) || duration <= 0) return <p className="timeline-unavailable">Timeline available after video metadata loads.</p>;
  return (
    <div className="timeline" aria-label="Video event timeline">
      <div className="timeline-track" onClick={(event) => {
        if ((event.target as HTMLElement).closest("button")) return;
        const rect = event.currentTarget.getBoundingClientRect();
        onSeek(Math.max(0, Math.min(duration, (event.clientX - rect.left) / rect.width * duration)));
      }}>
        {events.map((item) => {
          const start = Math.max(0, Math.min(duration, item.start_seconds));
          const end = Math.max(start, Math.min(duration, item.end_seconds));
          if (end <= start) return null;
          return <button key={item.event_id} type="button" className="timeline-event" aria-label={`Jump to bird event at ${formatTime(start)}`} title={`${formatTime(start)} to ${formatTime(end)}`} style={{ left: `${start / duration * 100}%`, width: `${(end - start) / duration * 100}%` }} onClick={() => onSeek(start)} />;
        })}
        <span className="timeline-playhead" aria-hidden="true" style={{ left: `${Math.max(0, Math.min(100, currentTime / duration * 100))}%` }} />
      </div>
      <div className="timeline-ticks" aria-hidden="true">
        {[0, 0.25, 0.5, 0.75, 1].map((position) => <span key={position}>{formatTime(duration * position)}</span>)}
      </div>
    </div>
  );
}
