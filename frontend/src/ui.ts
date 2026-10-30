import type { DetectionPage, JobState } from "./api/client";

export const ACCEPTED_EXTENSIONS = ["mp4", "mov", "m4v", "mkv", "webm"];
export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024;

export function validateVideoFile(file: File | null): string | null {
  if (!file) return "Choose a video file first.";
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!extension || !ACCEPTED_EXTENSIONS.includes(extension)) return "Supported formats: MP4, MOV, M4V, MKV, and WebM.";
  if (file.size > MAX_UPLOAD_BYTES) return "This file is larger than the 2 GB local upload limit.";
  return null;
}

export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00";
  const whole = Math.floor(seconds); const hours = Math.floor(whole / 3600); const minutes = Math.floor((whole % 3600) / 60); const secs = whole % 60;
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}` : `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function mapBbox(bbox: number[], videoRect: { left: number; top: number; width: number; height: number }, displayWidth: number, displayHeight: number) {
  const [x1, y1, x2, y2] = bbox;
  const scale = Math.min(videoRect.width / displayWidth, videoRect.height / displayHeight);
  const renderedWidth = displayWidth * scale; const renderedHeight = displayHeight * scale;
  const offsetX = (videoRect.width - renderedWidth) / 2; const offsetY = (videoRect.height - renderedHeight) / 2;
  return { left: videoRect.left + offsetX + x1 * renderedWidth, top: videoRect.top + offsetY + y1 * renderedHeight, width: (x2 - x1) * renderedWidth, height: (y2 - y1) * renderedHeight };
}

export function nearestFrame(page: DetectionPage | null, time: number, maxDelta = Number.POSITIVE_INFINITY) {
  if (!page?.frames.length) return null;
  const nearest = page.frames.reduce((best, frame) => Math.abs(frame.timestamp - time) < Math.abs(best.timestamp - time) ? frame : best);
  return Math.abs(nearest.timestamp - time) <= maxDelta ? nearest : null;
}

export function stateLabel(state: JobState) {
  return ({ queued: "Queued", probing: "Reading video", running: "Analyzing", completed: "Completed", failed: "Failed", cancelled: "Cancelled" } as Record<JobState, string>)[state];
}
