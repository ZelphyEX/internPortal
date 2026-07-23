# ĐẶC TẢ API — INTERN PORTAL

> Tài liệu này mô tả toàn bộ REST API của hệ thống, bám theo schema database đã chốt. Backend dùng làm bản thiết kế để code; Frontend dùng làm "hợp đồng" để gọi API. FastAPI sẽ tự sinh Swagger tương ứng tại `/docs`.

## Mục lục
1. Quy ước chung
2. Nhóm API: Auth & Profile
3. Nhóm API: Quản lý User (Mentor/Admin)
4. Nhóm API: Nhóm (Groups)
5. Nhóm API: Tài liệu (Documents) & Tags
6. Nhóm API: Lộ trình (Roadmaps), Chặng (Modules), gán tài liệu
7. Nhóm API: Gán lộ trình (Assignments) & bulk assign
8. Nhóm API: Học tập & Tiến độ (Progress)
9. Nhóm API: Dashboard
10. Nhóm API: Comment
11. Bảng tổng hợp toàn bộ endpoint

---

## 1. Quy ước chung

**Base URL:** `/api/v1`

**Xác thực:** gửi access token ở header với mọi request cần đăng nhập:
```
Authorization: Bearer <access_token>
```

**Cơ chế token:** đăng nhập trả về `access_token` (JWT ngắn hạn, ví dụ 15–60 phút) và `refresh_token` (dài hạn, lưu hash trong bảng `refresh_tokens`). Khi access token hết hạn, gọi `/auth/refresh` để lấy cái mới.

**Vai trò (role):** `ADMIN` | `MENTOR` | `INTERN`. Trong tài liệu, "MENTOR" ngầm hiểu gồm cả ADMIN (ADMIN có mọi quyền của MENTOR). Cột "Quyền" ghi role tối thiểu được gọi.

**Phân trang:** dùng query `?page=1&size=20`. Response dạng:
```json
{
  "items": [],
  "total": 135,
  "page": 1,
  "size": 20,
  "pages": 7
}
```

**Định dạng lỗi** (chuẩn FastAPI):
```json
{ "detail": "Thông báo lỗi" }
```

**Mã trạng thái dùng chung:**
- `200 OK` — thành công (GET/PATCH).
- `201 Created` — tạo mới thành công.
- `204 No Content` — xóa thành công, không trả body.
- `400 Bad Request` — dữ liệu gửi lên sai.
- `401 Unauthorized` — chưa đăng nhập / token sai/hết hạn.
- `403 Forbidden` — đã đăng nhập nhưng không đủ quyền.
- `404 Not Found` — không tìm thấy tài nguyên.
- `409 Conflict` — trùng dữ liệu (ví dụ email đã tồn tại).
- `422 Unprocessable Entity` — sai kiểu dữ liệu (FastAPI validate tự động).

**Kiểu thời gian:** ISO 8601 UTC, ví dụ `2026-07-22T09:30:00Z`.

---

## 2. Nhóm API: Auth & Profile

### POST /auth/register — Đăng ký (chỉ tạo INTERN)
Quyền: công khai (không cần token).
```json
// Request
{ "full_name": "Nguyen Van A", "email": "a@example.com", "password": "matkhau123" }
```
```json
// Response 201
{ "id": 12, "full_name": "Nguyen Van A", "email": "a@example.com", "role": "INTERN", "status": "ACTIVE" }
```
Lỗi: `409` nếu email đã tồn tại. Tài khoản MENTOR/ADMIN không tạo qua đây (xem mục 3).

### POST /auth/login — Đăng nhập
Quyền: công khai.
```json
// Request
{ "email": "a@example.com", "password": "matkhau123" }
```
```json
// Response 200
{
  "access_token": "eyJhbGci...",
  "refresh_token": "d9f3...",
  "token_type": "bearer",
  "user": { "id": 12, "full_name": "Nguyen Van A", "role": "INTERN", "avatar_url": null }
}
```
Lỗi: `401` nếu sai thông tin; `403` nếu tài khoản đang `LOCKED`.

### POST /auth/refresh — Làm mới access token
Quyền: công khai (dùng refresh token).
```json
// Request
{ "refresh_token": "d9f3..." }
```
```json
// Response 200
{ "access_token": "eyJhbGci...", "token_type": "bearer" }
```
Lỗi: `401` nếu refresh token sai, hết hạn, hoặc đã bị revoke.

### POST /auth/logout — Đăng xuất
Quyền: INTERN/MENTOR. Thu hồi (revoke) refresh token hiện tại.
```json
// Request
{ "refresh_token": "d9f3..." }
```
Response `204`.

### GET /auth/me — Lấy thông tin tài khoản hiện tại
Quyền: INTERN/MENTOR.
```json
// Response 200
{ "id": 12, "full_name": "Nguyen Van A", "email": "a@example.com",
  "role": "INTERN", "status": "ACTIVE", "avatar_url": "https://.../a.png" }
```

### PATCH /auth/me — Cập nhật profile (tên, ảnh)
Quyền: INTERN/MENTOR.
```json
// Request (gửi field nào cập nhật field đó)
{ "full_name": "Nguyen Van An", "avatar_url": "https://.../new.png" }
```
Response `200` trả user đã cập nhật.

> Upload ảnh đại diện: gọi `POST /documents/upload` (hoặc endpoint upload riêng) để lấy URL, rồi truyền `avatar_url` vào đây.

### POST /auth/change-password — Đổi mật khẩu
Quyền: INTERN/MENTOR.
```json
// Request
{ "old_password": "matkhau123", "new_password": "matkhaumoi456" }
```
Response `204`. Lỗi: `400` nếu mật khẩu cũ sai.

---

## 3. Nhóm API: Quản lý User (Mentor/Admin)

### GET /users — Liệt kê, tìm kiếm, phân trang Intern
Quyền: MENTOR.
Query: `?page=1&size=20&search=<tên hoặc email>&role=INTERN&status=ACTIVE`
```json
// Response 200 (dạng phân trang)
{ "items": [
    { "id": 12, "full_name": "Nguyen Van A", "email": "a@example.com", "role": "INTERN", "status": "ACTIVE" }
  ], "total": 40, "page": 1, "size": 20, "pages": 2 }
```

### POST /users — Tạo tài khoản (thường để Admin tạo MENTOR)
Quyền: ADMIN.
```json
// Request
{ "full_name": "Mentor B", "email": "b@example.com", "password": "...", "role": "MENTOR" }
```
Response `201`.

### GET /users/{id} — Chi tiết một user
Quyền: MENTOR. Response `200` trả thông tin user.

### PATCH /users/{id}/lock — Khóa tài khoản
Quyền: MENTOR. Đặt `status = LOCKED`. Response `200`.

### PATCH /users/{id}/unlock — Mở khóa
Quyền: MENTOR. Đặt `status = ACTIVE`. Response `200`.

### DELETE /users/{id} — Xóa mềm (soft delete)
Quyền: ADMIN. Đặt `deleted_at`, không xóa khỏi DB. Response `204`.

---

## 4. Nhóm API: Nhóm (Groups)

### GET /groups — Danh sách nhóm
Quyền: MENTOR. Query hỗ trợ `?search=&cohort=&page=&size=`.
```json
// Response 200 (item)
{ "id": 3, "name": "Frontend Khóa 1", "cohort": "K1", "description": "...", "member_count": 8 }
```

### POST /groups — Tạo nhóm
Quyền: MENTOR.
```json
// Request
{ "name": "Frontend Khóa 1", "cohort": "K1", "description": "Nhóm TTS frontend" }
```
Response `201`.

### GET /groups/{id} — Chi tiết nhóm (kèm danh sách thành viên)
Quyền: MENTOR.
```json
// Response 200
{ "id": 3, "name": "Frontend Khóa 1", "cohort": "K1", "description": "...",
  "members": [ { "id": 12, "full_name": "Nguyen Van A", "email": "a@example.com" } ] }
```

### PATCH /groups/{id} — Sửa thông tin nhóm
Quyền: MENTOR. Response `200`.

### DELETE /groups/{id} — Xóa nhóm
Quyền: MENTOR. Response `204`.

### POST /groups/{id}/members — Thêm nhiều Intern vào nhóm
Quyền: MENTOR.
```json
// Request (thêm hàng loạt)
{ "user_ids": [12, 15, 18] }
```
Response `200` trả danh sách thành viên mới. (Một Intern có thể thuộc nhiều nhóm — không báo lỗi nếu đã ở nhóm khác; chỉ chống trùng trong cùng nhóm.)

### DELETE /groups/{id}/members/{user_id} — Kick một Intern khỏi nhóm
Quyền: MENTOR. Response `204`.

---

## 5. Nhóm API: Tài liệu (Documents) & Tags

### GET /documents — Danh sách tài liệu (lọc theo tag, tìm kiếm, phân trang)
Quyền: INTERN (chỉ xem) / MENTOR.
Query: `?page=1&size=20&search=<tiêu đề>&tag=git&type=PDF`
```json
// Response 200 (item)
{ "id": 5, "title": "Git cơ bản", "description": "...", "content_url": "https://.../git.pdf",
  "type": "PDF", "tags": ["git", "cơ bản"], "created_at": "2026-07-01T00:00:00Z" }
```

### POST /documents — Tạo tài liệu mới
Quyền: MENTOR.
```json
// Request
{ "title": "Git cơ bản", "description": "Bài mở đầu", "content_url": "https://.../git.pdf",
  "type": "PDF", "tag_ids": [1, 4] }
```
Response `201`. (`type`: `VIDEO` | `PDF` | `LINK` | `ARTICLE`.)

### GET /documents/{id} — Chi tiết tài liệu
Quyền: INTERN/MENTOR. Response `200`.

### PATCH /documents/{id} — Sửa tài liệu
Quyền: MENTOR. Có thể cập nhật `tag_ids` để gán lại tags. Response `200`.

### DELETE /documents/{id} — Xóa tài liệu
Quyền: MENTOR. Response `204`.

### POST /documents/upload — Upload file (PDF, ảnh...)
Quyền: MENTOR (ảnh đại diện: INTERN/MENTOR). `multipart/form-data`, field `file`.
```json
// Response 201
{ "content_url": "https://storage.googleapis.com/intern-portal-files/abc.pdf" }
```
File được lưu lên Cloud Storage (hoặc thư mục local khi dev); API chỉ trả URL để gán vào `content_url`/`avatar_url`.

### GET /tags — Danh sách tag
Quyền: INTERN/MENTOR. Response `200`: `[{ "id": 1, "name": "git" }]`.

### POST /tags — Tạo tag
Quyền: MENTOR.
```json
{ "name": "docker" }
```
Response `201`. Lỗi `409` nếu tên tag trùng (`name` là unique).

### DELETE /tags/{id} — Xóa tag
Quyền: MENTOR. Response `204`.

---

## 6. Nhóm API: Lộ trình, Chặng, gán tài liệu

### GET /roadmaps — Danh sách lộ trình
Quyền: INTERN/MENTOR (Intern có thể xem để tham khảo; lộ trình được giao xem ở mục 8).
```json
// Response 200 (item)
{ "id": 7, "title": "Lộ trình Frontend", "description": "...", "module_count": 4 }
```

### POST /roadmaps — Tạo lộ trình
Quyền: MENTOR.
```json
{ "title": "Lộ trình Frontend", "description": "Dành cho TTS FE" }
```
Response `201`.

### GET /roadmaps/{id} — Chi tiết lộ trình (kèm chặng và bài học)
Quyền: INTERN/MENTOR.
```json
// Response 200
{ "id": 7, "title": "Lộ trình Frontend", "description": "...",
  "modules": [
    { "id": 20, "title": "Nhập môn", "position": 1,
      "documents": [
        { "module_document_id": 100, "document_id": 5, "title": "Git cơ bản", "type": "PDF", "position": 1 }
      ] }
  ] }
```
> Lưu ý: bài học trong chặng được tham chiếu bằng `module_document_id` — đây là ID dùng cho việc đánh dấu hoàn thành và comment.

### PATCH /roadmaps/{id} — Sửa lộ trình
Quyền: MENTOR. Response `200`.

### DELETE /roadmaps/{id} — Xóa lộ trình
Quyền: MENTOR. Response `204`.

### POST /roadmaps/{roadmap_id}/modules — Thêm chặng
Quyền: MENTOR.
```json
{ "title": "Nhập môn", "description": "...", "position": 1 }
```
Response `201`.

### PATCH /modules/{id} — Sửa chặng (kể cả đổi `position` để sắp xếp lại)
Quyền: MENTOR. Response `200`.

### DELETE /modules/{id} — Xóa chặng
Quyền: MENTOR. Response `204`.

### POST /modules/{module_id}/documents — Gán tài liệu từ Kho vào chặng
Quyền: MENTOR.
```json
// Request (gán 1 hoặc nhiều tài liệu, kèm thứ tự)
{ "items": [ { "document_id": 5, "position": 1 }, { "document_id": 8, "position": 2 } ] }
```
Response `201` trả danh sách `module_documents` vừa tạo.

### DELETE /module-documents/{id} — Gỡ một tài liệu khỏi chặng
Quyền: MENTOR. Response `204`. (Xóa liên kết, không xóa tài liệu gốc trong Kho.)

---

## 7. Nhóm API: Gán lộ trình (Assignments) & bulk assign

### POST /roadmaps/{roadmap_id}/assign — Gán lộ trình cho một/nhiều Intern
Quyền: MENTOR.
```json
// Request
{ "user_ids": [12, 15] }
```
```json
// Response 201
{ "created": [ { "assignment_id": 300, "user_id": 12 }, { "assignment_id": 301, "user_id": 15 } ] }
```
Mỗi Intern được tạo một dòng `roadmap_assignments` với `status = IN_PROGRESS`. Nếu Intern đã được gán lộ trình này thì bỏ qua (không tạo trùng).

### POST /roadmaps/{roadmap_id}/assign-group — Gán hàng loạt cho cả nhóm (Bulk)
Quyền: MENTOR.
```json
// Request
{ "group_id": 3 }
```
```json
// Response 201
{ "group_id": 3, "assigned_count": 8, "skipped_existing": 2 }
```
Hệ thống tự map lộ trình cho **toàn bộ Intern đang trong nhóm**, lưu `source_group_id = 3` để biết là gán qua nhóm. Intern nào đã có sẵn thì bỏ qua.

### DELETE /roadmap-assignments/{id} — Hủy gán lộ trình
Quyền: MENTOR. Response `204`.

### GET /roadmap-assignments — Danh sách lượt gán
Quyền: MENTOR (xem tất cả). Query: `?roadmap_id=&user_id=&group_id=&status=&page=&size=`.
```json
// Response 200 (item)
{ "assignment_id": 300, "roadmap_id": 7, "roadmap_title": "Lộ trình Frontend",
  "user_id": 12, "user_name": "Nguyen Van A", "status": "IN_PROGRESS",
  "progress_percent": 40, "assigned_at": "2026-07-10T00:00:00Z" }
```

---

## 8. Nhóm API: Học tập & Tiến độ

### GET /me/roadmaps — Lộ trình được giao cho Intern hiện tại
Quyền: INTERN.
```json
// Response 200 (item)
{ "assignment_id": 300, "roadmap_id": 7, "title": "Lộ trình Frontend",
  "status": "IN_PROGRESS", "progress_percent": 40,
  "completed_lessons": 4, "total_lessons": 10 }
```

### GET /me/roadmaps/{assignment_id} — Chi tiết lộ trình đang học (kèm trạng thái từng bài)
Quyền: INTERN (chỉ assignment của chính mình, nếu không → `403`).
```json
// Response 200
{ "assignment_id": 300, "roadmap_id": 7, "title": "Lộ trình Frontend", "progress_percent": 40,
  "modules": [
    { "id": 20, "title": "Nhập môn", "position": 1,
      "lessons": [
        { "module_document_id": 100, "title": "Git cơ bản", "type": "PDF",
          "content_url": "https://.../git.pdf", "completed": true, "completed_at": "2026-07-12T08:00:00Z" },
        { "module_document_id": 101, "title": "SQL nhập môn", "type": "PDF",
          "content_url": "https://.../sql.pdf", "completed": false, "completed_at": null }
      ] }
  ] }
```

### POST /lessons/{module_document_id}/complete — Đánh dấu hoàn thành bài học
Quyền: INTERN.
```json
// Request
{ "assignment_id": 300 }
```
```json
// Response 200 (trả % cập nhật tức thì để cập nhật progress bar)
{ "module_document_id": 100, "completed": true, "completed_at": "2026-07-12T08:00:00Z",
  "progress_percent": 50 }
```
Tạo/ cập nhật một dòng `lesson_progress`. Khi tất cả bài trong lộ trình `done`, backend tự đặt `roadmap_assignments.status = COMPLETED`.

### DELETE /lessons/{module_document_id}/complete — Bỏ đánh dấu hoàn thành
Quyền: INTERN. Query `?assignment_id=300`. Xóa dòng `lesson_progress`. Response `200` trả `progress_percent` mới.

> Cách tính %: `completed_lessons / total_lessons × 100`, trong đó `total_lessons` = tổng số `module_documents` của lộ trình. Backend tính lại mỗi lần mark/unmark để trả số real-time.

---

## 9. Nhóm API: Dashboard

### GET /dashboard/me — Dashboard của Intern (chỉ dữ liệu bản thân)
Quyền: INTERN.
```json
// Response 200
{ "total_roadmaps": 2, "completed_roadmaps": 0,
  "overall_progress_percent": 45,
  "roadmaps": [ { "assignment_id": 300, "title": "Lộ trình Frontend", "progress_percent": 40 } ] }
```

### GET /dashboard/overview — Dashboard tổng quan (Mentor xem tất cả)
Quyền: MENTOR.
```json
// Response 200
{ "total_interns": 40, "active_assignments": 55, "completed_assignments": 12,
  "by_group": [ { "group_id": 3, "name": "Frontend Khóa 1", "avg_progress_percent": 62 } ] }
```

### GET /dashboard/roadmaps/{roadmap_id} — Tiến độ mọi Intern trong một lộ trình
Quyền: MENTOR.
```json
// Response 200
{ "roadmap_id": 7, "title": "Lộ trình Frontend",
  "interns": [
    { "user_id": 12, "full_name": "Nguyen Van A", "progress_percent": 40, "status": "IN_PROGRESS" },
    { "user_id": 15, "full_name": "Tran Thi B", "progress_percent": 100, "status": "COMPLETED" }
  ] }
```

---

## 10. Nhóm API: Comment

### GET /lessons/{module_document_id}/comments — Danh sách comment của một bài học
Quyền: INTERN/MENTOR. Trả comment gốc kèm reply lồng nhau (theo `parent_comment_id`).
```json
// Response 200
[ { "id": 500, "user": { "id": 12, "full_name": "Nguyen Van A" }, "content": "Bài này hay",
    "created_at": "2026-07-12T09:00:00Z",
    "replies": [ { "id": 501, "user": { "id": 2, "full_name": "Mentor B" }, "content": "Cảm ơn em" } ] } ]
```

### POST /lessons/{module_document_id}/comments — Viết comment (hoặc reply)
Quyền: INTERN/MENTOR.
```json
// Request (reply thì thêm parent_comment_id)
{ "content": "Cho em hỏi...", "parent_comment_id": null }
```
Response `201`.

### PATCH /comments/{id} — Sửa comment của chính mình
Quyền: chủ comment. Response `200`. Người khác sửa → `403`.

### DELETE /comments/{id} — Xóa comment
Quyền: chủ comment hoặc MENTOR. Response `204`.

---

## 11. Bảng tổng hợp toàn bộ endpoint

| Method | Endpoint | Quyền | Chức năng |
|---|---|---|---|
| POST | /auth/register | công khai | Đăng ký Intern |
| POST | /auth/login | công khai | Đăng nhập |
| POST | /auth/refresh | công khai | Làm mới access token |
| POST | /auth/logout | INTERN/MENTOR | Đăng xuất |
| GET | /auth/me | INTERN/MENTOR | Thông tin bản thân |
| PATCH | /auth/me | INTERN/MENTOR | Cập nhật profile |
| POST | /auth/change-password | INTERN/MENTOR | Đổi mật khẩu |
| GET | /users | MENTOR | Liệt kê/tìm kiếm/phân trang |
| POST | /users | ADMIN | Tạo mentor/admin |
| GET | /users/{id} | MENTOR | Chi tiết user |
| PATCH | /users/{id}/lock | MENTOR | Khóa tài khoản |
| PATCH | /users/{id}/unlock | MENTOR | Mở khóa |
| DELETE | /users/{id} | ADMIN | Xóa mềm |
| GET | /groups | MENTOR | Danh sách nhóm |
| POST | /groups | MENTOR | Tạo nhóm |
| GET | /groups/{id} | MENTOR | Chi tiết nhóm + thành viên |
| PATCH | /groups/{id} | MENTOR | Sửa nhóm |
| DELETE | /groups/{id} | MENTOR | Xóa nhóm |
| POST | /groups/{id}/members | MENTOR | Thêm nhiều Intern |
| DELETE | /groups/{id}/members/{user_id} | MENTOR | Kick Intern |
| GET | /documents | INTERN/MENTOR | Danh sách + lọc tag |
| POST | /documents | MENTOR | Tạo tài liệu |
| GET | /documents/{id} | INTERN/MENTOR | Chi tiết |
| PATCH | /documents/{id} | MENTOR | Sửa |
| DELETE | /documents/{id} | MENTOR | Xóa |
| POST | /documents/upload | MENTOR | Upload file |
| GET | /tags | INTERN/MENTOR | Danh sách tag |
| POST | /tags | MENTOR | Tạo tag |
| DELETE | /tags/{id} | MENTOR | Xóa tag |
| GET | /roadmaps | INTERN/MENTOR | Danh sách lộ trình |
| POST | /roadmaps | MENTOR | Tạo lộ trình |
| GET | /roadmaps/{id} | INTERN/MENTOR | Chi tiết + chặng + bài |
| PATCH | /roadmaps/{id} | MENTOR | Sửa |
| DELETE | /roadmaps/{id} | MENTOR | Xóa |
| POST | /roadmaps/{id}/modules | MENTOR | Thêm chặng |
| PATCH | /modules/{id} | MENTOR | Sửa chặng |
| DELETE | /modules/{id} | MENTOR | Xóa chặng |
| POST | /modules/{id}/documents | MENTOR | Gán tài liệu vào chặng |
| DELETE | /module-documents/{id} | MENTOR | Gỡ tài liệu khỏi chặng |
| POST | /roadmaps/{id}/assign | MENTOR | Gán cho Intern |
| POST | /roadmaps/{id}/assign-group | MENTOR | Bulk assign cho nhóm |
| DELETE | /roadmap-assignments/{id} | MENTOR | Hủy gán |
| GET | /roadmap-assignments | MENTOR | Danh sách lượt gán |
| GET | /me/roadmaps | INTERN | Lộ trình được giao |
| GET | /me/roadmaps/{assignment_id} | INTERN | Chi tiết + trạng thái bài |
| POST | /lessons/{module_document_id}/complete | INTERN | Đánh dấu hoàn thành |
| DELETE | /lessons/{module_document_id}/complete | INTERN | Bỏ đánh dấu |
| GET | /dashboard/me | INTERN | Dashboard cá nhân |
| GET | /dashboard/overview | MENTOR | Dashboard tổng quan |
| GET | /dashboard/roadmaps/{id} | MENTOR | Tiến độ theo lộ trình |
| GET | /lessons/{module_document_id}/comments | INTERN/MENTOR | Danh sách comment |
| POST | /lessons/{module_document_id}/comments | INTERN/MENTOR | Viết comment/reply |
| PATCH | /comments/{id} | chủ comment | Sửa comment |
| DELETE | /comments/{id} | chủ comment/MENTOR | Xóa comment |

---

## Ghi chú thực thi cho Backend
- Kiểm tra quyền ở **mọi endpoint** bằng Dependency (ví dụ `require_role(MENTOR)`), không tin frontend.
- Với các API "của tôi" (`/me/...`), luôn kiểm tra tài nguyên thuộc về user trong token, tránh Intern xem được dữ liệu người khác.
- Các thao tác hàng loạt (`assign-group`, thêm nhiều thành viên) nên chạy trong một transaction và bỏ qua bản ghi trùng thay vì báo lỗi.
- Tận dụng Swagger tự sinh tại `/docs` làm bản hợp đồng sống cho Frontend.