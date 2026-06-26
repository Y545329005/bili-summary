"""Bilibili video metadata extraction.

Parses BV numbers from URLs and fetches video info from the API.
"""

import re
from dataclasses import dataclass
from typing import Optional

from bili_summary.bilibili.client import BiliClient

# BV number regex: BV followed by 10 alphanumeric characters
_BV_PATTERN = re.compile(r"BV[a-zA-Z0-9]{10}")


@dataclass
class VideoMeta:
    """Core video metadata needed for summarization."""

    bvid: str
    aid: int
    cid: int
    title: str
    desc: str
    owner: str
    duration: int  # seconds
    pic_url: str = ""
    pubdate: int = 0  # Unix timestamp

    @property
    def duration_str(self) -> str:
        """Human-readable duration string."""
        h = self.duration // 3600
        m = (self.duration % 3600) // 60
        s = self.duration % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @property
    def publish_date_str(self) -> str:
        """Human-readable publish date."""
        if not self.pubdate:
            return "未知"
        from datetime import datetime, timezone
        return datetime.fromtimestamp(self.pubdate, tz=timezone.utc).strftime("%Y-%m-%d")

    @property
    def video_url(self) -> str:
        """Full Bilibili video URL."""
        return f"https://www.bilibili.com/video/{self.bvid}"


def parse_bvid(raw: str) -> str:
    """Extract a BV number from a URL or raw string.

    Args:
        raw: A full Bilibili URL or a bare BV number.

    Returns:
        The extracted BV number (e.g., 'BV1xx411c7mD').

    Raises:
        ValueError: If no valid BV number is found.
    """
    raw = raw.strip()
    match = _BV_PATTERN.search(raw)
    if match:
        return match.group(0)

    # Could also be a bare BV number with different casing
    raise ValueError(
        f"无法从输入中提取 BV 号: '{raw}'\n"
        f"请提供完整的 Bilibili 视频链接或 BV 号。"
    )


def fetch_video_info(client: BiliClient, bvid: str) -> VideoMeta:
    """Fetch video metadata from Bilibili API.

    Args:
        client: Configured BiliClient instance.
        bvid: BV video identifier.

    Returns:
        VideoMeta with title, description, aid, cid, etc.

    Raises:
        BiliAPIError: If the API returns an error (video not found, etc.).
    """
    data = client.get_json(f"/x/web-interface/view?bvid={bvid}")
    video_data = data.get("data", {})

    if not video_data:
        raise ValueError(f"视频 {bvid} 不存在或已删除。")

    return VideoMeta(
        bvid=bvid,
        aid=video_data.get("aid", 0),
        cid=video_data.get("cid", 0),
        title=video_data.get("title", "未知标题"),
        desc=video_data.get("desc", ""),
        owner=video_data.get("owner", {}).get("name", "未知UP主"),
        duration=video_data.get("duration", 0),
        pic_url=video_data.get("pic", ""),
        pubdate=video_data.get("pubdate", 0),
    )
