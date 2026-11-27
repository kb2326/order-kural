"""FastAPI entry point: `uvicorn app.main:app`."""
import os
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import provider_status
from app.domain.catalog import Catalog
from app.flow.pieces import PieceService
from app.ratelimit import RateLimiter
from app.store.db import Store

STATIC_DIR = Path(__file__).parent / "static"
ITEMS_FILE = Path(__file__).parent.parent / "data" / "items.json"
DEFAULT_DB = "data/runtime/orderkural.db"


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Order Kural")
    app.state.db_path = db_path or os.environ.get("ORDER_KURAL_DB", DEFAULT_DB)
    app.state.pieces = PieceService(Store(app.state.db_path), Catalog.load(ITEMS_FILE))
    app.state.sample_sessions = OrderedDict()
    app.state.agent_sessions = OrderedDict()
    app.state.text_brains = {}
    app.state.llm_client = None  # tests inject a mock httpx client here
    app.state.text_limiter = RateLimiter(per_ip_hour=30, per_day=300)
    app.state.voice_limiter = RateLimiter(per_ip_hour=6, per_day=100)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/status")
    def status() -> dict:
        return {"providers": provider_status(), "sample_available": True}

    return app


app = create_app()
