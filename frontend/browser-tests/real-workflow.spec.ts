import { basename, resolve } from "node:path";
import { expect, test } from "@playwright/test";

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
