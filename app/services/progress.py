"""Shared progress computation (Dev B).

Single source of truth for the rule in CLAUDE.md mục 4:
    progress_percent = completed_lessons / total_lessons * 100
where total_lessons = number of module_documents in the assignment's roadmap.

Used by assignments, learning/progress and dashboard so the number stays
consistent everywhere. Batch helpers (`*_map`) avoid N+1 queries in list
endpoints.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import AssignmentStatus, LessonProgress, RoadmapAssignment
from app.models.roadmap import Module, ModuleDocument


def percent(completed: int, total: int) -> int:
    """Round to a whole percent; 0 when the roadmap has no lessons yet."""
    if total <= 0:
        return 0
    return int(round(completed / total * 100))


# --------------------------------------------------------------------------- #
# Single-assignment helpers
# --------------------------------------------------------------------------- #
def total_lessons(db: Session, roadmap_id: int) -> int:
    return db.scalar(
        select(func.count(ModuleDocument.id))
        .join(Module, ModuleDocument.module_id == Module.id)
        .where(Module.roadmap_id == roadmap_id)
    ) or 0


def completed_lessons(db: Session, assignment_id: int) -> int:
    return db.scalar(
        select(func.count(LessonProgress.id)).where(
            LessonProgress.assignment_id == assignment_id,
            LessonProgress.completed.is_(True),
        )
    ) or 0


def sync_status(db: Session, assignment: RoadmapAssignment) -> tuple[int, int, int]:
    """Recompute completion for `assignment` and update its status in place.

    Returns (completed, total, progress_percent). Caller commits.
    All lessons done (and there is at least one) -> COMPLETED, else IN_PROGRESS.
    """
    total = total_lessons(db, assignment.roadmap_id)
    done = completed_lessons(db, assignment.id)
    new_status = (
        AssignmentStatus.COMPLETED
        if total > 0 and done >= total
        else AssignmentStatus.IN_PROGRESS
    )
    if assignment.status != new_status:
        assignment.status = new_status
    return done, total, percent(done, total)


# --------------------------------------------------------------------------- #
# Batch helpers (for list endpoints / dashboards)
# --------------------------------------------------------------------------- #
def total_lessons_map(db: Session, roadmap_ids) -> dict[int, int]:
    """roadmap_id -> total number of lessons (module_documents)."""
    ids = list({rid for rid in roadmap_ids})
    if not ids:
        return {}
    rows = db.execute(
        select(Module.roadmap_id, func.count(ModuleDocument.id))
        .join(ModuleDocument, ModuleDocument.module_id == Module.id)
        .where(Module.roadmap_id.in_(ids))
        .group_by(Module.roadmap_id)
    ).all()
    return {rid: cnt for rid, cnt in rows}


def completed_counts(db: Session, assignment_ids) -> dict[int, int]:
    """assignment_id -> number of completed lessons."""
    ids = list({aid for aid in assignment_ids})
    if not ids:
        return {}
    rows = db.execute(
        select(LessonProgress.assignment_id, func.count(LessonProgress.id))
        .where(
            LessonProgress.assignment_id.in_(ids),
            LessonProgress.completed.is_(True),
        )
        .group_by(LessonProgress.assignment_id)
    ).all()
    return {aid: cnt for aid, cnt in rows}
