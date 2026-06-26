"""REST API routes for the bili-summary knowledge base."""

from __future__ import annotations

import json
import re
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from bili_summary.bilibili.client import BiliClient
from bili_summary.bilibili.subtitle import NoSubtitleError, get_subtitles
from bili_summary.bilibili.video_info import fetch_video_info, parse_bvid
from bili_summary.bilibili.wbi import clear_cache, get_cached_mixin_key, update_keys
from bili_summary.config import DEFAULT_MODEL
from bili_summary.storage.db import (
    delete_summary,
    get_stats,
    get_summary,
    list_summaries,
    save_summary,
    update_summary,
)
from bili_summary.summarizer.engine import SummarizerError, summarize

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SummarizeRequest(BaseModel):
    url: str = Field(..., description="B站视频链接或 BV 号")
    model: str = Field(default=DEFAULT_MODEL, description="DeepSeek 模型名称")
    depth: str = Field(
        default="auto",
        description="输出深度：auto / quick / standard / deep",
    )


class SummarizeResponse(BaseModel):
    id: int
    bvid: str
    title: str
    owner: str
    duration: str
    char_count: int
    markdown: str


class SummaryListItem(BaseModel):
    id: int
    bvid: str
    title: str
    owner: str
    duration: str
    char_count: int
    research_rating: str
    investment_conclusion: str
    tags: list[str]
    created_at: str


class PaginatedResponse(BaseModel):
    items: list[SummaryListItem]
    total: int
    limit: int
    offset: int


class UpdateSummaryRequest(BaseModel):
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    research_rating: Optional[str] = None
    investment_conclusion: Optional[str] = None


class SyncRequest(BaseModel):
    id: int = Field(..., description="Summary ID to sync")


# ---------------------------------------------------------------------------
# Helpers (minimal — reuse CLI pipeline)
# ---------------------------------------------------------------------------

async def _run_pipeline(url: str, model: str, depth: str = "auto") -> SummarizeResponse:
    """Run the full summarization pipeline and persist to the database."""

    # ---- cookie ----
    from bili_summary.auth.cookie_store import (
        AuthError,
        NeedLoginError,
        get_cookie_header,
        validate_cookie,
    )

    try:
        cookie_header = get_cookie_header()
    except NeedLoginError as e:
        raise HTTPException(401, f"未登录: {e}")
    except AuthError as e:
        raise HTTPException(500, f"认证错误: {e}")

    with BiliClient(cookie_header=cookie_header) as client:
        # Validate
        if not validate_cookie(cookie_header, client):
            raise HTTPException(401, "Cookie 已过期，请重新登录: bili-summary --login")

        # WBI keys
        cached = get_cached_mixin_key()
        if not cached:
            data = client.get_json("/x/web-interface/nav")
            nav_data = data.get("data", {})
            wbi_img = nav_data.get("wbi_img", {})
            img_url = wbi_img.get("img_url", "")
            sub_url = wbi_img.get("sub_url", "")
            if img_url and sub_url:
                update_keys(img_url, sub_url)

        # Parse BV
        try:
            bvid = parse_bvid(url)
        except ValueError as e:
            raise HTTPException(400, str(e))

        # Fetch video info
        try:
            video_meta = fetch_video_info(client, bvid)
        except Exception as e:
            raise HTTPException(502, f"获取视频信息失败: {e}")

        # Fetch subtitles
        try:
            segments, track = get_subtitles(client, video_meta.aid, video_meta.cid)
        except NoSubtitleError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(502, f"获取字幕失败: {e}")

        # Summarize
        try:
            markdown_content = summarize(
                segments=segments,
                video_meta=video_meta,
                model=model,
                depth=depth,
            )
        except SummarizerError as e:
            raise HTTPException(502, f"总结失败: {e}")

    # Persist to knowledge base
    row_id = save_summary(
        bvid=video_meta.bvid,
        title=video_meta.title,
        owner=video_meta.owner,
        duration=video_meta.duration_str,
        markdown_content=markdown_content,
        pic_url=video_meta.pic_url,
        desc_text=video_meta.desc,
    )

    return SummarizeResponse(
        id=row_id,
        bvid=video_meta.bvid,
        title=video_meta.title,
        owner=video_meta.owner,
        duration=video_meta.duration_str,
        char_count=len(markdown_content),
        markdown=markdown_content,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/summarize", response_model=SummarizeResponse)
async def api_summarize(req: SummarizeRequest):
    """Trigger a video summarization.  Blocks until complete."""
    return await _run_pipeline(req.url.strip(), req.model, req.depth)


@router.get("/summaries", response_model=PaginatedResponse)
async def api_list_summaries(
    search: str = Query(default="", description="FTS5 全文搜索"),
    tag: str = Query(default="", description="按标签筛选"),
    rating: str = Query(default="", description="按研究评级筛选 (A/B/C/D)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List summaries with optional filters."""
    records, total = list_summaries(
        search=search, tag=tag, rating=rating, limit=limit, offset=offset
    )
    return PaginatedResponse(
        items=[
            SummaryListItem(
                id=r.id,
                bvid=r.bvid,
                title=r.title,
                owner=r.owner,
                duration=r.duration,
                char_count=r.char_count,
                research_rating=r.research_rating,
                investment_conclusion=r.investment_conclusion,
                tags=r.tags,
                created_at=r.created_at,
            )
            for r in records
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/summaries/{summary_id}")
async def api_get_summary(summary_id: int):
    """Get a single summary by id."""
    r = get_summary(summary_id)
    if not r:
        raise HTTPException(404, "总结不存在")
    return {
        "id": r.id,
        "bvid": r.bvid,
        "title": r.title,
        "owner": r.owner,
        "duration": r.duration,
        "pic_url": r.pic_url,
        "markdown": r.markdown_content,
        "char_count": r.char_count,
        "research_rating": r.research_rating,
        "investment_conclusion": r.investment_conclusion,
        "tags": r.tags,
        "notes": r.notes,
        "feishu_doc_id": r.feishu_doc_id,
        "feishu_record_id": r.feishu_record_id,
        "synced_at": r.synced_at,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


@router.put("/summaries/{summary_id}")
async def api_update_summary(summary_id: int, req: UpdateSummaryRequest):
    """Update user-editable fields (tags, notes, ratings)."""
    ok = update_summary(
        summary_id,
        tags=req.tags,
        notes=req.notes,
        research_rating=req.research_rating,
        investment_conclusion=req.investment_conclusion,
    )
    if not ok:
        raise HTTPException(404, "总结不存在")
    return {"status": "ok"}


@router.delete("/summaries/{summary_id}")
async def api_delete_summary(summary_id: int):
    """Delete a summary."""
    ok = delete_summary(summary_id)
    if not ok:
        raise HTTPException(404, "总结不存在")
    return {"status": "ok"}


@router.get("/stats")
async def api_stats():
    """Return aggregate statistics."""
    return get_stats()
