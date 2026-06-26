"""Web UI routes — server-rendered pages with Jinja2 + HTMX."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from bili_summary.storage.db import get_stats, get_summary, list_summaries

ui_router = APIRouter()


@ui_router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    search: str = Query(default=""),
    tag: str = Query(default=""),
    rating: str = Query(default=""),
):
    """Main page: summary list + search."""
    records, total = list_summaries(search=search, tag=tag, rating=rating)
    stats = get_stats()
    return request.app.state.templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "records": records,
            "total": total,
            "search": search,
            "tag": tag,
            "rating": rating,
            "stats": stats,
        },
    )


@ui_router.get("/summary/{summary_id}", response_class=HTMLResponse)
async def detail(request: Request, summary_id: int):
    """Single summary detail page."""
    r = get_summary(summary_id)
    if not r:
        return HTMLResponse("<h1>404 — 总结不存在</h1>", status_code=404)
    return request.app.state.templates.TemplateResponse(
        "detail.html",
        {"request": request, "record": r},
    )
