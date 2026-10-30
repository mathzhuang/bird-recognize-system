from __future__ import annotations

import pytest

from app.detectors import Detection
from app.tracking import EventBuilder


def _bird(timestamp: float, confidence: float, track_id: int | None = None) -> Detection:
    return Detection(timestamp, (0.2, 0.2, 0.4, 0.4), confidence, "bird", track_id)


def test_empty_video_has_no_events() -> None:
    builder = EventBuilder(duration_seconds=4, sample_interval_seconds=0.4)

    assert builder.observe(0, []) == ()
    assert builder.observe(2, []) == ()
    assert builder.finish() == ()


def test_multibird_detections_and_short_miss_form_one_event() -> None:
    builder = EventBuilder(duration_seconds=3, sample_interval_seconds=0.4, max_detection_gap_seconds=0.8)
    builder.observe(0.2, [_bird(0.2, 0.71, 8), _bird(0.2, 0.94, 3)])
    builder.observe(0.6, [])
    builder.observe(1.0, [_bird(1.0, 0.82, 8)])

    events = builder.finish()

    assert len(events) == 1
    event = events[0]
    assert event.start_seconds == 0.1
    assert event.end_seconds == 1.5
    assert event.track_ids == (3, 8)
    assert event.max_confidence == 0.94
    assert event.detection_count == 3
    assert event.contract_dict()["track_ids"] == [3, 8]
    assert event.contract_dict()["end_seconds"] > event.contract_dict()["start_seconds"]


def test_far_apart_detections_are_separate_events_without_track_ids() -> None:
    builder = EventBuilder(
        duration_seconds=5,
        sample_interval_seconds=0.4,
        max_detection_gap_seconds=0.8,
        boundary_padding_seconds=0,
    )

    assert builder.observe(0.5, [_bird(0.5, 0.7)]) == ()
    emitted = builder.observe(2.0, [_bird(2.0, 0.9)])
    final = builder.finish()

    assert len(emitted) == 1
    assert len(final) == 1
    assert emitted[0].track_ids == ()
    assert emitted[0].start_seconds == 0.5
    assert emitted[0].end_seconds == 0.9
    assert final[0].start_seconds == 2.0
    assert final[0].end_seconds == 2.4


def test_events_are_half_open_and_bounded_by_video_duration() -> None:
    builder = EventBuilder(duration_seconds=2, sample_interval_seconds=0.4)
    builder.observe(1.9, [_bird(1.9, 0.8, 2)])

    (event,) = builder.finish()

    assert event.end_seconds == 2
    assert event.start_seconds == pytest.approx(1.8)


def test_observations_must_follow_video_presentation_timeline() -> None:
    builder = EventBuilder(duration_seconds=2, sample_interval_seconds=0.4)
    builder.observe(1.0, [])

    try:
        builder.observe(0.9, [])
    except ValueError as error:
        assert "ordered by presentation timestamp" in str(error)
    else:
        raise AssertionError("out-of-order timestamps should fail")
