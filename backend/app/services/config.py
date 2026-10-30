from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AnalysisOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_interval_seconds: float = Field(default=0.4, gt=0, le=5)
    confidence_threshold: float = Field(default=0.25, ge=0, le=1)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_upload_bytes: int = 2 * 1024 * 1024 * 1024
    upload_reserve_bytes: int = 1024 * 1024
    event_merge_gap_seconds: float = 0.8
    allowed_extensions: tuple[str, ...] = (".mp4", ".mov", ".m4v", ".mkv", ".webm")
    default_options: AnalysisOptions = field(default_factory=AnalysisOptions)

    @classmethod
    def from_environment(cls) -> Settings:
        raw_dir = Path(os.getenv("BIRD_DATA_DIR", "../bird-data")).expanduser()
        data_dir = raw_dir if raw_dir.is_absolute() else Path.cwd() / raw_dir
        raw_extensions = os.getenv("BIRD_ALLOWED_EXTENSIONS")
        extensions = (
            tuple(
                extension.strip().lower()
                if extension.strip().startswith(".")
                else f".{extension.strip().lower()}"
                for extension in raw_extensions.split(",")
                if extension.strip()
            )
            if raw_extensions
            else cls.__dataclass_fields__["allowed_extensions"].default
        )
        return cls(
            data_dir=data_dir.resolve(),
            max_upload_bytes=int(os.getenv("BIRD_MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024))),
            upload_reserve_bytes=int(os.getenv("BIRD_UPLOAD_RESERVE_BYTES", str(1024 * 1024))),
            event_merge_gap_seconds=float(os.getenv("BIRD_EVENT_MERGE_GAP_SECONDS", "0.8")),
            allowed_extensions=extensions,
            default_options=AnalysisOptions(
                sample_interval_seconds=float(os.getenv("BIRD_SAMPLE_INTERVAL_SECONDS", "0.4")),
                confidence_threshold=float(os.getenv("BIRD_CONFIDENCE_THRESHOLD", "0.25")),
            ),
        )
