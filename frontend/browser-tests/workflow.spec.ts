import { expect, test } from "@playwright/test";

test("shows seeded mock results and seeks without a source video", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /demo-bird-video/ }).click();

  await expect(page.getByText("Demo preview · no source video")).toBeVisible();
  await expect(page.locator(".event-list li")).toHaveCount(2);
  await expect(page.locator(".detection-box")).toHaveCount(1);
  await page.getByRole("button", { name: "Jump to bird event at 00:01" }).click();
  await expect(page.locator(".video-info span").first()).toHaveText("00:01 / 00:03");
  await expect(page.locator(".detection-box")).toHaveCount(2);
});

test("uploads a mock video, seeks an event, draws detections, and fits a narrow window", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Local service ready")).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({ name: "garden-clip.webm", mimeType: "video/webm", buffer: Buffer.from("mock video") });
  await page.getByRole("button", { name: "Start analysis" }).click();

  await expect(page.getByRole("heading", { name: "garden-clip.webm" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bird events" })).toBeVisible();
  await expect(page.locator(".event-list li")).toHaveCount(2);
  await page.locator("video").evaluate((element) => {
    const video = element as HTMLVideoElement;
    let mediaTime = 0;
    Object.defineProperty(video, "readyState", { configurable: true, value: 1 });
    Object.defineProperty(video, "duration", { configurable: true, value: 3 });
    Object.defineProperty(video, "currentTime", {
      configurable: true,
      get: () => mediaTime,
      set: (value: number) => { mediaTime = value; video.dispatchEvent(new Event("timeupdate")); },
    });
    video.dispatchEvent(new Event("loadedmetadata"));
  });
  await page.screenshot({ path: "test-results/desktop.png", fullPage: true });

  await page.getByRole("button", { name: "Jump to bird event at 00:01" }).click();
  await page.waitForFunction(() => Math.abs((document.querySelector("video")?.currentTime ?? 0) - 1.5) < 0.02);
  await expect(page.locator(".detection-box")).toHaveCount(2);
  const boxGeometry = await page.locator(".detection-box").first().evaluate((element) => {
    const box = element.getBoundingClientRect(); const stage = element.parentElement!.getBoundingClientRect();
    return { left: box.left - stage.left, top: box.top - stage.top, right: box.right - stage.left, bottom: box.bottom - stage.top, width: stage.width, height: stage.height };
  });
  expect(boxGeometry.left).toBeGreaterThan(0); expect(boxGeometry.top).toBeGreaterThan(0);
  expect(boxGeometry.right).toBeLessThan(boxGeometry.width); expect(boxGeometry.bottom).toBeLessThan(boxGeometry.height);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "Bird events" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});
