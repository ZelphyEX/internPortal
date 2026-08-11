# CLAUDE.md — Intern Portal

> File này là "bộ não" của dự án cho Claude Code. Đọc kỹ trước khi làm bất cứ việc gì.
> Nguồn sự thật đầy đủ về API nằm ở `docs/API_SPEC.md` (bản đặc tả đã chốt). Khi có mâu thuẫn, file đặc tả đó là chuẩn.

---

## 1. Dự án là gì

Hệ thống **Intern Portal**: quản lý thực tập sinh (Intern), giao lộ trình học (Roadmap), theo dõi tiến độ real-time. Có 3 role: `ADMIN` > `MENTOR` > `INTERN`. `MENTOR` mặc định gồm toàn bộ quyền của Intern; `ADMIN` gồm toàn bộ quyền của Mentor.

Tình trạng hiện tại: **repo trống**. Đã có sẵn (bên ngoài code):
- 1 instance **PostgreSQL** (chưa có bảng nào).
- 1 **bucket** để lưu file (ảnh đại diện, PDF tài liệu...).

Nhiệm vụ đầu tiên là dựng backend + tạo bảng bằng migration, KHÔNG tạo bảng thủ công trong DB.

---

## 2. Tech stack (đã CHỐT — không tự đổi)

| Layer | Công nghệ |
|---|---|
| Backend | **FastAPI (Python 3.11+)** |
| ORM | **SQLAlchemy 2.0** (style mới) |
| Migration | **Alembic** |
| Validation | **Pydantic v2** |
| Auth | **JWT** (access + refresh token) |
| DB | **PostgreSQL** |
| Storage | Bucket (S3-compatible / GCS) — cấu hình qua env |

> Đây là repo **backend-only**. Không có code frontend ở đây. Frontend là dự án riêng, chỉ gọi vào API này qua HTTP.

Quản lý package Python bằng `venv` + `requirements.txt` (hoặc `uv` nếu có). Password hash bằng `passlib[bcrypt]`. JWT bằng `python-jose` hoặc `pyjwt`.

---

## 3. Cấu trúc thư mục mục tiêu

Code nằm ngay ở gốc repo (repo này CHÍNH LÀ backend, không lồng trong `backend/`).

```
.
├── app/
│   ├── main.py               # khởi tạo FastAPI, mount router, CORS
│   ├── core/
│   │   ├── config.py         # đọc env (Settings, pydantic-settings)
│   │   ├── security.py       # hash password, tạo/verify JWT
│   │   └── deps.py           # get_db, get_current_user, require_role()
│   ├── db/
│   │   ├── base.py           # Base declarative + import models
│   │   └── session.py        # engine + SessionLocal
│   ├── models/               # SQLAlchemy models (1 file / bảng hoặc gom hợp lý)
│   ├── schemas/              # Pydantic request/response
│   ├── api/v1/routers/       # auth, users, groups, documents, tags,
│   │                         # roadmaps, modules, assignments, learning,
│   │                         # dashboard, comments, projects, tasks,
│   │                         # daily_reports
│   └── services/             # business logic (KHÔNG nhét logic vào router)
├── alembic/                  # migrations
├── alembic.ini
├── tests/
├── docs/
│   └── API_SPEC.md           # bản đặc tả API đầy đủ (nguồn sự thật)
├── requirements.txt
├── .env                      # KHÔNG commit
├── .env.example
└── CLAUDE.md
```

Cho phép **CORS** để frontend (chạy ở origin/domain khác) gọi được vào API.

---

## 4. DATABASE SCHEMA (bám sát để tạo models + migration)

Kiểu dữ liệu: `id` = BigInteger PK auto-increment. Mọi bảng có `created_at`, và bảng nào sửa được thì có `updated_at` (đều `TIMESTAMPTZ`, UTC).

- **users**: `id`, `full_name`, `email` (UNIQUE), `password_hash`, `role` ENUM(`ADMIN`,`MENTOR`,`INTERN`) default `INTERN`, `status` ENUM(`ACTIVE`,`LOCKED`) default `ACTIVE`, `avatar_url` (nullable), `deleted_at` (nullable — soft delete), `created_at`, `updated_at`.
  - Hồ sơ Intern (tất cả nullable, chỉ có ý nghĩa với `role=INTERN` — sửa qua `PATCH /users/{id}/profile`, quyền MENTOR): `department` ENUM `department`, `mentor_id` → users (self-FK, phải là MENTOR/ADMIN), `phone`, `start_date`, `end_date` (DATE), `university`, `major`, `bio`, `github_url`, `score` NUMERIC(5,2), `attendance_rate` NUMERIC(5,2).
  - ENUM **`department`** (dùng chung cho `users.department`, `modules.track`, `projects.department`): `Java Back-End`, `React Front-End`, `Cloud & DevOps`, `Salesforce/ERP`, `AI & Data Science`. Giá trị enum = đúng nhãn frontend hiển thị (đã chốt với FE) → không cần lớp map.
- **refresh_tokens**: `id`, `user_id` → users, `token_hash` (LƯU HASH, không lưu token thô), `expires_at`, `revoked_at` (nullable), `created_at`.
- **groups**: `id`, `name`, `cohort` (nullable), `description` (nullable), `created_at`, `updated_at`.
- **group_members** (N-N user↔group): `id`, `group_id` → groups, `user_id` → users, `joined_at`. **UNIQUE(`group_id`,`user_id`)**. Một Intern có thể thuộc nhiều nhóm.
- **documents**: `id`, `title`, `description` (nullable), `content_url`, `type` ENUM(`VIDEO`,`PDF`,`LINK`,`ARTICLE`), `created_at`, `updated_at`.
- **tags**: `id`, `name` (UNIQUE).
- **document_tags** (N-N): `document_id` → documents, `tag_id` → tags. PK kép (`document_id`,`tag_id`).
- **roadmaps**: `id`, `title`, `description` (nullable), `created_at`, `updated_at`.
- **modules** (Chặng): `id`, `roadmap_id` → roadmaps, `title`, `description` (nullable), `position` (int, để sắp xếp), `created_at`, `updated_at`.
  - Metadata course card (FE cần, nullable): `track` ENUM `department`, `week_number` (int), `duration_text` (String(100), text tự do vd "2 tuần"), `key_skills` JSONB NOT NULL default `'[]'`.
- **module_documents** (Bài học = document gán vào chặng): `id`, `module_id` → modules, `document_id` → documents, `position` (int), `created_at`.
  - ⚠️ `module_documents.id` chính là **`module_document_id`** dùng cho đánh dấu hoàn thành và comment.
- **roadmap_assignments** (lượt gán lộ trình): `id`, `roadmap_id` → roadmaps, `user_id` → users, `status` ENUM(`IN_PROGRESS`,`COMPLETED`) default `IN_PROGRESS`, `source_group_id` → groups (nullable — nếu gán qua nhóm), `assigned_at`. **UNIQUE(`roadmap_id`,`user_id`)** để chống gán trùng.
  - ⚠️ `roadmap_assignments.id` chính là **`assignment_id`**.
- **lesson_progress**: `id`, `assignment_id` → roadmap_assignments, `module_document_id` → module_documents, `completed` (bool), `completed_at` (nullable). **UNIQUE(`assignment_id`,`module_document_id`)**.
- **comments**: `id`, `module_document_id` → module_documents, `user_id` → users, `content`, `code_snippet` (nullable — đoạn code đính kèm), `is_resolved` (bool NOT NULL default false — chỉ MENTOR đổi qua `PATCH /comments/{id}/resolve`), `parent_comment_id` → comments (nullable, self-ref cho reply), `created_at`, `updated_at`.
- **projects** (Dự án): `id`, `code` (UNIQUE), `title`, `department` ENUM `department` (nullable), `status` ENUM `project_status`(`In Planning`,`Active`,`Under Review`,`Completed`) default `In Planning`, `lead_user_id` → users (nullable), `progress_percent` (int, mentor tự cập nhật — KHÔNG suy ra từ tasks), `deadline` (DATE nullable), `description` (nullable), `deleted_at` (nullable — **soft delete** vì tasks còn tham chiếu), `created_at`, `updated_at`.
- **project_members** (N-N user↔project): `id`, `project_id` → projects, `user_id` → users, `joined_at`. **UNIQUE(`project_id`,`user_id`)**.
- **project_tags** (N-N, dùng chung bảng `tags` với documents): PK kép (`project_id`,`tag_id`).
- **tasks**: `id`, `title`, `project_id` → projects (nullable), `assigned_intern_id` → users (nullable), `mentor_id` → users (nullable), `status` ENUM `task_status`(`To Do`,`In Progress`,`In Review`,`Done`,`Blocked`) default `To Do`, `priority` ENUM `task_priority`(`Low`,`Medium`,`High`,`Urgent`) default `Medium`, `due_date` (DATE nullable), `description` (nullable), `pr_url` (nullable), `mentor_feedback` (nullable — chỉ MENTOR ghi), `completed_at` (nullable — backend tự set khi `status=Done`, xóa khi rời `Done`), `created_at`, `updated_at`.
- **daily_reports**: `id`, `intern_id` → users, `date` (DATE), `completed_today`, `tomorrow_plan` (nullable), `blockers` (nullable), `hours_logged` NUMERIC(4,2) (nullable), `status` ENUM `daily_report_status`(`Pending`,`Approved`,`Needs Revision`) default `Pending`, `mentor_comment` (nullable), `rating` (int 1..5 nullable), `reviewed_by` → users (nullable), `reviewed_at` (nullable), `created_at`, `updated_at`. **UNIQUE(`intern_id`,`date`)** — 1 báo cáo / người / ngày.

**Cách tính % tiến độ:** `progress_percent = completed_lessons / total_lessons * 100`, với `total_lessons` = tổng số `module_documents` của roadmap tương ứng. Tính lại mỗi lần mark/unmark. Khi tất cả bài `completed` → tự set `roadmap_assignments.status = COMPLETED`.

---

## 5. Quy ước API (bắt buộc)

- Base URL: **`/api/v1`**. FastAPI tự sinh Swagger tại `/docs`.
- Auth header: `Authorization: Bearer <access_token>`.
- Login trả `access_token` (JWT ngắn hạn, 30 phút) + `refresh_token` (lưu **hash** trong `refresh_tokens`) + `session_expires_at`. Access token hết hạn → gọi `/auth/refresh`.
- **Một phiên đăng nhập chỉ sống `REFRESH_TOKEN_EXPIRE_DAYS` = 1 ngày.** Đây là hạn TUYỆT ĐỐI: `/auth/refresh` không cấp refresh token mới nên không đẩy mốc này ra xa. Hết hạn là phải đăng nhập lại, kể cả khi đang dùng liên tục.
- **Người dùng chỉ đăng nhập bằng Google** (`POST /auth/google` → `POST /auth/google/complete`), chỉ nhận email thuộc `ALLOWED_EMAIL_DOMAINS`. `POST /auth/register` đã tắt; `POST /auth/login` (mật khẩu) chỉ dành cho tài khoản ADMIN do `scripts/ensure_admin.py` tạo.
- Phân trang: query `?page=1&size=20`. Response: `{ "items": [], "total", "page", "size", "pages" }`.
- Định dạng lỗi: `{ "detail": "..." }`.
- Mã trạng thái: 200 OK, 201 Created, 204 No Content, 400, 401 (chưa/hết hạn token), 403 (thiếu quyền), 404, 409 (trùng dữ liệu), 422 (sai kiểu — FastAPI tự validate).
- Thời gian: ISO 8601 UTC, ví dụ `2026-07-22T09:30:00Z`.

Danh sách endpoint đầy đủ + ví dụ request/response: xem `docs/API_SPEC.md`.

---

## 6. LUẬT BẢO MẬT (IMPORTANT — không được vi phạm)

- **IMPORTANT:** Kiểm tra quyền ở MỌI endpoint bằng dependency (vd `require_role(MENTOR)`). **KHÔNG BAO GIỜ tin frontend.**
- **IMPORTANT:** Với endpoint `/me/...`, luôn kiểm tra tài nguyên thuộc về user trong token. Intern không được xem dữ liệu người khác (sai → 403).
- **IMPORTANT:** Các list endpoint dùng chung cho cả 2 role (`/projects`, `/tasks`, `/daily-reports`) phải **tự thu hẹp phạm vi theo role trong service**, KHÔNG dựa vào filter client gửi lên: INTERN chỉ thấy dự án mình là lead/thành viên, task được gán cho mình, báo cáo của mình — kể cả khi client truyền `assigned_intern_id`/`intern_id` của người khác.
- **IMPORTANT:** Không lưu token/password dạng thô. Password → bcrypt hash. Refresh token → lưu hash.
- **IMPORTANT:** Mọi thao tác hàng loạt (`assign-group`, thêm nhiều thành viên) phải chạy trong **1 transaction** và **bỏ qua bản ghi trùng** thay vì báo lỗi.
- Xóa user và document theo yêu cầu là **soft delete** (`deleted_at`), không xóa vật lý.
- Secrets chỉ nằm trong `.env`. **KHÔNG commit `.env`**; luôn có `.env.example`.

---

## 7. Quy tắc làm việc với DB & code

- **KHÔNG tạo/sửa bảng thủ công trong PostgreSQL.** Mọi thay đổi schema đi qua Alembic: sửa model → `alembic revision --autogenerate -m "..."` → kiểm tra file migration → `alembic upgrade head`.
- Không nhét business logic vào router — để trong `services/`. Router chỉ nhận request, gọi service, trả response.
- Mỗi model có Pydantic schema riêng cho Request và Response. Không trả `password_hash` ra ngoài.
- Viết code chạy được rồi mới báo xong; nếu thêm dependency, cập nhật `requirements.txt`.

---

## 8. Lệnh hay dùng (cập nhật khi có)

```bash
# Chạy từ gốc repo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload            # chạy dev, mở http://localhost:8000/docs

# Migration mới
alembic revision --autogenerate -m "add xxx"
alembic upgrade head

# Test
pytest
```

---

## 9. THỨ TỰ BUILD (làm lần lượt, không nhảy cóc)

1. Scaffold ở gốc repo: `app/core/config.py` (đọc env), `app/db/session.py`, `app/db/base.py`, `app/main.py`, cài Alembic + trỏ tới DATABASE_URL.
2. Viết **toàn bộ models** ở mục 4 → tạo migration đầu tiên → `upgrade head` (kiểm tra bảng đã lên DB).
3. `core/security.py` + `core/deps.py`: hash password, JWT, `get_current_user`, `require_role()`.
4. **Auth**: register (chỉ tạo INTERN), login, refresh, logout, `GET/PATCH /auth/me`, change-password.
5. **Users** (Mentor/Admin): list + search + pagination, create mentor (ADMIN), detail, lock/unlock, soft delete.
6. **Groups** + members (thêm nhiều / kick).
7. **Documents** + upload (bucket) + **Tags**.
8. **Roadmaps** → **Modules** → gán document vào chặng (`module_documents`).
9. **Assignments**: gán cá nhân + `assign-group` (bulk, transaction).
10. **Learning**: `/me/roadmaps`, mark/unmark complete, tính % real-time.
11. **Comments** (có reply lồng nhau).
12. **Dashboard**: `/dashboard/me`, `/dashboard/overview`, `/dashboard/roadmaps/{id}`.
13. **Phase 3 — theo `docs/backend-requirements.md`** (đã xong): field hồ sơ Intern + `PATCH /users/{id}/profile`; metadata chặng; `code_snippet`/`is_resolved` + `PATCH /comments/{id}/resolve`; resource mới **Projects / Tasks / Daily Reports**; bổ sung field Dashboard. Phần "major task → section" của mục 5 vẫn **để mở**, cần họp với FE trước khi thêm cấp con.

Sau mỗi bước: chạy thử trên `/docs`, xác nhận không lỗi, rồi mới sang bước tiếp theo. Khi xong toàn bộ, Swagger tại `/docs` chính là "hợp đồng" để phía frontend gọi API.