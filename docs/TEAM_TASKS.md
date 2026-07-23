# TEAM_TASKS.md — Phân công 2 người (bàn giao tuần tự)

> Đọc cùng `CLAUDE.md` (quy ước dự án) và `docs/API_SPEC.md` (đặc tả API đầy đủ).
> Mô hình: **TUẦN TỰ, KHÔNG song song.**
> **Dev A** xây trọn database + cloud storage + nền tảng + các API gắn với dữ liệu/storage → đẩy lên `main`.
> **Dev B** pull về, đọc code, rồi **viết tiếp các API còn lại** trên nền A đã dựng.

---

## 0. Tóm tắt

| | Dev A — Nền tảng, Data, Storage | Dev B — Các API còn lại |
|---|---|---|
| Bắt đầu | Ngay từ đầu (repo trống) | Sau khi A bàn giao & merge `main` |
| Chạm database | ✅ Tạo toàn bộ schema + migration | Chỉ đọc/ghi qua model có sẵn, gần như không cần migration |
| Chạm cloud storage | ✅ Tích hợp bucket + upload | ❌ (chỉ nhận URL đã có) |
| Kết quả bàn giao | Backend chạy được, `/docs` có sẵn Auth + Content | Bổ sung phần người dùng, nhóm, gán, học tập, dashboard |

---

## 1. PHASE 1 — Dev A (làm trước, làm hết phần này)

Mục tiêu: sau Phase 1, repo phải **chạy được**, đăng nhập được, quản lý được tài liệu/lộ trình — B chỉ việc cắm thêm router vào.

### 1.1 Nền tảng & Database
1. Scaffold `app/...` ở gốc repo (mục 3 CLAUDE.md), `main.py` bật CORS + prefix `/api/v1`.
2. `core/config.py` đọc `.env` (+ `.env.example`), `db/session.py`, `db/base.py`.
3. **Toàn bộ SQLAlchemy models** theo mục 4 CLAUDE.md — đủ enum, FK, UNIQUE, self-ref comments. Làm HẾT mọi bảng ngay cả bảng mà sau này B mới dùng (users, groups, assignments, lesson_progress, comments...).
4. Alembic + **migration tạo hết bảng** → `upgrade head`, xác nhận đủ bảng trên DB.

### 1.2 Bảo mật (để B tái sử dụng)
5. `core/security.py`: bcrypt hash password, tạo/verify JWT (access + refresh).
6. `core/deps.py`: `get_db`, `get_current_user`, `require_role()`. **Đây là thứ B sẽ dùng cho mọi endpoint** — làm chắc và đặt tên rõ ràng.

### 1.3 Cloud Storage
7. `services/storage.py`: bọc bucket (endpoint, key, bucket name qua env; có chế độ lưu local khi dev).
8. `POST /documents/upload` — nhận `multipart/form-data`, đẩy lên bucket, trả `content_url`.

### 1.4 Các API gắn với dữ liệu/storage
9. **Auth** (`docs/API_SPEC.md` mục 2): register (chỉ INTERN), login, refresh, logout, `GET/PATCH /auth/me`, change-password. (Bám nặng users + refresh_tokens.)
10. **Documents** (mục 5): `GET/POST/GET{id}/PATCH/DELETE /documents` (lọc tag, search, phân trang).
11. **Tags** (mục 5): `GET/POST /tags` (name UNIQUE → 409), `DELETE /tags/{id}`.
12. **Roadmaps / Modules / gán tài liệu** (mục 6): CRUD `/roadmaps`, `POST /roadmaps/{id}/modules`, `PATCH/DELETE /modules/{id}`, `POST /modules/{id}/documents`, `DELETE /module-documents/{id}`.

**Xong Phase 1:** commit + push `main`, chạy thử toàn bộ trên `/docs`.

---

## 2. BÀN GIAO — "Định nghĩa Hoàn thành" của Dev A

Trước khi A báo xong, phải đủ:
- [ ] `alembic upgrade head` chạy sạch, đủ mọi bảng ở mục 4.
- [ ] `uvicorn app.main:app --reload` lên được, `/docs` hiển thị nhóm Auth + Documents + Tags + Roadmaps.
- [ ] Đăng ký → đăng nhập → gọi được 1 endpoint có `Authorization: Bearer`.
- [ ] `.env.example` đầy đủ biến (DATABASE_URL, JWT secret, bucket config).
- [ ] Ghi vào PR / một đoạn ngắn trong README: **chữ ký các hàm dùng chung** cho B — cụ thể `get_current_user`, `require_role(...)`, và (nếu có) helper query/paginate.

---

## 3. PHASE 2 — Dev B (pull về rồi viết tiếp)

Bắt đầu bằng: `git pull main` → đọc `app/models/`, `core/deps.py`, `services/`. **Dùng lại** model + deps + storage của A, **không tạo lại**. Schema đã đầy đủ nên B gần như không cần migration; nếu thật sự phát sinh cột mới, B tạo migration nối tiếp (an toàn vì tuần tự, chỉ mình B đang chạm DB lúc này).

Các API phụ trách (`docs/API_SPEC.md`):
- **Users (Mentor/Admin)** (mục 3): `GET /users` (search + phân trang), `POST /users` (ADMIN tạo mentor), `GET /users/{id}`, `PATCH /users/{id}/lock` + `/unlock`, `DELETE /users/{id}` (soft delete).
- **Groups** (mục 4): CRUD `/groups`, `POST /groups/{id}/members` (thêm nhiều), `DELETE /groups/{id}/members/{user_id}`.
- **Assignments** (mục 7): `POST /roadmaps/{id}/assign`, `POST /roadmaps/{id}/assign-group` (bulk — transaction, bỏ qua trùng), `DELETE /roadmap-assignments/{id}`, `GET /roadmap-assignments`.
- **Learning & Progress** (mục 8): `GET /me/roadmaps`, `GET /me/roadmaps/{assignment_id}`, `POST/DELETE /lessons/{module_document_id}/complete`. Viết luôn logic tính `progress_percent` = completed/total×100, và tự set `status=COMPLETED` khi đủ 100%.
- **Dashboard** (mục 9): `GET /dashboard/me`, `GET /dashboard/overview`, `GET /dashboard/roadmaps/{id}` (query aggregate).
- **Comments** (mục 10): `GET/POST /lessons/{module_document_id}/comments`, `PATCH/DELETE /comments/{id}` (reply lồng nhau, chỉ chủ comment/Mentor được xóa).

Mỗi router mới nhớ include vào `app/main.py`.

---

## 4. Luật chung
- Nguồn sự thật là `docs/API_SPEC.md` — không tự chế field/response khác đặc tả.
- Tuân thủ **LUẬT BẢO MẬT** (mục 6 CLAUDE.md): kiểm quyền bằng `require_role`, endpoint `/me/*` phải kiểm tài nguyên thuộc về user trong token, bulk chạy trong transaction & bỏ qua trùng, soft delete thay vì xóa cứng.
- Vì làm tuần tự, không cần nhánh phức tạp; nhưng B nên làm trên nhánh `feat/phase-2` rồi PR về `main` để A review.