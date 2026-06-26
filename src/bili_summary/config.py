"""Centralized constants and configuration."""

import os
from pathlib import Path

# Cookie storage
COOKIE_DIR = Path.home() / ".bili-summary"
COOKIE_PATH = COOKIE_DIR / "cookies.json"

# Bilibili API
BILI_API_BASE = "https://api.bilibili.com"
BILI_REFERER = "https://www.bilibili.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# DeepSeek API
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEFAULT_MODEL = "deepseek-reasoner"

# WBI signing: fixed 64-element shuffle table
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]

# HTTP client settings
REQUEST_TIMEOUT = 30.0  # seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0
RETRYABLE_STATUSES = {429, 502, 503, 504}

# WBI key cache TTL (24 hours in seconds)
WBI_KEY_CACHE_TTL = 24 * 60 * 60

# Subtitle track preference order
SUBTITLE_PREFERENCE = ["zh-CN", "zh-Hans", "zh-TW", "ai-zh", "zh"]

# Subtitle chunking threshold (characters)
SUBTITLE_CHUNK_THRESHOLD = 8000
SUBTITLE_CHUNK_SIZE = 200      # segments per chunk
SUBTITLE_CHUNK_OVERLAP = 20    # segments overlap between chunks

# DeepSeek API settings
DEEPSEEK_MAX_TOKENS = 8192
