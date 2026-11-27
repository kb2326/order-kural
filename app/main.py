"""FastAPI entry point: `uvicorn app.main:app`."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import provider_status

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_DB = "data/runtime/orderkural.db"


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Order Kural")
    app.state.db_path = db_path or os.environ.get("ORDER_KURAL_DB", DEFAULT_DB)
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
