from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import av
import numpy as np


def make_video(path: Path, frame_count: int = 10, rate: int = 10, pts_values: list[int] | None = None) -> Path:
    pts_values = pts_values or list(range(frame_count))
    if len(pts_values) != frame_count:
        raise ValueError("pts_values must contain one PTS per frame")
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("mpeg4", rate=rate)
        stream.width = 32
        stream.height = 24
        stream.pix_fmt = "yuv420p"
        for index in range(frame_count):
            pixels = np.full((24, 32, 3), index * 15 % 255, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = pts_values[index]
            frame.time_base = Fraction(1, rate)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path
