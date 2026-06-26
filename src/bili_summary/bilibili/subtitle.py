"""Bilibili subtitle extraction.

Fetches the subtitle track list from the player API and downloads/parses
the selected subtitle JSON.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Optional

from bili_summary.bilibili.client import BiliClient, BiliAPIError
from bili_summary.bilibili.wbi import get_cached_mixin_key, sign_params
from bili_summary.config import SUBTITLE_PREFERENCE


class NoSubtitleError(Exception):
    """Video has no available subtitle track."""


@dataclass
class SubtitleSegment:
    """A single subtitle segment with timing."""

    from_sec: float
    to_sec: float
    content: str


@dataclass
class SubtitleTrack:
    """A subtitle track from the player API."""

    id: int
    lan: str  # language code, e.g. "zh-CN", "ai-zh"
    lan_doc: str  # display name, e.g. "中文（中国）"
    subtitle_url: str
    is_ai: bool = False


def _choose_best_track(tracks: list[SubtitleTrack]) -> SubtitleTrack:
    """Select the best subtitle track based on preference order.

    Priority: zh-CN > zh-Hans > zh-TW > ai-zh > zh > first available
    """
    if not tracks:
        raise NoSubtitleError("该视频没有可用字幕。")

    # Try each preference in order
    for pref in SUBTITLE_PREFERENCE:
        for track in tracks:
            if track.lan == pref:
                if track.lan == "ai-zh":
                    print(
                        "⚠️  注意：该视频仅有 AI 自动生成字幕，准确度可能较低。",
                        file=sys.stderr,
                    )
                print(
                    f"📝 已选择字幕轨道：{track.lan_doc} ({track.lan})",
                    file=sys.stderr,
                )
                return track

    # Fallback to first available
    track = tracks[0]
    print(
        f"📝 已选择字幕轨道：{track.lan_doc} ({track.lan})",
        file=sys.stderr,
    )
    return track


def _ensure_https(url: str) -> str:
    """Ensure a URL has the https: scheme."""
    if url.startswith("//"):
        return "https:" + url
    if not url.startswith("http"):
        return "https://" + url
    return url


def fetch_subtitle_list(
    client: BiliClient, aid: int, cid: int
) -> list[SubtitleTrack]:
    """Fetch available subtitle tracks for a video.

    Uses the player API with WBI signing.
    """
    # Build WBI-signed params
    params = {"aid": str(aid), "cid": str(cid)}
    mixin_key = get_cached_mixin_key()
    if mixin_key:
        params = sign_params(params, mixin_key)
    else:
        # If no cached keys, try without signing first
        # (the player endpoint may work without WBI for some videos)
        pass

    try:
        data = client.get_json("/x/player/wbi/v2", params=params)
    except BiliAPIError as e:
        # If WBI sign failed, try without signing
        if e.code == -352:
            data = client.get_json("/x/player/wbi/v2", params={"aid": str(aid), "cid": str(cid)})
        else:
            raise

    player_data = data.get("data", {})
    subtitle_info = player_data.get("subtitle", {})
    raw_tracks = subtitle_info.get("subtitles", [])

    tracks = []
    for t in raw_tracks:
        url = t.get("subtitle_url", "")
        if not url:
            continue
        track = SubtitleTrack(
            id=t.get("id", 0),
            lan=t.get("lan", "unknown"),
            lan_doc=t.get("lan_doc", "未知语言"),
            subtitle_url=_ensure_https(url),
            is_ai=t.get("lan", "").startswith("ai-"),
        )
        tracks.append(track)

    return tracks


def fetch_subtitle_content(client: BiliClient, track: SubtitleTrack) -> list[SubtitleSegment]:
    """Download and parse the subtitle JSON content.

    Bilibili subtitle JSON format:
        {"body": [{"from": 0.0, "to": 3.5, "content": "text"}, ...]}
    """
    # Subtitle URLs may be on a different domain, so use a separate request
    import httpx
    resp = httpx.get(
        track.subtitle_url,
        headers={
            "User-Agent": client.headers.get("User-Agent", ""),
            "Referer": "https://www.bilibili.com",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()

    body = data.get("body", [])
    if not body:
        raise NoSubtitleError("字幕内容为空。")

    segments = []
    for item in body:
        content = item.get("content", "").strip()
        if not content:
            continue
        segments.append(
            SubtitleSegment(
                from_sec=item.get("from", 0.0),
                to_sec=item.get("to", 0.0),
                content=content,
            )
        )

    if not segments:
        raise NoSubtitleError("字幕解析后无有效内容。")

    print(f"📝 共解析 {len(segments)} 条字幕。", file=sys.stderr)
    return segments


def get_subtitles(
    client: BiliClient, aid: int, cid: int
) -> tuple[list[SubtitleSegment], SubtitleTrack]:
    """Fetch and return subtitle segments and the selected track.

    Args:
        client: Configured BiliClient.
        aid: Video aid.
        cid: Video cid (page/part identifier).

    Returns:
        Tuple of (segments, selected_track).

    Raises:
        NoSubtitleError: If no subtitles are available.
    """
    tracks = fetch_subtitle_list(client, aid, cid)
    track = _choose_best_track(tracks)
    segments = fetch_subtitle_content(client, track)
    return segments, track
