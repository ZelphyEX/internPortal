"""FastAPI application entrypoint.

Run: uvicorn app.main:app --reload  ->  http://localhost:8000/docs
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Local storage backend: serve uploaded files so their content_url resolves.
if settings.STORAGE_BACKEND.lower() == "local":
    _local_dir = Path(settings.STORAGE_LOCAL_DIR)
    _local_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=_local_dir), name="files")

# CORS: allow the (separate) frontend origin(s) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All v1 endpoints live under /api/v1.
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
