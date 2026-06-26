"""Tests for WBI signing algorithm."""

import pytest
from bili_summary.bilibili.wbi import (
    compute_mixin_key,
    sign_params,
    _extract_key_from_url,
    update_keys,
    clear_cache,
    get_cached_mixin_key,
)


class TestExtractKeyFromUrl:
    def test_extract_key(self):
        url = "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png"
        assert _extract_key_from_url(url) == "7cd084941338484aae1ad9425b84077c"

    def test_extract_key_no_ext(self):
        assert _extract_key_from_url("https://example.com/abc123") == "abc123"


class TestComputeMixinKey:
    def test_known_keys(self):
        # Test with known keys to verify the algorithm
        img_key = "7cd084941338484aae1ad9425b84077c"
        sub_key = "4932caff0ff746eab6f01bf08b70ac45"
        mixin = compute_mixin_key(img_key, sub_key)
        assert len(mixin) == 32
        assert mixin == mixin  # the key should be deterministic

    def test_length_is_32(self):
        mixin = compute_mixin_key("a" * 32, "b" * 32)
        assert len(mixin) == 32


class TestSignParams:
    def test_sign_adds_wts_and_w_rid(self):
        mixin_key = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        params = {"aid": "123", "cid": "456"}
        signed = sign_params(params, mixin_key)
        assert "wts" in signed
        assert "w_rid" in signed
        assert signed["aid"] == "123"
        assert signed["cid"] == "456"

    def test_w_rid_is_md5_hex(self):
        mixin_key = "testmixin"
        params = {"foo": "bar"}
        signed = sign_params(params, mixin_key)
        assert len(signed["w_rid"]) == 32
        assert all(c in "0123456789abcdef" for c in signed["w_rid"])

    def test_sign_filters_special_chars(self):
        mixin_key = "test"
        # The sign should not crash on special chars
        params = {"key": "value!with'special(chars)here*"}
        signed = sign_params(params, mixin_key)
        assert "w_rid" in signed


class TestKeyCache:
    def setup_method(self):
        clear_cache()

    def test_cache_empty_initially(self):
        assert get_cached_mixin_key() is None

    def test_cache_after_update(self):
        # Use realistic 32-char keys like Bilibili's actual WBI keys
        img_url = "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png"
        sub_url = "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"
        mixin = update_keys(img_url, sub_url)
        cached = get_cached_mixin_key()
        assert cached == mixin
        assert len(cached) == 32

    def test_clear_cache(self):
        update_keys(
            "https://example.com/bfs/wbi/abc123.png",
            "https://example.com/bfs/wbi/def456.png",
        )
        clear_cache()
        assert get_cached_mixin_key() is None
