import { basename, resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import type { components } from "../src/api/schema";

type JobDetail = components["schemas"]["JobDetail"];

function fixtureJob(jobId: string, fileName: string, state: "completed" | "failed"): JobDetail {
  const error = state === "failed" ? {
    code: "detector_unavailable",
    message: "YOLO11n weights are missing. Run scripts/setup.ps1 -WithDetector.",
    details: null,
    request_id: "browser-test",
  } : null;
  return {
    job_id: jobId,
    source_job_id: null,
    file_name: fileName,
    state,
    created_at: "2026-10-30T00:00:00Z",
    updated_at: "2026-10-30T00:00:01Z",
    finished_at: "2026-10-30T00:00:01Z",
    progress: { processed_seconds: 4, duration_seconds: 4, processed_frames: 10, total_frames: 10 },
    error,
    video: {
      duration_seconds: 4,
      coded_width: 640,
      coded_height: 360,
      display_width: 640,
      display_height: 360,
      rotation_degrees: 0,
      average_frame_rate: 25,
      variable_frame_rate: false,
      video_codec: "h264",
      has_audio: false,
    },
    video_url: null,
    analysis_options: { sample_interval_seconds: 0.4, confidence_threshold: 0.25 },
    detection_count: 0,
    event_count: 0,
  };
}

async function mockJobApi(page: Page, job: JobDetail) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/health") {
      await route.fulfill({ json: { status: "ok", service: "bird-video-analyzer", version: "0.1.0", mode: "local" } });
    } else if (path === "/api/jobs") {
      await route.fulfill({ json: { items: [job], next_cursor: null } });
    } else if (path === `/api/jobs/${job.job_id}`) {
      await route.fulfill({ json: job });
    } else if (path.endsWith("/events")) {
      await route.fulfill({ json: { items: [], next_cursor: null } });
    } else if (path.endsWith("/detections")) {
      await route.fulfill({ json: { from_seconds: 0, to_seconds: 4, frames: [], next_cursor: null } });
    } else if (path.endsWith("/progress")) {
      const progress = {
        ...job.progress,
        job_id: job.job_id,
        state: job.state,
        updated_at: job.updated_at,
        error: job.error,
      };
      await route.fulfill({
        contentType: "text/event-stream",
        body: `id: 1\nevent: progress\ndata: ${JSON.stringify(progress)}\n\n`,
      });
    } else {
      await route.abort();
    }
  });
}

test("real local detector upload plays, draws a box, seeks an event, and survives refresh", async ({ page }) => {
  const videoPath = process.env.BIRD_TEST_VIDEO;
  test.skip(!videoPath, "Set BIRD_TEST_VIDEO to a local bird video before running the real workflow.");
  test.setTimeout(180_000);

  const fileName = basename(videoPath!);
  const rangeResponse = page.waitForResponse(
    (response) => response.url().includes("/video") && response.status() === 206,
    { timeout: 120_000 },
  ).catch(() => null);
  await page.goto("/");
  await expect(page.getByText("Local service ready")).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(resolve(videoPath!));
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page.getByRole("heading", { name: fileName })).toBeVisible();
  await expect(page.locator(".state-pill")).toContainText("Completed", { timeout: 120_000 });
  await expect(page.locator(".event-list li").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".event-list small").first()).toContainText("bird detection");
  await expect(page.locator(".timeline-event").first()).toBeVisible();
  await page.waitForFunction(() => (document.querySelector("video")?.readyState ?? 0) >= 1);

  const videoSource = await page.locator("video").getAttribute("src");
  const jobId = new URL(videoSource!, page.url()).pathname.split("/")[3];
  const events = await page.evaluate(async (id) => {
    const response = await fetch(`/api/jobs/${id}/events`);
    return (await response.json()).items;
  }, jobId);
  expect(events.length).toBeGreaterThan(0);

  await page.locator(".event-list li button").first().click();
  await page.waitForFunction((start) => Math.abs((document.querySelector("video")?.currentTime ?? 0) - start) < 0.15, events[0].start_seconds);
  await page.waitForFunction(() => (document.querySelector("video")?.readyState ?? 0) >= 2);
  await expect(page.locator(".detection-box").first()).toBeVisible({ timeout: 20_000 });
  const frameBrightness = await page.locator("video").evaluate((video) => {
    const canvas = document.createElement("canvas");
    canvas.width = 64; canvas.height = 36;
    const context = canvas.getContext("2d")!;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let total = 0;
    for (let index = 0; index < pixels.length; index += 4) total += (pixels[index] + pixels[index + 1] + pixels[index + 2]) / 3;
    return total / (pixels.length / 4);
  });
  expect(frameBrightness).toBeGreaterThan(5);
  const rangedVideo = await rangeResponse;
  expect(rangedVideo?.status()).toBe(206);

  await page.screenshot({ path: "test-results-real/detected-bird.png", fullPage: true });
  await page.reload();
  await page.getByRole("button", { name: new RegExp(fileName) }).first().click();
  await expect(page.locator(".state-pill")).toContainText("Completed");
  await expect(page.locator(".event-list li").first()).toBeVisible();
  await page.locator(".timeline-event").first().click();
  await page.waitForFunction((start) => Math.abs((document.querySelector("video")?.currentTime ?? 0) - start) < 0.15, events[0].start_seconds);
  await page.waitForFunction(() => (document.querySelector("video")?.readyState ?? 0) >= 2);
  await expect(page.locator(".detection-box").first()).toBeVisible({ timeout: 20_000 });
});

test("a completed job with no detections shows the empty result state", async ({ page }) => {
  const job = fixtureJob("empty-result", "quiet-field.mp4", "completed");
  await mockJobApi(page, job);
  await page.goto("/");
  await page.getByRole("button", { name: /quiet-field\.mp4/ }).click();

  await expect(page.locator(".state-pill")).toContainText("Completed");
  await expect(page.getByText("No bird events were found in this video.")).toBeVisible();
  await expect(page.getByText("No birds detected in this video.")).toBeVisible();
  await expect(page.locator(".event-list li")).toHaveCount(0);
});

test("a failed detector task shows its error and does not stay in progress", async ({ page }) => {
  const job = fixtureJob("failed-result", "missing-model.mp4", "failed");
  await mockJobApi(page, job);
  await page.goto("/");
  await page.getByRole("button", { name: /missing-model\.mp4/ }).click();

  await expect(page.locator(".state-pill")).toContainText("Failed");
  await expect(page.locator(".error-empty")).toContainText("YOLO11n weights are missing");
  await expect(page.locator(".task-progress")).toHaveCount(0);
});
