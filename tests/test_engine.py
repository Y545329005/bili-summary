"""Tests for the summarization engine."""

from bili_summary.summarizer.engine import (
    _format_time,
    format_subtitles,
)
from bili_summary.bilibili.subtitle import SubtitleSegment


class TestFormatTime:
    def test_zero(self):
        assert _format_time(0) == "00:00"

    def test_seconds_only(self):
        assert _format_time(45) == "00:45"

    def test_minutes_and_seconds(self):
        assert _format_time(125) == "02:05"

    def test_hours(self):
        assert _format_time(3661) == "61:01"


class TestFormatSubtitles:
    def test_format(self):
        segments = [
            SubtitleSegment(from_sec=0.0, to_sec=3.0, content="大家好"),
            SubtitleSegment(from_sec=3.0, to_sec=6.0, content="今天我们来聊聊"),
        ]
        result = format_subtitles(segments)
        lines = result.split("\n")
        assert lines[0] == "[00:00] 大家好"
        assert lines[1] == "[00:03] 今天我们来聊聊"
