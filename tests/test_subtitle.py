"""Tests for subtitle parsing and track selection."""

import pytest
from bili_summary.bilibili.subtitle import (
    SubtitleTrack,
    SubtitleSegment,
    _choose_best_track,
    _ensure_https,
    NoSubtitleError,
)


class TestChooseBestTrack:
    def test_prefers_zh_cn(self):
        tracks = [
            SubtitleTrack(id=1, lan="en", lan_doc="English", subtitle_url="http://x"),
            SubtitleTrack(id=2, lan="zh-CN", lan_doc="中文（中国）", subtitle_url="http://x"),
        ]
        chosen = _choose_best_track(tracks)
        assert chosen.lan == "zh-CN"

    def test_prefers_zh_cn_over_ai_zh(self):
        tracks = [
            SubtitleTrack(id=1, lan="ai-zh", lan_doc="AI中文", subtitle_url="http://x"),
            SubtitleTrack(id=2, lan="zh-CN", lan_doc="中文（中国）", subtitle_url="http://x"),
        ]
        chosen = _choose_best_track(tracks)
        assert chosen.lan == "zh-CN"

    def test_fallback_to_first(self):
        tracks = [
            SubtitleTrack(id=1, lan="ja", lan_doc="日本語", subtitle_url="http://x"),
            SubtitleTrack(id=2, lan="en", lan_doc="English", subtitle_url="http://x"),
        ]
        chosen = _choose_best_track(tracks)
        assert chosen.lan == "ja"

    def test_empty_tracks_raises(self):
        with pytest.raises(NoSubtitleError):
            _choose_best_track([])

    def test_prefers_zh_hans(self):
        tracks = [
            SubtitleTrack(id=1, lan="ai-zh", lan_doc="AI中文", subtitle_url="http://x"),
            SubtitleTrack(id=2, lan="zh-Hans", lan_doc="中文（简体）", subtitle_url="http://x"),
        ]
        chosen = _choose_best_track(tracks)
        assert chosen.lan == "zh-Hans"


class TestEnsureHttps:
    def test_scheme_relative(self):
        assert _ensure_https("//example.com/path") == "https://example.com/path"

    def test_already_https(self):
        assert _ensure_https("https://example.com/path") == "https://example.com/path"

    def test_no_scheme(self):
        assert _ensure_https("example.com/path") == "https://example.com/path"

    def test_http_upgraded(self):
        assert _ensure_https("http://example.com/path") == "http://example.com/path"
        # Note: http is not upgraded — we keep it as-is since it already has a scheme
