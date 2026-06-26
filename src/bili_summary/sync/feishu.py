"""Feishu (Lark) API client for syncing video summaries.

Syncs two things per summary:
1. Bitable record — structured metadata (title, owner, rating, tags, etc.)
2. Docx document — full markdown content rendered in Feishu's block format

Configuration is read from ~/.bili-summary/config.json:
{
    "feishu": {
        "app_id": "cli_xxx",
        "app_secret": "xxx",
        "bitable_app_token": "xxx",
        "bitable_table_id": "xxx",
        "wiki_folder_token": "xxx"   // optional
    }
}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".bili-summary" / "config.json"
FEISHU_API = "https://open.feishu.cn"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class FeishuConfig:
    """Feishu configuration loaded from config.json."""

    def __init__(self) -> None:
        self.app_id: str = ""
        self.app_secret: str = ""
        self.bitable_app_token: str = ""
        self.bitable_table_id: str = ""
        self.wiki_folder_token: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret and self.bitable_app_token and self.bitable_table_id)


def _load_config() -> FeishuConfig:
    """Load Feishu configuration from config.json."""
    cfg = FeishuConfig()
    if not CONFIG_PATH.exists():
        return cfg

    try:
        raw = json.loads(CONFIG_PATH.read_text())
        feishu = raw.get("feishu", {})
        cfg.app_id = feishu.get("app_id", "")
        cfg.app_secret = feishu.get("app_secret", "")
        cfg.bitable_app_token = feishu.get("bitable_app_token", "")
        cfg.bitable_table_id = feishu.get("bitable_table_id", "")
        cfg.wiki_folder_token = feishu.get("wiki_folder_token", "")
    except (json.JSONDecodeError, KeyError) as e:
        print(f"⚠️  飞书配置解析失败: {e}", file=sys.stderr)

    return cfg


# ---------------------------------------------------------------------------
# Access token (with in-memory cache)
# ---------------------------------------------------------------------------

_token_cache: dict = {"token": "", "expires_at": 0}


def _get_access_token(app_id: str, app_secret: str) -> str:
    """Get a tenant access token, caching until expiry."""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]

    url = f"{FEISHU_API}/open-apis/auth/v3/app_access_token/internal"
    resp = httpx.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    code = data.get("code", -1)
    if code != 0:
        raise RuntimeError(f"飞书认证失败: {data.get('msg', 'unknown error')} (code={code})")

    token = data["tenant_access_token"]
    expire = data.get("expire", 7200)  # seconds, default 2h
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expire - 300  # refresh 5 min before expiry
    return token


def _feishu_headers(app_id: str, app_secret: str) -> dict:
    """Authorization headers for Feishu API calls."""
    token = _get_access_token(app_id, app_secret)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }


# ---------------------------------------------------------------------------
# Bitable sync
# ---------------------------------------------------------------------------

def _find_or_create_fields(
    app_id: str, app_secret: str, app_token: str, table_id: str
) -> dict:
    """List existing Bitable fields and return a name→field_id dict.

    If the table is newly created (no fields), Feishu's Bitable may have
    only a default text field.  We try to add the fields we need.
    """
    url = f"{FEISHU_API}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    h = _feishu_headers(app_id, app_secret)

    resp = httpx.get(url, headers=h, params={"page_size": 50}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"获取字段列表失败: {data.get('msg')}")

    existing = {}
    for f in data.get("data", {}).get("items", []):
        existing[f["field_name"]] = f["field_id"]

    desired = [
        ("标题", 1),       # 1 = text
        ("UP主", 1),
        ("时长", 1),
        ("BV号", 1),
        ("研究评级", 3),    # 3 = single select
        ("投资结论", 3),
        ("标签", 4),        # 4 = multi select
        ("字数", 2),        # 2 = number
        ("同步时间", 5),    # 5 = datetime
        ("Summary ID", 1),
    ]

    for name, ftype in desired:
        if name not in existing:
            try:
                body = {"field_name": name, "type": ftype}
                r = httpx.post(url, headers=h, json=body, timeout=15)
                rdata = r.json()
                if rdata.get("code") == 0:
                    fid = rdata["data"]["field"]["field_id"]
                    existing[name] = fid
                    print(f"  📋 已创建字段: {name}", file=sys.stderr)
            except Exception:
                pass  # best-effort field creation

    return existing


def _create_bitable_record(
    app_id: str,
    app_secret: str,
    app_token: str,
    table_id: str,
    fields: dict,
    values: dict,
) -> str:
    """Create a Bitable record and return the record_id."""
    url = f"{FEISHU_API}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    h = _feishu_headers(app_id, app_secret)

    record_fields = {}
    for field_name, field_id in fields.items():
        val = values.get(field_name)
        if val is None or val == "":
            continue
        record_fields[field_id] = val

    body = {"fields": record_fields}
    resp = httpx.post(url, headers=h, json=body, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"创建 Bitable 记录失败: {data.get('msg')}")

    return data["data"]["record"]["record_id"]


# ---------------------------------------------------------------------------
# Docx sync
# ---------------------------------------------------------------------------

def _create_docx_and_convert(
    app_id: str,
    app_secret: str,
    title: str,
    markdown: str,
    folder_token: str = "",
) -> str:
    """Create a Feishu Docx document, convert markdown to blocks, return doc_id."""

    h = _feishu_headers(app_id, app_secret)

    # 1. Create the document
    create_body = {"title": title}
    if folder_token:
        create_body["folder_token"] = folder_token

    resp = httpx.post(
        f"{FEISHU_API}/open-apis/docx/v1/documents",
        headers=h, json=create_body, timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"创建飞书文档失败: {data.get('msg')}")

    doc_id = data["data"]["document"]["document_id"]

    # 2. Convert markdown to blocks and insert
    # Clean markdown: remove the preamble header (title line + meta line) since
    # the doc already has its own title
    convert_resp = httpx.post(
        f"{FEISHU_API}/open-apis/docx/v1/documents/{doc_id}/convert",
        headers=h,
        json={"content": markdown, "content_type": "markdown"},
        timeout=30,
    )
    convert_resp.raise_for_status()
    cdata = convert_resp.json()
    if cdata.get("code", -1) != 0:
        # Non-fatal: doc was created but conversion failed
        print(f"  ⚠️  Markdown 转换失败 (doc 已创建): {cdata.get('msg')}", file=sys.stderr)
    else:
        print(f"  ✅ Markdown 已转换为飞书文档", file=sys.stderr)

    return doc_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sync_to_feishu(
    bvid: str,
    title: str,
    owner: str,
    duration: str,
    markdown: str,
    char_count: int,
    research_rating: str = "",
    investment_conclusion: str = "",
    tags: list[str] | None = None,
) -> dict:
    """Sync a single summary to Feishu.

    Returns:
        {"doc_id": "...", "record_id": "..."}
    """
    cfg = _load_config()
    if not cfg.is_configured:
        raise RuntimeError(
            "飞书未配置。请在 ~/.bili-summary/config.json 中添加 feishu 字段:\n"
            '  "feishu": {"app_id": "cli_xxx", "app_secret": "xxx", '
            '"bitable_app_token": "xxx", "bitable_table_id": "xxx"}'
        )

    print(f"📤 同步到飞书: {title}", file=sys.stderr)

    # 1. Resolve field IDs
    field_map = _find_or_create_fields(
        cfg.app_id, cfg.app_secret, cfg.bitable_app_token, cfg.bitable_table_id
    )

    # 2. Build Bitable record values
    from datetime import datetime
    now_ts = int(time.time() * 1000)

    record_values = {
        "标题": [{"text": title}],
        "UP主": [{"text": owner}],
        "时长": [{"text": duration}],
        "BV号": [{"text": bvid, "link": f"https://www.bilibili.com/video/{bvid}"}],
        "字数": char_count,
        "同步时间": now_ts,
        "Summary ID": [{"text": bvid}],
    }

    if research_rating:
        record_values["研究评级"] = research_rating
    if investment_conclusion:
        record_values["投资结论"] = investment_conclusion
    if tags:
        record_values["标签"] = tags

    # 3. Create Bitable record
    record_id = _create_bitable_record(
        cfg.app_id, cfg.app_secret,
        cfg.bitable_app_token, cfg.bitable_table_id,
        field_map, record_values,
    )
    print(f"  ✅ Bitable 记录: {record_id}", file=sys.stderr)

    # 4. Create Docx
    doc_id = _create_docx_and_convert(
        cfg.app_id, cfg.app_secret,
        title=f"[{owner}] {title}",
        markdown=markdown,
        folder_token=cfg.wiki_folder_token,
    )
    print(f"  ✅ Docx 文档: {doc_id}", file=sys.stderr)

    return {"doc_id": doc_id, "record_id": record_id}


def is_configured() -> bool:
    """Check if Feishu integration is configured."""
    return _load_config().is_configured
