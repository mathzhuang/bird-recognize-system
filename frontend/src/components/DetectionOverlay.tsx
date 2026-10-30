import { useEffect, useState } from "react";
import type { components } from "../api/schema";
import { mapBbox } from "../ui";

type Detection = components["schemas"]["Detection"];
type Rect = { left: number; top: number; width: number; height: number };

export function DetectionOverlay({ container, detections, displayWidth, displayHeight }: {
  container: HTMLElement | null;
  detections: Detection[];
  displayWidth: number;
  displayHeight: number;
}) {
  const [rect, setRect] = useState<Rect | null>(null);
  useEffect(() => {
    if (!container) { setRect(null); return; }
    const update = () => { const box = container.getBoundingClientRect(); setRect({ left: box.left, top: box.top, width: box.width, height: box.height }); };
    update();
    const observer = new ResizeObserver(update); observer.observe(container);
    window.addEventListener("resize", update); window.addEventListener("scroll", update, true);
    return () => { observer.disconnect(); window.removeEventListener("resize", update); window.removeEventListener("scroll", update, true); };
  }, [container]);

  if (!rect || !displayWidth || !displayHeight) return null;
  const contentScale = Math.min(rect.width / displayWidth, rect.height / displayHeight);
  const contentHeight = displayHeight * contentScale;
  const insetY = (rect.height - contentHeight) / 2;
  return <div className="detection-overlay" aria-label={`${detections.length} bird detections`}>
    {detections.map((detection, index) => {
      const [x1, y1, x2, y2] = detection.bbox;
      if (![x1, y1, x2, y2].every(Number.isFinite) || x1 >= x2 || y1 >= y2) return null;
      const box = mapBbox(detection.bbox, { left: 0, top: 0, width: rect.width, height: rect.height }, displayWidth, displayHeight);
      return <div key={`${detection.track_id ?? "bird"}-${index}`} className="detection-box" style={{ left: box.left, top: box.top, width: box.width, height: box.height }}>
        <span className={`detection-label ${box.top - insetY < 25 ? "label-inside" : ""}`}>Bird {detection.track_id ?? index + 1} · {Math.round(detection.confidence * 100)}%</span>
      </div>;
    })}
  </div>;
}
