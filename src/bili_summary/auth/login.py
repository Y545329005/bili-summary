"""Playwright-based Bilibili login flow.

Opens a Chromium browser window for the user to log in (QR scan or password),
detects successful login by polling for the SESSDATA cookie, and saves
the Playwright storage_state for subsequent API calls.
"""

import sys
import time

from bili_summary.config import COOKIE_PATH
from bili_summary.auth.cookie_store import ensure_cookie_dir


_LOGIN_TIMEOUT = 120  # seconds
_POLL_INTERVAL = 2    # seconds


def login() -> None:
    """Open a browser for the user to log into Bilibili.

    Launches Chromium via Playwright, navigates to bilibili.com,
    and waits for the user to complete login (QR scan or credentials).
    Once the SESSDATA cookie is detected, saves the storage state to disk.

    Raises:
        RuntimeError: If Playwright is not installed or login times out.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "需要安装 Playwright。请运行:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    ensure_cookie_dir()

    print("🌐 正在启动浏览器...", file=sys.stderr)
    print("📱 请在浏览器中完成登录（扫码或账号密码）", file=sys.stderr)
    print(f"⏰ 等待超时时间：{_LOGIN_TIMEOUT} 秒", file=sys.stderr)
    print("", file=sys.stderr)

    with sync_playwright() as p:
        # Try to use the system Chrome/Chromium if available
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox"],
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()
        page.goto("https://www.bilibili.com", wait_until="domcontentloaded")

        # Poll for login success
        start_time = time.time()
        while time.time() - start_time < _LOGIN_TIMEOUT:
            cookies = context.cookies()
            for cookie in cookies:
                if cookie.get("name") == "SESSDATA" and cookie.get("value"):
                    # Login detected!
                    context.storage_state(path=str(COOKIE_PATH))
                    print("", file=sys.stderr)
                    print("✅ 登录成功！Cookie 已保存。", file=sys.stderr)
                    browser.close()
                    return

            # Show progress dots
            print(".", end="", flush=True, file=sys.stderr)
            time.sleep(_POLL_INTERVAL)

        # Timeout
        print("", file=sys.stderr)
        print("❌ 登录超时，请重试。", file=sys.stderr)
        browser.close()
        raise TimeoutError(
            f"登录超时（{_LOGIN_TIMEOUT} 秒内未检测到登录状态）。"
        )
