import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("contract API client", () => {
  it("loads long detection ranges as successive bounded pages", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ from_seconds: 0, to_seconds: 5, frames: [{ timestamp: 1, detections: [] }], next_cursor: "page-2" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ from_seconds: 0, to_seconds: 5, frames: [{ timestamp: 2, detections: [] }], next_cursor: null }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const page = await api.getDetections("job-1", 0, 5);

    expect(page.frames.map((frame) => frame.timestamp)).toEqual([1, 2]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0][0])).toContain("from_seconds=0&to_seconds=5&limit=1000");
    expect(String(fetchMock.mock.calls[1][0])).toContain("cursor=page-2");
  });

  it("preserves the contract error code and message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "results_not_ready", message: "Results are not ready.", details: null, request_id: "r1" } }), { status: 409 })));
    await expect(api.getDetections("job-1", 0, 5)).rejects.toMatchObject({ code: "results_not_ready", message: "Results are not ready.", status: 409 });
  });

});
