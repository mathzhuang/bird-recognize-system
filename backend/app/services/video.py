from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import av
import numpy as np


class InvalidVideo(Exception):
    pass


@dataclass(frozen=True)
class ProbeResult:
    video: dict[str, object]
    total_frames: int | None
    media_type: str


@dataclass(frozen=True)
class VideoSample:
    timestamp: float
    image: np.ndarray
    width: int
    height: int


MIME_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
}


def probe_video(path: Path, extension: str) -> ProbeResult:
    try:
        with av.open(str(path), mode="r") as container:
            if not container.streams.video:
                raise InvalidVideo("The uploaded file does not contain a video stream.")
            stream = container.streams.video[0]
            coded_width = int(stream.codec_context.width or stream.width or 0)
            coded_height = int(stream.codec_context.height or stream.height or 0)
            if coded_width < 1 or coded_height < 1:
                raise InvalidVideo("The video stream has invalid dimensions.")
            first_frame = next(container.decode(video=stream.index), None)
            if first_frame is None:
                raise InvalidVideo("The video stream contains no decodable frames.")
            rotation_ccw = float(first_frame.rotation or 0)
            rotation_clockwise = _normalize_rotation(-rotation_ccw)
            quarter_turn = int(round(rotation_clockwise / 90)) % 2
            duration = _stream_duration(stream)
            if duration is None:
                duration = container.duration / av.time_base if container.duration is not None else None
            if duration is None or not math.isfinite(duration) or duration <= 0:
                raise InvalidVideo("The video's duration could not be determined.")
            average_rate = _rate(stream.average_rate)
            base_rate = _rate(stream.base_rate)
            variable_frame_rate = (
                abs(average_rate - base_rate) > max(0.01, average_rate * 0.01)
                if average_rate is not None and base_rate is not None
                else None
            )
            video = {
                "duration_seconds": float(duration),
                "coded_width": coded_width,
                "coded_height": coded_height,
                "display_width": coded_height if quarter_turn else coded_width,
                "display_height": coded_width if quarter_turn else coded_height,
                "rotation_degrees": rotation_clockwise,
                "average_frame_rate": average_rate,
                "variable_frame_rate": variable_frame_rate,
                "video_codec": stream.codec_context.name,
                "has_audio": bool(container.streams.audio),
            }
            total_frames = int(stream.frames) if stream.frames and stream.frames > 0 else None
            return ProbeResult(video, total_frames, _media_type(container.format.name, extension))
    except InvalidVideo:
        raise
    except (av.error.FFmpegError, OSError, ValueError, ZeroDivisionError, StopIteration) as exc:
        raise InvalidVideo("The uploaded file is not a supported, readable video.") from exc


def iter_sampled_frames(path: Path, interval_seconds: float) -> Iterator[VideoSample]:
    try:
        with av.open(str(path), mode="r") as container:
            if not container.streams.video:
                raise InvalidVideo("The source video stream is missing.")
            stream = container.streams.video[0]
            first_timestamp: float | None = None
            next_sample = 0.0
            for frame in container.decode(video=stream.index):
                time_base = frame.time_base or stream.time_base
                if frame.pts is None or time_base is None:
                    raise InvalidVideo("A decoded video frame has no presentation timestamp.")
                raw_timestamp = float(frame.pts * time_base)
                if first_timestamp is None:
                    first_timestamp = raw_timestamp
                timestamp = max(0.0, raw_timestamp - first_timestamp)
                if timestamp + 1e-9 < next_sample:
                    continue
                rotation_ccw = float(frame.rotation or 0)
                pixels = frame.to_ndarray(format="rgb24")
                if abs(rotation_ccw) >= 45:
                    pixels = np.rot90(pixels, k=int(round(rotation_ccw / 90)), axes=(0, 1)).copy()
                height, width = pixels.shape[:2]
                yield VideoSample(timestamp, pixels, width, height)
                next_sample = timestamp + interval_seconds
    except InvalidVideo:
        raise
    except (av.error.FFmpegError, OSError, ValueError) as exc:
        raise InvalidVideo("The source video could not be decoded.") from exc


def _stream_duration(stream: av.stream.Stream) -> float | None:
    if stream.duration is None or stream.time_base is None:
        return None
    return float(stream.duration * stream.time_base)


def _rate(rate: object) -> float | None:
    if rate is None:
        return None
    try:
        value = float(rate)  # type: ignore[arg-type]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _normalize_rotation(degrees: float) -> float:
    normalized = ((degrees + 180) % 360) - 180
    return 0.0 if abs(normalized) < 0.01 else normalized


def _media_type(format_name: str, extension: str) -> str:
    formats = set(format_name.lower().split(","))
    if "webm" in formats:
        return "video/webm"
    if "matroska" in formats:
        return "video/x-matroska"
    return MIME_TYPES[extension]
