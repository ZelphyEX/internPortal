"""Aggregate router for API v1. Sub-routers are included here as they are built.

Dev B: add your routers with `api_router.include_router(<router>)` below.
"""
from fastapi import APIRouter

from app.api.v1.routers import (
    assignments,
    auth,
    comments,
    dashboard,
    documents,
    groups,
    learning,
    roadmaps,
    tags,
    users,
)

api_router = APIRouter()

# --- Dev A (Phase 1) ---
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(tags.router)
api_router.include_router(roadmaps.router)

# --- Dev B (Phase 2) ---
# users, groups, assignments, learning, dashboard, comments
api_router.include_router(users.router)
api_router.include_router(groups.router)
api_router.include_router(assignments.router)
api_router.include_router(learning.router)
api_router.include_router(comments.router)
api_router.include_router(dashboard.router)
