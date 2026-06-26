"""FastAPI server entry point for bili-summary knowledge base.

Start with:
    python server.py
    uvicorn server:app --reload --port 8765
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from bili_summary.storage.db import get_summary, update_sync_status
from bili_summary.sync.feishu import is_configured, sync_to_feishu
from bili_summary.web.api import router as api_router
from bili_summary.web.ui import ui_router

# Template engine
TEMPLATES_DIR = Path(__file__).parent / "src" / "bili_summary" / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Pydantic models (defined at module level to avoid forward-ref issues)
class SyncFeishuRequest(BaseModel):
    id: int


def create_app() -> FastAPI:
    app = FastAPI(
        title="投资研究知识库",
        description="B站视频投资研究总结知识库 — 一键总结 + 全文搜索 + 飞书同步",
        version="0.2.0",
    )

    # Inject template engine
    app.state.templates = templates

    # Sync endpoint — must be added to api_router BEFORE include_router
    @api_router.post("/sync/feishu")
    async def sync_feishu(body: SyncFeishuRequest):
        r = get_summary(body.id)
        if not r:
            return {"status": "error", "message": "总结不存在"}

        if not is_configured():
            return {
                "status": "error",
                "message": (
                    "飞书未配置。请在 ~/.bili-summary/config.json 中添加:\n"
                    '  "feishu": {"app_id": "cli_xxx", "app_secret": "xxx", '
                    '"bitable_app_token": "xxx", "bitable_table_id": "xxx"}'
                ),
            }

        try:
            result = sync_to_feishu(
                bvid=r.bvid,
                title=r.title,
                owner=r.owner,
                duration=r.duration,
                markdown=r.markdown_content,
                char_count=r.char_count,
                research_rating=r.research_rating,
                investment_conclusion=r.investment_conclusion,
                tags=r.tags,
            )
            update_sync_status(
                summary_id=r.id,
                feishu_doc_id=result["doc_id"],
                feishu_record_id=result["record_id"],
            )
            return {
                "status": "ok",
                "doc_id": result["doc_id"],
                "record_id": result["record_id"],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # Routes
    app.include_router(api_router)
    app.include_router(ui_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=True)
