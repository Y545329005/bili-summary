"""Markdown output writer.

Prepends video metadata header and appends a footer to the LLM-generated
Markdown summary, then saves it to disk with a sanitized filename.
"""

import re
import sys
from pathlib import Path

from bili_summary.bilibili.video_info import VideoMeta


def _sanitize_filename(name: str) -> str:
    """Remove or replace characters unsafe for filenames."""
    name = name.replace("/", "／").replace("\\", "＼")
    name = re.sub(r'[<>:"|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > 100:
        name = name[:100]
    return name


def build_markdown(video: VideoMeta, content: str) -> str:
    """Wrap LLM-generated Markdown with a video metadata header and footer.

    Args:
        video: Video metadata.
        content: The Markdown string returned by the LLM summarizer.

    Returns:
        Complete Markdown string with header prepended and footer appended.
    """
    lines = []

    # Header
    lines.append(f"# {video.title}")
    lines.append("")

    meta_parts = [
        f"**UP主**: {video.owner}",
        f"**时长**: {video.duration_str}",
        f"**BV号**: [{video.bvid}]({video.video_url})",
    ]
    lines.append(f"> {' | '.join(meta_parts)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # LLM-generated body
    lines.append(content.rstrip())
    lines.append("")

    return "\n".join(lines)


def write_markdown(
    video: VideoMeta,
    content: str,
    output_path: str = "",
) -> Path:
    """Build the Markdown document and save it to disk.

    Args:
        video: Video metadata.
        content: The Markdown string returned by the LLM summarizer.
        output_path: Desired output path. Auto-generated if empty.

    Returns:
        Path to the saved file.
    """
    markdown = build_markdown(video, content)

    if output_path:
        path = Path(output_path)
    else:
        filename = f"{_sanitize_filename(video.title)}_summary.md"
        path = Path.cwd() / filename

    path.write_text(markdown, encoding="utf-8")
    print(f"💾 总结已保存到: {path}", file=sys.stderr)
    return path
