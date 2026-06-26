"""Tests for the Markdown output writer."""

from bili_summary.output.writer import _sanitize_filename, build_markdown
from bili_summary.bilibili.video_info import VideoMeta


class TestSanitizeFilename:
    def test_normal_title(self):
        assert _sanitize_filename("这是一个测试标题") == "这是一个测试标题"

    def test_special_chars(self):
        sanitized = _sanitize_filename("测试:标题<>?*")
        assert ":" not in sanitized
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert "?" not in sanitized
        assert "*" not in sanitized

    def test_slashes(self):
        sanitized = _sanitize_filename("测试/标题\\test")
        assert "/" not in sanitized
        assert "\\" not in sanitized

    def test_long_title(self):
        long_title = "A" * 200
        sanitized = _sanitize_filename(long_title)
        assert len(sanitized) <= 100


class TestBuildMarkdown:
    def test_complete_output(self):
        video = VideoMeta(
            bvid="BV1234567890",
            aid=123,
            cid=456,
            title="测试视频标题",
            desc="这是一个测试视频",
            owner="测试UP主",
            duration=600,
        )

        llm_output = """### 📌 一句话核心论点
这是一句测试总结。

### 🎯 核心观点
| # | 观点 | 论据 | 确定性 | 启示 |
|---|------|------|--------|------|
| 1 | 观点1 | 论据1 | 高 | 启示1 |

### 💎 值得沉淀的洞察
- 洞察1
- 洞察2

*由 DeepSeek 生成，仅供参考*"""

        markdown = build_markdown(video, llm_output)
        assert "# 测试视频标题" in markdown
        assert "BV1234567890" in markdown
        assert "测试UP主" in markdown
        assert "一句测试总结" in markdown
        assert "观点1" in markdown
        assert "洞察1" in markdown
        assert "由 DeepSeek 生成" in markdown

    def test_minimal_output(self):
        video = VideoMeta(
            bvid="BV1234567890",
            aid=1,
            cid=1,
            title="最小视频",
            desc="",
            owner="UP",
            duration=60,
        )

        llm_output = "一句总结。"

        markdown = build_markdown(video, llm_output)
        assert "# 最小视频" in markdown
        assert "一句总结。" in markdown
