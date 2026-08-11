"""Roadmap-assignment business logic (API_SPEC mục 7).

Both assign endpoints run in a single transaction and skip interns that are
already assigned (UNIQUE(roadmap_id,user_id)) rather than erroring
(CLAUDE.md mục 6). Progress in the list view is computed live via
`app.services.progress`.
"""
from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.assignment import LessonProgress, RoadmapAssignment
from app.models.group import Group, GroupMember
from app.models.roadmap import Roadmap
from app.models.user import User
from app.schemas.assignment import (
    AssignCreatedItem,
    AssignmentListItem,
    AssignResponse,
)
from app.services import progress


def _get_roadmap(db: Session, roadmap_id: int) -> Roadmap:
    r = db.get(Roadmap, roadmap_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")
    return r


def _existing_assignments(db: Session, roadmap_id: int, user_ids) -> dict[int, int]:
    """user_id -> assignment_id for interns already assigned to this roadmap."""
    if not user_ids:
        return {}
    rows = db.execute(
        select(RoadmapAssignment.user_id, RoadmapAssignment.id).where(
            RoadmapAssignment.roadmap_id == roadmap_id,
            RoadmapAssignment.user_id.in_(list(user_ids)),
        )
    ).all()
    return {uid: aid for uid, aid in rows}


def _valid_user_ids(db: Session, user_ids) -> set[int]:
    """Subset of user_ids that are existing, non-deleted users."""
    if not user_ids:
        return set()
    return set(
        db.scalars(
            select(User.id).where(
                User.id.in_(list(user_ids)), User.deleted_at.is_(None)
            )
        ).all()
    )


def assign(db: Session, roadmap_id: int, user_ids: list[int]) -> AssignResponse:
    _get_roadmap(db, roadmap_id)
    valid = _valid_user_ids(db, set(user_ids))
    existing = set(_existing_assignments(db, roadmap_id, valid))
    to_create = valid - existing
    created: list[RoadmapAssignment] = [
        RoadmapAssignment(roadmap_id=roadmap_id, user_id=uid) for uid in to_create
    ]
    if created:
        db.add_all(created)
        db.commit()
        for a in created:
            db.refresh(a)
    return AssignResponse(
        created=[AssignCreatedItem(assignment_id=a.id, user_id=a.user_id) for a in created]
    )


def assign_group(db: Session, roadmap_id: int, group_id: int) -> tuple[int, int]:
    """Assign the roadmap to every (non-deleted) member of the group.
    Returns (assigned_count, skipped_existing)."""
    _get_roadmap(db, roadmap_id)
    if db.get(Group, group_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    member_ids = set(
        db.scalars(
            select(GroupMember.user_id)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id, User.deleted_at.is_(None))
        ).all()
    )
    existing = set(_existing_assignments(db, roadmap_id, member_ids))
    to_create = member_ids - existing
    if to_create:
        db.add_all(
            RoadmapAssignment(
                roadmap_id=roadmap_id, user_id=uid, source_group_id=group_id,
            )
            for uid in to_create
        )
        db.commit()
    return len(to_create), len(member_ids) - len(to_create)


# --------------------------------------------------------------------------- #
# Gán theo nhóm = LUẬT THƯỜNG TRỰC, không phải một lần chép
#
# `source_group_id` ghi lại "người này có lộ trình vì thuộc nhóm X". Nhờ đó:
#   * ai vào nhóm SAU vẫn được nhận lộ trình của nhóm (`sync_new_group_members`);
#   * rời nhóm thì chỉ thu hồi đúng phần đến từ nhóm, và chỉ khi chưa học gì
#     (`revoke_for_leaving_member`).
# --------------------------------------------------------------------------- #
def roadmap_ids_for_group(db: Session, group_id: int) -> set[int]:
    """Các lộ trình đang được gán cho nhóm này."""
    return set(
        db.scalars(
            select(RoadmapAssignment.roadmap_id)
            .where(RoadmapAssignment.source_group_id == group_id)
            .distinct()
        ).all()
    )


def sync_new_group_members(db: Session, group_id: int, user_ids: set[int]) -> int:
    """Gán mọi lộ trình của nhóm cho những người vừa được thêm vào nhóm.

    Đây là chỗ vá lỗi cũ: trước đây `assign_group` chỉ gán cho thành viên CÓ MẶT
    lúc bấm gán, nên người vào nhóm sau không hề nhận được lộ trình nào.

    Trả về số lượt gán mới. Không commit — người gọi commit chung một transaction.
    """
    if not user_ids:
        return 0
    roadmap_ids = roadmap_ids_for_group(db, group_id)
    if not roadmap_ids:
        return 0

    # Bỏ qua ai đã có lộ trình đó rồi (dù được gán lẻ hay qua nhóm khác).
    existing = {
        (rid, uid)
        for rid, uid in db.execute(
            select(RoadmapAssignment.roadmap_id, RoadmapAssignment.user_id).where(
                RoadmapAssignment.roadmap_id.in_(roadmap_ids),
                RoadmapAssignment.user_id.in_(user_ids),
            )
        ).all()
    }
    created = [
        RoadmapAssignment(roadmap_id=rid, user_id=uid, source_group_id=group_id)
        for rid in roadmap_ids
        for uid in user_ids
        if (rid, uid) not in existing
    ]
    if created:
        db.add_all(created)
    return len(created)


def revoke_for_leaving_member(db: Session, group_id: int, user_id: int) -> tuple[int, int]:
    """Xử lý lộ trình khi một người rời nhóm. Trả về (đã gỡ, giữ lại vì đã học).

    Luật: chỉ đụng tới lộ trình ĐẾN TỪ nhóm này. Nếu người đó đã hoàn thành bài
    nào trong lộ trình thì KHÔNG gỡ — thay vào đó chuyển thành gán cá nhân
    (`source_group_id = NULL`). Rời nhóm không được phép xoá công sức đã học.
    Lộ trình được gán lẻ từ đầu thì không liên quan, giữ nguyên.
    """
    from_group = list(
        db.scalars(
            select(RoadmapAssignment).where(
                RoadmapAssignment.source_group_id == group_id,
                RoadmapAssignment.user_id == user_id,
            )
        ).all()
    )
    if not from_group:
        return 0, 0

    started = set(
        db.scalars(
            select(LessonProgress.assignment_id).where(
                LessonProgress.assignment_id.in_([a.id for a in from_group]),
                LessonProgress.completed.is_(True),
            )
        ).all()
    )
    removed = kept = 0
    for a in from_group:
        if a.id in started:
            a.source_group_id = None  # giữ lại, chuyển thành gán cá nhân
            kept += 1
        else:
            db.delete(a)
            removed += 1
    return removed, kept


def get_assignment(db: Session, assignment_id: int) -> RoadmapAssignment:
    a = db.get(RoadmapAssignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return a


def delete_assignment(db: Session, a: RoadmapAssignment) -> None:
    """Cancel an assignment; its lesson_progress rows go with it (transaction)."""
    db.query(LessonProgress).filter(
        LessonProgress.assignment_id == a.id
    ).delete(synchronize_session=False)
    db.delete(a)
    db.commit()


def list_query(
    *, roadmap_id: int | None, user_id: int | None,
    group_id: int | None, status_: str | None,
) -> Select:
    stmt = select(RoadmapAssignment)
    if roadmap_id is not None:
        stmt = stmt.where(RoadmapAssignment.roadmap_id == roadmap_id)
    if user_id is not None:
        stmt = stmt.where(RoadmapAssignment.user_id == user_id)
    if group_id is not None:
        stmt = stmt.where(RoadmapAssignment.source_group_id == group_id)
    if status_ is not None:
        stmt = stmt.where(RoadmapAssignment.status == status_)
    return stmt.order_by(RoadmapAssignment.id.desc())


def to_list_items(db: Session, rows: list[RoadmapAssignment]) -> list[AssignmentListItem]:
    if not rows:
        return []
    roadmap_ids = {r.roadmap_id for r in rows}
    user_ids = {r.user_id for r in rows}
    titles = dict(
        db.execute(select(Roadmap.id, Roadmap.title).where(Roadmap.id.in_(roadmap_ids))).all()
    )
    names = dict(
        db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all()
    )
    totals = progress.total_lessons_map(db, roadmap_ids)
    completed = progress.completed_counts(db, [r.id for r in rows])
    return [
        AssignmentListItem(
            assignment_id=r.id,
            roadmap_id=r.roadmap_id,
            roadmap_title=titles.get(r.roadmap_id, ""),
            user_id=r.user_id,
            user_name=names.get(r.user_id, ""),
            status=r.status,
            progress_percent=progress.percent(
                completed.get(r.id, 0), totals.get(r.roadmap_id, 0)
            ),
            assigned_at=r.assigned_at,
        )
        for r in rows
    ]
