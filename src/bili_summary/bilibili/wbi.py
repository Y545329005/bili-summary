"""Bilibili WBI signing algorithm.

WBI (Web Interface) signing uses a rotating key pair (img_key, sub_key)
retrieved from the nav endpoint. Keys are cached for 24 hours.

Algorithm:
1. Get img_key and sub_key from /x/web-interface/nav (extract stem from URL)
2. Mix them using a fixed 64-element permutation table → mixin_key (first 32 chars)
3. For each request: sort params, filter special chars, URL-encode, MD5 with mixin_key
"""

from __future__ import annotations

import hashlib
import time
import urllib.parse
from typing import Optional

from bili_summary.config import MIXIN_KEY_ENC_TAB, WBI_KEY_CACHE_TTL

# In-memory cache for WBI keys
_cache: dict = {"img_key": "", "sub_key": "", "fetched_at": 0.0}


def _extract_key_from_url(url: str) -> str:
    """Extract the filename stem from a WBI image URL.

    Example:
        'https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png'
        → '7cd084941338484aae1ad9425b84077c'
    """
    return url.rsplit("/", 1)[-1].split(".")[0]


def compute_mixin_key(img_key: str, sub_key: str) -> str:
    """Compute the mixin key by shuffling img_key + sub_key.

    The concatenated string is permuted using a fixed 64-element table,
    and the first 32 characters are taken as the mixin key.
    """
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw))[:32]


def _is_cache_valid() -> bool:
    """Check if the cached WBI keys are still fresh."""
    if not _cache["img_key"] or not _cache["sub_key"]:
        return False
    elapsed = time.time() - _cache["fetched_at"]
    return elapsed < WBI_KEY_CACHE_TTL


def get_cached_mixin_key() -> Optional[str]:
    """Get the cached mixin key if available and fresh."""
    if _is_cache_valid():
        return compute_mixin_key(_cache["img_key"], _cache["sub_key"])
    return None


def update_keys(img_url: str, sub_url: str) -> str:
    """Update the cached WBI keys and return the new mixin key."""
    _cache["img_key"] = _extract_key_from_url(img_url)
    _cache["sub_key"] = _extract_key_from_url(sub_url)
    _cache["fetched_at"] = time.time()
    return compute_mixin_key(_cache["img_key"], _cache["sub_key"])


def clear_cache() -> None:
    """Clear the WBI key cache (e.g., after re-login)."""
    _cache["img_key"] = ""
    _cache["sub_key"] = ""
    _cache["fetched_at"] = 0.0


def sign_params(params: dict[str, str], mixin_key: str) -> dict[str, str]:
    """Sign a parameter dict with WBI signing.

    1. Add wts (current unix timestamp)
    2. Sort by key alphabetically
    3. Filter special characters !'()* from values
    4. URL-encode (uppercase hex, space as %20)
    5. MD5(query_string + mixin_key) → w_rid

    Returns a new dict with w_rid and wts added.
    """
    signed = dict(params)
    signed["wts"] = str(int(time.time()))

    # Sort by key
    sorted_keys = sorted(signed.keys())
    filtered = []
    for k in sorted_keys:
        v = signed[k]
        # Filter special characters: ! ' ( ) *
        v = v.translate(str.maketrans("", "", "!'()*"))
        filtered.append((k, v))

    # URL-encode with uppercase hex
    query_string = urllib.parse.urlencode(filtered, safe="")

    # MD5 with mixin key appended
    sign_str = query_string + mixin_key
    w_rid = hashlib.md5(sign_str.encode()).hexdigest()

    signed["w_rid"] = w_rid
    return signed
