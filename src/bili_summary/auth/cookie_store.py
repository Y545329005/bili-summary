"""Cookie storage and validation.

Uses Playwright's storage_state JSON format to persist cookies.
Extracts the Cookie header string needed for API calls.
Validates cookie freshness via the Bilibili nav endpoint.
"""

import json
import sys
from pathlib import Path
from typing import Optional

from bili_summary.config import COOKIE_DIR, COOKIE_PATH

# Essential Bilibili cookies for API access
RELEVANT_COOKIE_NAMES = [
    "SESSDATA",
    "bili_jct",
    "DedeUserID",
    "DedeUserID__ckMd5",
    "buvid3",
    "buvid4",
    "b_nut",
    "sid",
]


class AuthError(Exception):
    """Base exception for authentication errors."""


class NeedLoginError(AuthError):
    """No cookies file exists; user must log in first."""


class CookieExpiredError(AuthError):
    """Cookies exist but are invalid or expired."""


def ensure_cookie_dir() -> None:
    """Create the cookie storage directory if it doesn't exist."""
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def load_storage_state() -> dict:
    """Load the Playwright storage_state JSON from disk.

    Returns:
        The parsed storage_state dict.

    Raises:
        NeedLoginError: If no cookies file exists.
    """
    if not COOKIE_PATH.exists():
        raise NeedLoginError(
            f"未找到登录信息。请先运行:\n"
            f"  bili-summary --login\n\n"
            f"Cookie 存储路径: {COOKIE_PATH}"
        )
    try:
        with open(COOKIE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise AuthError(f"无法读取 Cookie 文件 ({COOKIE_PATH}): {e}") from e


def build_cookie_header(storage_state: dict) -> str:
    """Build a Cookie header string from Playwright storage_state.

    Extracts only the essential Bilibili cookies.
    """
    cookies = storage_state.get("cookies", [])
    parts = []
    for c in cookies:
        if c.get("name") in RELEVANT_COOKIE_NAMES and c.get("value"):
            parts.append(f"{c['name']}={c['value']}")
    return "; ".join(parts)


def get_cookie_header() -> str:
    """Load cookies from disk and return the Cookie header string.

    Raises:
        NeedLoginError: If no cookies file exists.
    """
    state = load_storage_state()
    header = build_cookie_header(state)
    if not header:
        raise CookieExpiredError(
            "Cookie 文件存在但没有有效的 SESSDATA，请重新登录:\n"
            "  bili-summary --login"
        )
    return header


def validate_cookie(cookie_header: str, client) -> bool:
    """Validate the cookie by checking if the user is logged in.

    Makes a lightweight GET /x/web-interface/nav request.
    Uses the provided httpx client (which should have the cookie set).

    Args:
        cookie_header: The Cookie header string.
        client: An httpx.Client instance.

    Returns:
        True if logged in, False otherwise.
    """
    try:
        resp = client.get("/x/web-interface/nav")
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("isLogin", False)
    except Exception:
        return False


def save_storage_state(storage_state: dict) -> None:
    """Save a Playwright storage_state dict to disk."""
    ensure_cookie_dir()
    with open(COOKIE_PATH, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, ensure_ascii=False, indent=2)
    print(f"✅ Cookie 已保存到: {COOKIE_PATH}", file=sys.stderr)
