"""Learning & progress business logic (API_SPEC mục 8).

Security: every function resolves the assignment via `_owned_assignment`,
which enforces that it belongs to the caller (Intern cannot touch someone
else's progress -> 403). Progress % is recomputed live on each mark/unmark and
the assignment auto-flips to COMPLETED when all lessons are done
(app.services.progress).
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import LessonProgress, RoadmapAssignment
from app.models.roadmap import LessonAttachment, Module, ModuleDocument, Roadmap
from app.models.user import User
from app.schemas.learning import (
    CompleteResponse,
    LessonDetail,
    ModuleWithLessons,
    MyRoadmapDetail,
    MyRoadmapItem,
)
from app.services import progress
from app.services import roadmap_service as roadmap_svc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owned_assignment(db: Session, user: User, assignment_id: int) -> RoadmapAssignment:
    a = db.get(RoadmapAssignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if a.user_id != user.id:
        # Never reveal other users' assignments.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assignment does not belong to you",
        )
    return a


def list_my_roadmaps(db: Session, user: User) -> list[MyRoadmapItem]:
    rows = list(
        db.scalars(
            select(RoadmapAssignment)
            .where(RoadmapAssignment.user_id == user.id)
            .order_by(RoadmapAssignment.id.desc())
        ).all()
    )
    if not rows:
        return []
    roadmap_ids = {a.roadmap_id for a in rows}
    titles = dict(
        db.execute(select(Roadmap.id, Roadmap.title).where(Roadmap.id.in_(roadmap_ids))).all()
    )
    totals = progress.total_lessons_map(db, roadmap_ids)
    completed = progress.completed_counts(db, [a.id for a in rows])
    items = []
    for a in rows:
        done = completed.get(a.id, 0)
        total = totals.get(a.roadmap_id, 0)
        items.append(
            MyRoadmapItem(
                assignment_id=a.id,
                roadmap_id=a.roadmap_id,
                title=titles.get(a.roadmap_id, ""),
                status=a.status,
                progress_percent=progress.percent(done, total),
                completed_lessons=done,
                total_lessons=total,
            )
        )
    return items


def get_my_roadmap_detail(db: Session, user: User, assignment_id: int) -> MyRoadmapDetail:
    a = _owned_assignment(db, user, assignment_id)
    roadmap = db.scalar(
        select(Roadmap)
        .where(Roadmap.id == a.roadmap_id)
        .options(
            selectinload(Roadmap.modules)
            .selectinload(Module.module_documents)
            .selectinload(ModuleDocument.document),
            selectinload(Roadmap.modules)
            .selectinload(Module.module_documents)
            .selectinload(ModuleDocument.attachments)
            .selectinload(LessonAttachment.document),
        )
    )
    if roadmap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")

    prog = {
        p.module_document_id: p
        for p in db.scalars(
            select(LessonProgress).where(LessonProgress.assignment_id == a.id)
        ).all()
    }
    total = 0
    done = 0
    modules = []
    for m in roadmap.modules:
        lessons = []
        for md in m.module_documents:
            total += 1
            p = prog.get(md.id)
            is_done = bool(p and p.completed)
            if is_done:
                done += 1
            lessons.append(
                LessonDetail(
                    module_document_id=md.id,
                    # Bài học tạo tay có tên/link riêng; bài học lấy từ Thư viện thì
                    # rơi về tên/link của tài liệu gốc (xem ModuleDocument.display_*).
                    title=md.display_title,
                    type=md.document.type if md.document is not None else None,
                    content_url=md.display_url,
                    completed=is_done,
                    completed_at=p.completed_at if p else None,
                    attachments=[roadmap_svc.to_attachment_out(a) for a in md.attachments],
                )
            )
        modules.append(
            ModuleWithLessons(
                id=m.id,
                title=m.title,
                position=m.position,
                track=m.track,
                week_number=m.week_number,
                duration_text=m.duration_text,
                key_skills=m.key_skills or [],
                start_date=m.start_date,
                end_date=m.end_date,
                lessons=lessons,
            )
        )
    return MyRoadmapDetail(
        assignment_id=a.id,
        roadmap_id=roadmap.id,
        title=roadmap.title,
        progress_percent=progress.percent(done, total),
        modules=modules,
    )


def _get_lesson_in_roadmap(
    db: Session, module_document_id: int, roadmap_id: int,
) -> ModuleDocument:
    """Fetch the module_document and ensure it belongs to `roadmap_id`."""
    md = db.get(ModuleDocument, module_document_id)
    if md is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    module = db.get(Module, md.module_id)
    if module is None or module.roadmap_id != roadmap_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lesson is not part of this assignment's roadmap",
        )
    return md


def set_completion(
    db: Session, user: User, module_document_id: int, assignment_id: int, completed: bool,
) -> CompleteResponse:
    a = _owned_assignment(db, user, assignment_id)
    md = _get_lesson_in_roadmap(db, module_document_id, a.roadmap_id)

    lp = db.scalar(
        select(LessonProgress).where(
            LessonProgress.assignment_id == a.id,
            LessonProgress.module_document_id == md.id,
        )
    )
    completed_at = None
    if completed:
        completed_at = _now()
        if lp is None:
            db.add(LessonProgress(
                assignment_id=a.id, module_document_id=md.id,
                completed=True, completed_at=completed_at,
            ))
        else:
            lp.completed = True
            lp.completed_at = completed_at
    else:
        # Unmark = remove the progress row (per spec).
        if lp is not None:
            db.delete(lp)

    db.flush()  # make the change visible to the recompute below
    _done, _total, pct = progress.sync_status(db, a)
    db.commit()
    return CompleteResponse(
        module_document_id=md.id,
        completed=completed,
        completed_at=completed_at,
        progress_percent=pct,
    )
