// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { JobSummary } from "./api/client";
import { EventTimeline } from "./components/EventTimeline";
import { JobList } from "./components/JobList";
import { formatTime, mapBbox, nearestFrame, validateVideoFile } from "./ui";

describe("video UI helpers", () => {
  it("validates supported local video files and rejects unsupported formats", () => {
    expect(validateVideoFile(new File(["video"], "field.MP4"))).toBeNull();
    expect(validateVideoFile(new File(["video"], "notes.txt"))).toContain("Supported formats");
    expect(validateVideoFile(null)).toContain("Choose a video");
  });

  it("maps normalized boxes into a contained portrait or letterboxed display region", () => {
    const box = mapBbox([0.25, 0.2, 0.75, 0.8], { left: 0, top: 0, width: 400, height: 400 }, 1600, 900);
    expect(box.left).toBe(100); expect(box.top).toBe(132.5); expect(box.width).toBe(200); expect(box.height).toBeCloseTo(135);
  });

  it("does not reuse a sampled frame outside its display tolerance", () => {
    const page = { from_seconds: 0, to_seconds: 5, next_cursor: null, frames: [{ timestamp: 1, detections: [] }] };
    expect(nearestFrame(page, 1.2, 0.5)?.timestamp).toBe(1);
    expect(nearestFrame(page, 4.5, 0.5)).toBeNull();
    expect(formatTime(3661.8)).toBe("1:01:01");
  });
});

describe("event timeline and task list", () => {
  it("keeps event positions relative to duration and seeks to the interval start", () => {
    const onSeek = vi.fn();
    render(<EventTimeline duration={40} currentTime={10} events={[{ event_id: "e1", start_seconds: 8, end_seconds: 12, track_ids: [1], max_confidence: 0.9, detection_count: 4 }]} onSeek={onSeek} />);
    const event = screen.getByRole("button", { name: "Jump to bird event at 00:08" });
    expect(event.style.left).toBe("20%");
    expect(event.style.width).toBe("10%");
    fireEvent.click(event);
    expect(onSeek).toHaveBeenCalledWith(8);
    expect(screen.getByText("00:40")).toBeTruthy();
  });

  it("shows task state and opens the selected task", () => {
    const job: JobSummary = { job_id: "j1", source_job_id: null, file_name: "wetland.mp4", state: "running", created_at: "2026-10-30T00:00:00Z", updated_at: "2026-10-30T00:00:00Z", finished_at: null, progress: { processed_seconds: 10, duration_seconds: 20, processed_frames: 25, total_frames: 50 }, error: null };
    const onSelect = vi.fn();
    render(<JobList jobs={[job]} selectedId="j1" loading={false} error={null} hasMore={false} onSelect={onSelect} onLoadMore={() => undefined} onRetry={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: /wetland\.mp4/ }));
    expect(screen.getByText("Analyzing · 00:20")).toBeTruthy();
    expect(screen.getByText("50%")).toBeTruthy();
    expect(onSelect).toHaveBeenCalledWith("j1");
  });
});
