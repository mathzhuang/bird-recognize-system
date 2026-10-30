import { defineConfig } from "@playwright/test";

const frontendPort = Number(process.env.BIRD_E2E_FRONTEND_PORT ?? 5181);

export default defineConfig({
  testDir: "./browser-tests",
  testMatch: "real-workflow.spec.ts",
  reporter: "list",
  outputDir: "./test-results-real",
  timeout: 180_000,
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    browserName: "chromium",
    channel: "msedge",
    headless: true,
    viewport: { width: 1440, height: 1000 },
  },
  webServer: {
    command: `node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${frontendPort} --strictPort`,
    url: `http://127.0.0.1:${frontendPort}`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: { VITE_API_TARGET: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000" },
  },
});
