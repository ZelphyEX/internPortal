"""Aggregate router for API v1. Sub-routers are included here as they are built.

Dev B: add your routers with `api_router.include_router(<router>)` below.
"""
from fastapi import APIRouter

from app.api.v1.routers import auth, documents, roadmaps, tags

api_router = APIRouter()

# --- Dev A (Phase 1) ---
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(tags.router)
api_router.include_router(roadmaps.router)

# --- Dev B (Phase 2) ---
# users, groups, assignments, learning, dashboard, comments
