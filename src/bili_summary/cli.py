"""CLI entry point for bili-summary.

Orchestrates the full pipeline:
  Cookie load → Video info → Subtitle → DeepSeek → Markdown output
"""

import argparse
import sys
from pathlib import Path

from bili_summary.auth.cookie_store import (
    AuthError,
    CookieExpiredError,
    NeedLoginError,
    get_cookie_header,
    validate_cookie,
)
from bili_summary.auth.login import login
from bili_summary.bilibili.client import BiliClient, BiliAPIError
from bili_summary.bilibili.subtitle import NoSubtitleError, get_subtitles
from bili_summary.bilibili.video_info import fetch_video_info, parse_bvid
from bili_summary.bilibili.wbi import clear_cache, get_cached_mixin_key, update_keys
from bili_summary.config import DEFAULT_MODEL
from bili_summary.output.writer import write_markdown
from bili_summary.storage.db import save_summary
from bili_summary.summarizer.engine import SummarizerError, summarize


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="bili-summary",
        description="哔哩哔哩长视频内容总结工具 - 自动提取字幕并用 DeepSeek 生成结构化总结",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  bili-summary --login                         # 登录 Bilibili 账号
  bili-summary "https://www.bilibili.com/video/BV1xx411c7mD"  # 总结视频
  bili-summary BV1xx411c7mD -o my_notes.md     # 指定输出文件
  bili-summary BV1xx411c7mD --model deepseek-chat  # 使用 chat 模型
        """,
    )

    parser.add_argument(
        "url",
        nargs="?",
        help="Bilibili 视频链接或 BV 号",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="打开浏览器登录 Bilibili 并保存 Cookie",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="",
        help="输出 Markdown 文件路径（默认：当前目录下 {视频标题}_summary.md）",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=DEFAULT_MODEL,
        help=f"DeepSeek 模型名称（默认：{DEFAULT_MODEL}）",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="跳过 WBI 密钥缓存，强制重新获取",
    )
    parser.add_argument(
        "--depth", "-d",
        type=str,
        choices=["auto", "quick", "standard", "deep"],
        default="auto",
        help="输出深度：auto（自动判断，默认）、quick（仅正文）、standard（完整框架）、deep（深度展开 D/H/I/F）",
    )

    return parser.parse_args()


def _ensure_wbi_keys(client: BiliClient, force_refresh: bool = False) -> str:
    """Ensure WBI signing keys are available.

    Fetches keys from the nav endpoint if not cached or expired.
    Returns the mixin_key.

    Raises:
        BiliAPIError: If the nav endpoint fails.
    """
    if force_refresh:
        clear_cache()

    cached = get_cached_mixin_key()
    if cached:
        return cached

    print("🔑 正在获取 WBI 签名密钥...", file=sys.stderr)
    data = client.get_json("/x/web-interface/nav")
    nav_data = data.get("data", {})
    wbi_img = nav_data.get("wbi_img", {})

    img_url = wbi_img.get("img_url", "")
    sub_url = wbi_img.get("sub_url", "")

    if not img_url or not sub_url:
        raise BiliAPIError(-1, "无法获取 WBI 密钥 URL", "/x/web-interface/nav")

    return update_keys(img_url, sub_url)


def _run_summary(args: argparse.Namespace) -> int:
    """Run the video summarization pipeline.

    Returns exit code (0 = success, 1 = error).
    """
    url = args.url.strip()

    # Step 1: Load cookies
    print("🔐 正在加载登录信息...", file=sys.stderr)
    try:
        cookie_header = get_cookie_header()
    except NeedLoginError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    except AuthError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    # Step 2: Create client
    with BiliClient(cookie_header=cookie_header) as client:
        # Step 3: Validate login
        print("🔐 正在验证登录状态...", file=sys.stderr)
        if not validate_cookie(cookie_header, client):
            print(
                "❌ Cookie 已过期或无效，请重新登录:\n"
                "  bili-summary --login",
                file=sys.stderr,
            )
            return 1
        print("✅ 登录状态有效。", file=sys.stderr)

        # Step 4: Fetch WBI keys
        try:
            mixin_key = _ensure_wbi_keys(client, force_refresh=args.no_cache)
        except BiliAPIError as e:
            print(f"❌ 获取 WBI 签名密钥失败: {e}", file=sys.stderr)
            return 1

        # Step 5: Parse BV and fetch video info
        print("📹 正在获取视频信息...", file=sys.stderr)
        try:
            bvid = parse_bvid(url)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1

        try:
            video_meta = fetch_video_info(client, bvid)
        except BiliAPIError as e:
            _print_bili_error(e)
            return 1

        print(f"📹 视频: {video_meta.title}", file=sys.stderr)
        print(f"   UP主: {video_meta.owner}  |  时长: {video_meta.duration_str}", file=sys.stderr)

        # Step 6: Fetch subtitles
        print("📝 正在获取字幕...", file=sys.stderr)
        try:
            segments, track = get_subtitles(client, video_meta.aid, video_meta.cid)
        except NoSubtitleError as e:
            print(f"❌ {e}", file=sys.stderr)
            print(
                "该视频没有字幕，无法进行总结。\n"
                "提示：Bilibili 上大部分视频依赖 CC 字幕或 AI 字幕。",
                file=sys.stderr,
            )
            return 1
        except BiliAPIError as e:
            _print_bili_error(e)
            return 1

        # Step 7: Summarize
        try:
            markdown_content = summarize(
                segments=segments,
                video_meta=video_meta,
                model=args.model,
                depth=args.depth,
            )
        except SummarizerError as e:
            print(f"❌ 总结失败: {e}", file=sys.stderr)
            return 1

        # Step 8: Write output
        output_path = write_markdown(
            video=video_meta,
            content=markdown_content,
            output_path=args.output,
        )

        # Step 9: Save to knowledge base
        try:
            save_summary(
                bvid=video_meta.bvid,
                title=video_meta.title,
                owner=video_meta.owner,
                duration=video_meta.duration_str,
                markdown_content=markdown_content,
                pic_url=video_meta.pic_url,
                desc_text=video_meta.desc,
            )
        except Exception as e:
            print(f"⚠️  保存到知识库失败: {e}", file=sys.stderr)

        # Print a preview
        char_count = len(markdown_content)
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"✅ 投资研究总结完成，共 {char_count} 字符", file=sys.stderr)

    return 0


def _print_bili_error(e: BiliAPIError) -> None:
    """Print a user-friendly Bilibili API error message."""
    error_map = {
        -404: "视频不存在（BV 号无效）。",
        62002: "视频不可见（可能被锁定或审核中）。",
        62004: "视频已被删除。",
        -352: "WBI 签名验证失败，请重试。",
        -101: "未登录或登录已过期，请重新登录: bili-summary --login",
        -111: "请求被限流，请稍后重试。",
    }
    friendly = error_map.get(e.code, f"API 错误 [{e.code}]: {e.message}")
    print(f"❌ {friendly}", file=sys.stderr)


def main() -> None:
    """Main entry point."""
    args = _parse_args()

    # Handle --login mode
    if args.login:
        try:
            login()
        except RuntimeError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
        except TimeoutError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
        return

    # If no URL provided, show help
    if not args.url:
        print("请提供 Bilibili 视频链接或运行 --login 登录。", file=sys.stderr)
        print("运行 bili-summary --help 查看帮助。", file=sys.stderr)
        sys.exit(1)

    # Run the summary pipeline
    exit_code = _run_summary(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
