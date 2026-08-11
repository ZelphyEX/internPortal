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
11. Nhóm API: Dự án (Projects)
12. Nhóm API: Công việc (Tasks)
13. Nhóm API: Báo cáo hằng ngày (Daily Reports)
14. Bảng tổng hợp toàn bộ endpoint

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
Ràng buộc: `page >= 1`, `size` trong khoảng `1..100` (**mặc định 20**). Gửi `size > 100` → `422`. Giới hạn này được ghi trong `description` của param `size` trên Swagger nên client generate type từ OpenAPI đọc được luôn.

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

> **Đăng nhập bằng Google là đường vào duy nhất của người dùng.** Chỉ email thuộc
> `ALLOWED_EMAIL_DOMAINS` (mặc định `gimasys.com`, `edu.gimasys.com`) được chấp nhận —
> OAuth Consent Screen đặt là "External" nên Google không tự chặn, backend phải chặn.
> **Ai đăng nhập lần đầu cũng được cấp vai trò `INTERN` với trạng thái `ACTIVE`** —
> tên miền email KHÔNG quyết định vai trò. Đường duy nhất lên `MENTOR` là **yêu cầu
> chuyển vai trò** (mục 3b) do ADMIN duyệt.
>
> Form đăng ký **chỉ hỏi họ tên** (điền sẵn từ Google, sửa được). Hồ sơ chi tiết
> (SĐT, trường, ngành, đơn vị, GitHub) do Mentor bổ sung sau qua
> `PATCH /users/{id}/profile`.
>
> **Tuổi thọ phiên: `REFRESH_TOKEN_EXPIRE_DAYS` (mặc định 1 ngày).** Mọi response
> cấp token đều kèm `session_expires_at` (ISO 8601 UTC) — hạn **tuyệt đối** tính từ
> lúc đăng nhập. `/auth/refresh` chỉ cấp access token mới và **không** đẩy mốc này ra
> xa, nên hết ngày là phải đăng nhập lại dù đang thao tác liên tục. Client nên tự
> đăng xuất khi tới mốc đó thay vì đợi 401.

### POST /auth/register — ⛔ ĐÃ TẮT
Quyền: công khai. Luôn trả `403`.
Trước đây endpoint này cho tự đăng ký bằng mật khẩu mà **không xác thực email**, nên
ai cũng tạo được tài khoản mang email của người khác. Tài khoản giờ chỉ sinh ra từ
`POST /auth/google` + `POST /auth/google/complete`.

### POST /auth/google — Đăng nhập bằng Google (bước 1)
Quyền: công khai.
```json
// Request — credential = Google ID token do Google Identity Services trả về
{ "credential": "eyJhbGciOiJSUzI1NiIs..." }
```
```json
// Response 200 — đã có tài khoản
{
  "status": "AUTHENTICATED",
  "tokens": {
    "access_token": "eyJhbGci...", "refresh_token": "d9f3...", "token_type": "bearer",
    "session_expires_at": "2026-08-11T02:00:00Z",
    "user": { "id": 12, "full_name": "Nguyen Van A", "email": "a@edu.gimasys.com",
              "role": "INTERN", "status": "ACTIVE", "avatar_url": "https://..." }
  },
  "profile": null, "signup_ticket": null
}
```
```json
// Response 200 — chưa có tài khoản: client hiện form hồ sơ rồi gọi /auth/google/complete
{
  "status": "NEEDS_REGISTRATION",
  "tokens": null,
  "profile": { "email": "a@edu.gimasys.com", "full_name": "Nguyen Van A",
               "avatar_url": "https://...", "assigned_role": "INTERN",
               "needs_admin_approval": false },
  "signup_ticket": "eyJhbGci..."
}
```
Lỗi: `401` nếu ID token sai/hết hạn; `403` nếu email ngoài tên miền cho phép, email
Google chưa xác thực, tài khoản `LOCKED`, hoặc Mentor chưa được duyệt (detail bắt đầu
bằng `PENDING_APPROVAL`); `503` nếu server chưa cấu hình `GOOGLE_CLIENT_ID`.

### POST /auth/google/complete — Tạo tài khoản (bước 2)
Quyền: công khai, nhưng phải kèm `signup_ticket` do bước 1 cấp (hết hạn sau
`SIGNUP_TICKET_EXPIRE_MINUTES`). **Email lấy từ vé, không lấy từ body** — nên không ai
đăng ký hộ email người khác được. Vai trò cũng do server suy ra, client không gửi lên.
```json
// Request — chỉ cần họ tên
{ "signup_ticket": "eyJhbGci...", "full_name": "Nguyen Van A" }
```
Response `201` cùng shape với `/auth/google`: `AUTHENTICATED` + tokens, vai trò `INTERN`.
(Nhánh `NEEDS_REGISTRATION` + `needs_admin_approval: true` chỉ xảy ra nếu chính sách đổi
sang "tài khoản mới phải chờ duyệt"; luồng hiện tại không dùng.)
Lỗi: `400` vé hết hạn/không hợp lệ; `403` email ngoài tên miền cho phép; `409` email đã
có tài khoản.

### POST /auth/login — Đăng nhập bằng mật khẩu (CHỈ tài khoản ADMIN)
Quyền: công khai, nhưng **403 nếu tài khoản không phải ADMIN**. Intern/Mentor bắt buộc
đi qua Google, nên đường mật khẩu không thể dùng để đi vòng qua xác thực Google.

Tài khoản ADMIN được `scripts/ensure_admin.py` tạo/đồng bộ mỗi lần container khởi động
theo `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD` (xem Dockerfile `CMD`). Đây là
đường vào không phụ thuộc Google — bắt buộc phải có, vì Mentor mới cần ADMIN duyệt.
Đổi mật khẩu admin = đổi biến môi trường rồi deploy lại.
```json
// Request
{ "email": "admin@gimasys.com", "password": "matkhau123" }
```
```json
// Response 200
{
  "access_token": "eyJhbGci...",
  "refresh_token": "d9f3...",
  "token_type": "bearer",
  "session_expires_at": "2026-08-11T02:00:00Z",
  "user": { "id": 1, "full_name": "Quản trị viên Gimasys", "email": "admin@gimasys.com",
            "role": "ADMIN", "status": "ACTIVE", "avatar_url": null }
}
```
Lỗi: `401` sai email/mật khẩu; `403` nếu không phải ADMIN, tài khoản `LOCKED`, hoặc
email ngoài tên miền cho phép.

### POST /auth/refresh — Làm mới access token
Quyền: công khai (dùng refresh token). Chỉ cấp access token mới; **không** gia hạn
phiên — refresh token hết hạn (`session_expires_at`) là phải đăng nhập lại.
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

### Hồ sơ Intern (profile) — các field dùng chung
Mọi response user của nhóm này (`GET /users`, `GET /users/{id}`, `POST /users`, lock/unlock, `PATCH /users/{id}/profile`) đều trả **cùng một bộ field**. Tất cả field hồ sơ đều **nullable** và chỉ có ý nghĩa với `role=INTERN`:

| Field | Kiểu | Ghi chú |
|---|---|---|
| `department` | enum \| null | `Java Back-End` \| `React Front-End` \| `Cloud & DevOps` \| `Salesforce/ERP` \| `AI & Data Science` |
| `bio` | string \| null | |
| `github_url` | string \| null | |
| `score`, `attendance_rate` | number (0..100) \| null | Điểm đánh giá / tỉ lệ chuyên cần (%) |

> **Đã bỏ khỏi bảng `users`** (không còn trả về, gửi lên cũng bị bỏ qua):
> `mentor_id` / `mentor_name` / `mentor_email` / `phone` / `start_date` / `end_date` /
> `university` (migration `d5c8a2e64f19`) và `major` (migration `e7a4b1d09c53`).
> Các trường này không còn hiển thị ở đâu trong portal.

### GET /users — Liệt kê, tìm kiếm, phân trang Intern
Quyền: MENTOR.
Query: `?page=1&size=20&search=<tên hoặc email>&role=INTERN&status=ACTIVE`
```json
// Response 200 (dạng phân trang)
{ "items": [
    { "id": 12, "full_name": "Nguyen Van A", "email": "a@example.com",
      "role": "INTERN", "status": "ACTIVE", "avatar_url": null,
      "department": "React Front-End", "bio": "TTS FE",
      "github_url": "https://github.com/a", "score": 8.5, "attendance_rate": 96.5 }
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
Quyền: MENTOR. Response `200` trả thông tin user (kèm toàn bộ field hồ sơ ở trên).

### PATCH /users/{id}/profile — Cập nhật hồ sơ Intern
Quyền: MENTOR. Chỉ sửa các field hồ sơ; **không** đổi `full_name`/`email`/`role`/`status` qua đây (tự sửa tên/ảnh của chính mình thì dùng `PATCH /auth/me`).
```json
// Request — gửi field nào sửa field đó
{ "department": "React Front-End", "bio": "TTS FE",
  "github_url": "https://github.com/a", "score": 8.5, "attendance_rate": 96.5 }
```
Response `200` trả user sau khi cập nhật.
- Gửi `null` tường minh = **xóa** giá trị field đó (ví dụ `{"department": null}`).
- Lỗi `422`: `score`/`attendance_rate` ngoài khoảng 0..100.

### PATCH /users/{id}/lock — Khóa tài khoản
Quyền: MENTOR. Đặt `status = LOCKED`. Response `200`.

### PATCH /users/{id}/unlock — Mở khóa
Quyền: MENTOR. Đặt `status = ACTIVE`. Response `200`.

### DELETE /users/{id} — Xóa mềm (soft delete)
Quyền: ADMIN. Đặt `deleted_at`, không xóa khỏi DB. Response `204`.

---

## 3b. Nhóm API: Yêu cầu chuyển vai trò (Intern ↔ Mentor)

Vai trò được cấp theo tên miền email lúc đăng ký, nên đây là cách duy nhất để đổi
vai trò về sau. Bảng `role_change_requests` có **unique index có điều kiện** trên
`user_id WHERE status='PENDING'` → mỗi người tối đa một yêu cầu đang chờ.

Luật:
- **INTERN → MENTOR** (nâng quyền): tạo yêu cầu `PENDING`, chờ ADMIN duyệt. Người gửi
  tự rút lại được khi chưa duyệt.
- **MENTOR → INTERN** (hạ quyền): áp dụng **ngay**, không cần duyệt (`applied: true`),
  vẫn ghi một dòng `APPROVED` để có vết lịch sử. Client phải gọi lại `GET /auth/me`.
- **ADMIN**: không dùng cơ chế này (`400`).

### GET /role-requests/me — Yêu cầu đang chờ của mình
Quyền: INTERN/MENTOR. Trả `null` nếu không có.
```json
// Response 200
{ "id": 5, "user_id": 12, "user_name": "Nguyen Van A", "user_email": "a@edu.gimasys.com",
  "from_role": "INTERN", "to_role": "MENTOR", "status": "PENDING",
  "created_at": "2026-08-10T02:00:00Z", "decided_at": null, "applied": false }
```

### POST /role-requests — Gửi yêu cầu
Quyền: INTERN/MENTOR.
```json
// Request
{ "to_role": "MENTOR" }
```
Response `201` (shape như trên). Lỗi: `400` nếu là ADMIN hoặc đã ở đúng vai trò đó;
`409` nếu đang có yêu cầu chờ duyệt.

### DELETE /role-requests/me — Rút lại yêu cầu
Quyền: INTERN/MENTOR. Đặt `status = CANCELLED`. Response `204`, `404` nếu không có
yêu cầu nào đang chờ.

### GET /role-requests — Hàng đợi
Quyền: ADMIN. Query `?status=PENDING&page=&size=`. Sắp xếp `id` tăng dần (ai gửi
trước xếp trước); duyệt xong thì yêu cầu đó rời hàng đợi.

### PATCH /role-requests/{id}/approve — Duyệt
Quyền: ADMIN. Đổi `users.role` của người gửi sang `to_role` ngay. Response `200` với
`applied: true`. Lỗi: `400` nếu yêu cầu đã xử lý, `404` nếu không tồn tại.

### PATCH /role-requests/{id}/reject — Từ chối
Quyền: ADMIN. `status = REJECTED`, vai trò giữ nguyên. Người dùng gửi lại được sau.

---

## 3c. Nhóm API: Điểm thi thử Anthropic Mock Exam

Đề thi là dữ liệu **tĩnh trong bundle frontend** (`src/data/CF.tests/`), server không
có đáp án nên không tự chấm lại được. Client gửi số câu đúng, **server tự tính điểm**
(client không gửi `score`).

**Cách tính điểm** (`app/services/exam_service.py` — nguồn duy nhất):
- Thang chuẩn hoá **100 – 1000**: `score = round(100 + correct/total * 900)`.
- Đỗ: **>= 720**.
- Đề: 60 câu trắc nghiệm (một hoặc nhiều đáp án), 120 phút. Câu đúng phải khớp
  **chính xác** tập đáp án đúng.
- ⚠️ Đặc tả nói tính theo "độ khó và trọng số từng câu" nhưng dữ liệu đề hiện tại
  KHÔNG có trường độ khó/trọng số — mọi câu đang tính như nhau. Khi đề bổ sung trường
  đó chỉ cần sửa `scaled_score()`.

Chỉ bài làm ở **chế độ thi** mới được nộp; chế độ luyện tập không ghi nhận.
"Điểm của một đề" = điểm **cao nhất** trong các lần làm đề đó.

### POST /exam-attempts — Nộp kết quả một lần thi
Quyền: INTERN/MENTOR.
```json
// Request
{ "exam_id": "claude-dev-1", "exam_title": "Claude Developer — Practice Exam 1",
  "exam_code": "Claude Developer", "total_questions": 60, "correct_count": 45,
  "duration_seconds": 5400 }
```
```json
// Response 201
{ "id": 9, "user_id": 12, "exam_id": "claude-dev-1", "exam_title": "...",
  "exam_code": "Claude Developer", "total_questions": 60, "correct_count": 45,
  "score": 775, "passed": true, "duration_seconds": 5400,
  "created_at": "2026-08-11T03:00:00Z" }
```
Lỗi: `400` nếu `correct_count > total_questions`.

### GET /exam-attempts/me — Lịch sử làm bài của mình
Quyền: INTERN/MENTOR. Phân trang, mới nhất trước.

### GET /exam-attempts/me/summary — Điểm tổng hợp của mình
Quyền: INTERN/MENTOR. `avg_score` = trung bình điểm **tốt nhất mỗi đề** (làm lại nhiều
lần không kéo trung bình xuống), `null` nếu chưa thi bài nào.
```json
// Response 200
{ "user_id": 12, "full_name": "Nguyen Van A", "email": "a@edu.gimasys.com",
  "avg_score": 812.5, "best_score": 900, "exams_taken": 4, "exams_passed": 3,
  "attempts_count": 7,
  "per_exam": [
    { "exam_id": "claude-dev-1", "exam_title": "...", "exam_code": "Claude Developer",
      "best_score": 900, "passed": true, "attempts": 2,
      "last_taken_at": "2026-08-11T03:00:00Z" }
  ] }
```

### GET /exam-attempts/overview — Điểm TB toàn bộ Thực tập sinh
Quyền: MENTOR. Dùng cho thẻ "Điểm Năng lực TB" ở Dashboard của Mentor.
`avg_score` là trung bình `avg_score` của các Intern **đã thi ít nhất 1 bài** — người
chưa thi không bị tính 0 điểm.
```json
// Response 200
{ "avg_score": 764.2, "interns_with_attempts": 5, "interns_total": 8,
  "interns": [ { "user_id": 12, "full_name": "...", "avg_score": 812.5, "...": "..." } ] }
```

### GET /users/{id}/exam-attempts — Lịch sử làm bài của một người
Quyền: MENTOR. Phân trang. 404 nếu user không tồn tại.

### GET /users/{id}/exam-attempts/summary — Điểm từng đề của một người
Quyền: MENTOR. Cùng shape với `/exam-attempts/me/summary`.

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

> **GÁN NHÓM LÀ LUẬT THƯỜNG TRỰC, KHÔNG PHẢI CHÉP MỘT LẦN.**
> `roadmap_assignments.source_group_id` và `project_members.source_group_id` ghi lại
> "người này có lộ trình/dự án **vì** thuộc nhóm X". Nhờ đó:
> * ai vào nhóm **sau** vẫn nhận được mọi lộ trình + dự án của nhóm;
> * rời nhóm chỉ thu hồi đúng phần đến từ nhóm, và **chỉ khi chưa động vào**.
>
> Trước đây `POST /roadmaps/{id}/assign-group` chỉ chép cho những ai có mặt lúc bấm
> gán, nên người vào nhóm sau không nhận được lộ trình nào — đó là lỗi đã sửa.

### POST /groups/{id}/members — Thêm nhiều Intern vào nhóm
Quyền: MENTOR. Chạy trong 1 transaction. Bỏ qua id không tồn tại và người đã ở trong
nhóm. Người mới **tự động kế thừa** mọi lộ trình + dự án đang gán cho nhóm.
```json
// Request (thêm hàng loạt)
{ "user_ids": [12, 15, 18] }
```
```json
// Response 200
{ "members": [ { "id": 12, "full_name": "...", "email": "..." } ],
  "added_count": 3, "skipped_existing": 0,
  "inherited_roadmaps": 6, "inherited_projects": 3 }
```
(Một Intern có thể thuộc nhiều nhóm — không báo lỗi nếu đã ở nhóm khác; chỉ chống
trùng trong cùng nhóm.)

### DELETE /groups/{id}/members/{user_id} — Kick một Intern khỏi nhóm
Quyền: MENTOR. Response `200`.

Chỉ thu hồi lộ trình/dự án người đó có **vì thuộc nhóm này**, và **chỉ khi chưa có
tiến độ**: đã hoàn thành bài học nào (lộ trình) hoặc đang được giao task (dự án) thì
GIỮ LẠI và chuyển thành gán cá nhân (`source_group_id = NULL`). Rời nhóm không được
phép xoá công sức đã bỏ ra. Lộ trình/dự án gán lẻ từ đầu thì không bị đụng tới.
```json
// Response 200
{ "revoked_roadmaps": 2, "kept_roadmaps": 1, "revoked_projects": 1, "kept_projects": 0 }
```

---

## 5. Nhóm API: Tài liệu (Documents) & Tags

> **Metadata Thư viện Tài liệu** (migration `a92f4c17be60`): `category`, `file_type`,
> `file_size_bytes`. Ba trường này BẮT BUỘC phải gửi khi tạo tài liệu, nếu không tải
> lại trang là mất — `type` (chỉ 4 giá trị) không biểu diễn được định dạng thật mà
> giao diện hiển thị (`PDF`/`DOCX`/`SLIDE`/`MD`: DOCX và MD đều dồn về `ARTICLE`), và
> danh mục/dung lượng thì trước đây không có chỗ lưu nào cả. Cả ba đều nullable nên
> tài liệu tạo trước migration vẫn đọc được (client suy ngược từ `type`).

### GET /documents — Danh sách tài liệu (lọc theo tag, tìm kiếm, phân trang)
Quyền: INTERN (chỉ xem) / MENTOR.
Query: `?page=1&size=20&search=<tiêu đề>&tag=git&type=PDF`
```json
// Response 200 (item)
{ "id": 5, "title": "Git cơ bản", "description": "...", "content_url": "https://.../git.pdf",
  "type": "PDF", "category": "Coding Standard", "file_type": "PDF",
  "file_size_bytes": 865280, "tags": ["git", "cơ bản"],
  "created_at": "2026-07-01T00:00:00Z" }
```

### POST /documents — Tạo tài liệu mới
Quyền: MENTOR.
```json
// Request — `tag_names` tiện hơn `tag_ids`: tag chưa có thì server tự tạo
{ "title": "Git cơ bản", "description": "Bài mở đầu", "content_url": "https://.../git.pdf",
  "type": "PDF", "category": "Coding Standard", "file_type": "PDF",
  "file_size_bytes": 865280, "tag_names": ["git", "cơ bản"] }
```
Response `201`. (`type`: `VIDEO` | `PDF` | `LINK` | `ARTICLE`;
`file_type`: `PDF` | `DOCX` | `SLIDE` | `MD`.)

Danh mục frontend đang dùng: `CCA-F Certificate`, `Coding Standard`, `Onboarding`,
`Architecture`, `Template`, `AI`. Cột `category` là chuỗi tự do nên thêm danh mục mới
chỉ cần sửa `DOC_CATEGORIES` ở `KnowledgeBaseView.tsx`, không phải migration.

### GET /documents/{id} — Chi tiết tài liệu
Quyền: INTERN/MENTOR. Response `200`.

### PATCH /documents/{id} — Sửa tài liệu
Quyền: MENTOR. Gửi `tag_ids` hoặc `tag_names` (kể cả `[]`) để gán lại toàn bộ tags.
Response `200`.

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
      "track": "React Front-End", "week_number": 1,
      "duration_text": "2 tuần", "key_skills": ["React", "TypeScript"],
      "documents": [
        { "module_document_id": 100, "document_id": 5, "title": "Git cơ bản", "type": "PDF", "position": 1 }
      ] }
  ] }
```
> Lưu ý: bài học trong chặng được tham chiếu bằng `module_document_id` — đây là ID dùng cho việc đánh dấu hoàn thành và comment.

**Metadata của chặng (course card):** `track` (enum `department`, nullable), `week_number` (int ≥ 1, nullable), `duration_text` (string tự do, ví dụ `"2 tuần"`, nullable), `key_skills` (mảng string, mặc định `[]`). Có ở cả `POST /roadmaps/{id}/modules`, `PATCH /modules/{id}`, `GET /roadmaps/{id}` và `GET /me/roadmaps/{assignment_id}`. Gửi `key_skills` (kể cả `[]`) là **thay toàn bộ** danh sách; `null` được hiểu là `[]`.

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
      "track": "React Front-End", "week_number": 1,
      "duration_text": "2 tuần", "key_skills": ["React", "TypeScript"],
      "lessons": [
        { "module_document_id": 100, "title": "Git cơ bản", "type": "PDF",
          "content_url": "https://.../git.pdf", "completed": true, "completed_at": "2026-07-12T08:00:00Z" },
        { "module_document_id": 101, "title": "SQL nhập môn", "type": "PDF",
          "content_url": "https://.../sql.pdf", "completed": false, "completed_at": null }
      ] }
  ] }
```

### GET /users/{user_id}/roadmaps — Lộ trình của MỘT người (Mentor xem)
Quyền: MENTOR. Cùng shape với `GET /me/roadmaps`. `404` nếu user không tồn tại.
Dùng ở màn hồ sơ chi tiết Thực tập sinh (khối "Chi tiết Lộ trình Đào tạo").

### GET /users/{user_id}/roadmaps/{assignment_id} — Đã học xong bài nào (Mentor xem)
Quyền: MENTOR. Cùng shape với `GET /me/roadmaps/{assignment_id}` — từng chặng, từng
bài học, `completed` + `completed_at`.
`403` nếu `assignment_id` không thuộc `user_id` (dùng chung hàm kiểm tra sở hữu với
endpoint `/me/...`, nên không lộ được lượt gán của người khác); `404` nếu user hoặc
lượt gán không tồn tại.

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
  "task_completion_percent": 60,
  "pending_reports_count": 1,
  "roadmaps": [ { "assignment_id": 300, "title": "Lộ trình Frontend", "progress_percent": 40 } ] }
```
- `task_completion_percent`: `tasks` có `status = Done` / tổng số task được gán cho chính user (0 nếu chưa có task nào).
- `pending_reports_count`: số `daily_reports` của chính user đang ở `status = Pending` (chờ mentor duyệt).

### GET /dashboard/overview — Dashboard tổng quan (Mentor xem tất cả)
Quyền: MENTOR.
```json
// Response 200
{ "total_interns": 40, "active_assignments": 55, "completed_assignments": 12,
  "avg_score": 8.12, "completed_tasks_this_week": 17, "pending_reviews_count": 5,
  "by_group": [ { "group_id": 3, "name": "Frontend Khóa 1", "avg_progress_percent": 62 } ] }
```
- `avg_score`: trung bình `users.score` của các Intern chưa xóa **và đã có điểm** (trả `0` nếu chưa ai có điểm).
- `completed_tasks_this_week`: số task chuyển sang `Done` kể từ **thứ Hai 00:00 UTC** của tuần hiện tại (dựa trên `tasks.completed_at`).
- `pending_reviews_count`: tổng số `daily_reports` đang `Pending` (của mọi Intern).

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
    "code_snippet": "const a = 1;", "is_resolved": false,
    "created_at": "2026-07-12T09:00:00Z",
    "replies": [ { "id": 501, "user": { "id": 2, "full_name": "Mentor B" }, "content": "Cảm ơn em",
                   "code_snippet": null, "is_resolved": false } ] } ]
```
- `code_snippet` (string \| null): đoạn code đính kèm khi hỏi/thảo luận.
- `is_resolved` (bool, mặc định `false`): chỉ MENTOR đổi được, qua endpoint riêng bên dưới.

### POST /lessons/{module_document_id}/comments — Viết comment (hoặc reply)
Quyền: INTERN/MENTOR.
```json
// Request (reply thì thêm parent_comment_id)
{ "content": "Cho em hỏi...", "code_snippet": "const a = 1;", "parent_comment_id": null }
```
Response `201`.

### PATCH /comments/{id} — Sửa comment của chính mình
Quyền: chủ comment. Body: `{ "content": "...", "code_snippet": "..." }` (gửi `code_snippet: null` để bỏ đoạn code). Response `200`. Người khác sửa → `403`.

### PATCH /comments/{id}/resolve — Đánh dấu đã giải quyết
Quyền: MENTOR (khác với quyền sửa nội dung — đó là của chủ comment).
```json
// Request (body không bắt buộc; mặc định là resolve)
{ "is_resolved": true }
```
Response `200` trả comment sau khi cập nhật. Gửi `{"is_resolved": false}` để mở lại. INTERN gọi → `403`.

### DELETE /comments/{id} — Xóa comment
Quyền: chủ comment hoặc MENTOR. Response `204`.

---

## 11. Nhóm API: Dự án (Projects)

> Quy tắc xem: MENTOR/ADMIN thấy mọi dự án. **INTERN chỉ thấy dự án mình là `lead_user_id` hoặc là thành viên** — kể cả khi truyền filter khác (CLAUDE.md mục 6). Ghi (tạo/sửa/xóa/thêm-kick thành viên): MENTOR.

### GET /projects — Danh sách dự án
Quyền: INTERN (chỉ dự án của mình) / MENTOR (tất cả).
Query: `?page=1&size=20&search=<title hoặc code>&department=React Front-End&status=Active&member_id=12`
```json
// Response 200 (item)
{ "id": 4, "code": "PRJ-001", "title": "Intern Portal", "department": "React Front-End",
  "status": "Active", "lead_user_id": 2, "lead_name": "Mentor B", "progress_percent": 55,
  "deadline": "2026-09-30", "description": "...", "tags": ["react"],
  "member_count": 3, "created_at": "2026-07-20T00:00:00Z" }
```
- `status`: `In Planning` | `Active` | `Under Review` | `Completed`.
- `progress_percent` (0..100) do Mentor tự cập nhật, **không** tự suy ra từ tasks (số theo task xem `task_completion_percent` ở mục 9).
- `tags` dùng chung bảng `tags` với Documents (gửi `tag_ids` khi ghi, đọc ra là danh sách tên).

### POST /projects — Tạo dự án
Quyền: MENTOR.
```json
// Request
{ "code": "PRJ-001", "title": "Intern Portal", "department": "React Front-End",
  "status": "Active", "lead_user_id": 2, "progress_percent": 0, "deadline": "2026-09-30",
  "description": "...", "tag_ids": [1], "member_ids": [12, 15] }
```
Response `201` (dạng chi tiết, kèm `members`). Lỗi: `409` nếu `code` đã tồn tại; `400` nếu `lead_user_id` không tồn tại. `member_ids` bỏ qua id không tồn tại / trùng.

### GET /projects/{id} — Chi tiết dự án (kèm thành viên)
Quyền: INTERN (phải là lead/thành viên, nếu không → `403`) / MENTOR.
```json
// Response 200
{ "id": 4, "code": "PRJ-001", "title": "Intern Portal", "...": "...",
  "members": [ { "id": 12, "full_name": "Nguyen Van A", "email": "a@example.com", "avatar_url": null } ] }
```

### PATCH /projects/{id} — Sửa dự án
Quyền: MENTOR. Gửi field nào sửa field đó; `tag_ids` xuất hiện (kể cả `[]`) là gán lại toàn bộ tags. Response `200` (dạng chi tiết). Lỗi `409` nếu đổi sang `code` đã có.

### DELETE /projects/{id} — Xóa dự án
Quyền: MENTOR. **Xóa mềm** (đặt `deleted_at`) vì `tasks` còn tham chiếu tới dự án. Sau khi xóa: không còn trong danh sách, `GET /projects/{id}` trả `404`. Response `204`.

### POST /projects/{id}/members — Thêm nhiều thành viên
Quyền: MENTOR. Chạy trong 1 transaction, bỏ qua người đã ở trong dự án và id không tồn tại.
```json
{ "user_ids": [12, 15, 18] }
```
Response `200` trả danh sách thành viên hiện tại.

### POST /projects/{id}/members/group — Gán cả một NHÓM vào dự án
Quyền: MENTOR. Đối xứng với `POST /roadmaps/{id}/assign-group`. Ghi
`project_members.source_group_id` nên **ai vào nhóm sau này cũng tự vào dự án**.
```json
// Request
{ "group_id": 3 }
```
```json
// Response 200
{ "added_count": 5, "skipped_existing": 1 }
```
`404` nếu dự án hoặc nhóm không tồn tại.

### DELETE /projects/{id}/members/{user_id} — Kick thành viên
Quyền: MENTOR. Response `204`; `404` nếu user không phải thành viên.

---

## 12. Nhóm API: Công việc (Tasks)

> Quy tắc xem: MENTOR/ADMIN thấy mọi task. **INTERN chỉ thấy task được gán cho mình** (`assigned_intern_id`), kể cả khi truyền `assigned_intern_id` khác.

### GET /tasks — Danh sách công việc
Quyền: INTERN (task của mình) / MENTOR (tất cả).
Query: `?page=1&size=20&project_id=4&assigned_intern_id=12&status=In Progress&priority=High`
```json
// Response 200 (item)
{ "id": 90, "title": "Làm trang login", "project_id": 4, "project_code": "PRJ-001",
  "project_title": "Intern Portal", "assigned_intern_id": 12,
  "assigned_intern_name": "Nguyen Van A", "mentor_id": 2, "mentor_name": "Mentor B",
  "status": "In Progress", "priority": "High", "due_date": "2026-08-01",
  "description": "...", "pr_url": null, "mentor_feedback": null,
  "completed_at": null, "created_at": "2026-07-21T00:00:00Z", "updated_at": "2026-07-21T00:00:00Z" }
```
- `status`: `To Do` | `In Progress` | `In Review` | `Done` | `Blocked` (mặc định `To Do`).
- `priority`: `Low` | `Medium` | `High` | `Urgent` (mặc định `Medium`).
- `completed_at` do backend tự quản: chuyển sang `Done` → set thời điểm hiện tại; rời `Done` → về `null`.

### POST /tasks — Tạo công việc
Quyền: MENTOR.
```json
// Request
{ "title": "Làm trang login", "project_id": 4, "assigned_intern_id": 12,
  "priority": "High", "due_date": "2026-08-01", "description": "..." }
```
Response `201`. `mentor_id` mặc định là người gọi. `project_id` để `null` được (task ngoài dự án). Lỗi `400` nếu `project_id`/`assigned_intern_id`/`mentor_id` không tồn tại.

### GET /tasks/{id} — Chi tiết công việc
Quyền: INTERN (task của mình, nếu không → `403`) / MENTOR.

### PATCH /tasks/{id} — Cập nhật công việc
Quyền: MENTOR (mọi field) / INTERN (**chỉ `status` và `pr_url`**, và chỉ trên task của mình).
```json
// Intern kéo task trên Kanban + nộp PR
{ "status": "In Review", "pr_url": "https://github.com/org/repo/pull/12" }
```
```json
// Mentor nhận xét
{ "status": "Done", "mentor_feedback": "Code ổn, merge được" }
```
Response `200`. Intern gửi field khác (ví dụ `mentor_feedback`, `assigned_intern_id`) → `403` kèm danh sách field bị từ chối.

### DELETE /tasks/{id} — Xóa công việc
Quyền: MENTOR. Response `204`. (Xóa vật lý — task không phải dữ liệu cần lưu vết như user/document.)

---

## 13. Nhóm API: Báo cáo hằng ngày (Daily Reports)

> Quy tắc xem: MENTOR/ADMIN thấy mọi báo cáo. **INTERN chỉ thấy báo cáo của mình.** Người tạo báo cáo **luôn** là user trong token — không nhận `intern_id` từ body. Mỗi Intern chỉ có 1 báo cáo / 1 ngày (`UNIQUE(intern_id, date)`).

### GET /daily-reports — Danh sách báo cáo
Quyền: INTERN (của mình) / MENTOR (tất cả).
Query: `?page=1&size=20&intern_id=12&date_from=2026-07-01&date_to=2026-07-31&status=Pending`
```json
// Response 200 (item)
{ "id": 30, "intern_id": 12, "intern_name": "Nguyen Van A", "date": "2026-07-26",
  "completed_today": "Xong trang login", "tomorrow_plan": "Làm trang register",
  "blockers": null, "hours_logged": 7.5, "status": "Pending",
  "mentor_comment": null, "rating": null, "reviewed_by": null, "reviewer_name": null,
  "reviewed_at": null, "created_at": "2026-07-26T10:00:00Z", "updated_at": "2026-07-26T10:00:00Z" }
```
`status`: `Pending` | `Approved` | `Needs Revision`.

### POST /daily-reports — Intern tự tạo báo cáo
Quyền: INTERN/MENTOR (báo cáo thuộc về người gọi).
```json
// Request
{ "date": "2026-07-26", "completed_today": "Xong trang login",
  "tomorrow_plan": "Làm trang register", "blockers": null, "hours_logged": 7.5 }
```
Response `201` với `status = Pending`. Lỗi: `409` nếu đã có báo cáo cho ngày đó; `422` nếu `hours_logged` ngoài 0..24.

### GET /daily-reports/{id} — Chi tiết báo cáo
Quyền: chủ báo cáo hoặc MENTOR (Intern xem của người khác → `403`).

### PATCH /daily-reports/{id} — Sửa báo cáo của chính mình
Quyền: **chủ báo cáo** (người khác → `403`). Dùng khi mentor trả về `Needs Revision`.
```json
{ "completed_today": "Xong trang login + validate", "hours_logged": 8 }
```
Response `200`. Báo cáo đang `Needs Revision` sẽ **tự quay về `Pending`** sau khi sửa. Lỗi `400` nếu báo cáo đã `Approved` (đóng băng), `409` nếu đổi `date` sang ngày đã có báo cáo khác.

### PATCH /daily-reports/{id}/review — Mentor duyệt
Quyền: MENTOR.
```json
// Request
{ "status": "Needs Revision", "mentor_comment": "Thiếu phần blockers", "rating": 3 }
```
Response `200` (ghi nhận `reviewed_by`, `reviewer_name`, `reviewed_at`). Lỗi: `400` nếu `status = Pending` (review phải là `Approved` hoặc `Needs Revision`); `422` nếu `rating` ngoài 1..5.

---

## 14. Bảng tổng hợp toàn bộ endpoint

| Method | Endpoint | Quyền | Chức năng |
|---|---|---|---|
| POST | /auth/register | công khai | ⛔ đã tắt (luôn 403) |
| POST | /auth/google | công khai | Đăng nhập bằng Google (bước 1) |
| POST | /auth/google/complete | công khai + signup_ticket | Tạo tài khoản (bước 2) |
| POST | /auth/login | công khai (chỉ ADMIN qua được) | Đăng nhập bằng mật khẩu |
| POST | /auth/refresh | công khai | Làm mới access token |
| POST | /auth/logout | INTERN/MENTOR | Đăng xuất |
| GET | /auth/me | INTERN/MENTOR | Thông tin bản thân |
| PATCH | /auth/me | INTERN/MENTOR | Cập nhật profile |
| POST | /auth/change-password | INTERN/MENTOR | Đổi mật khẩu |
| GET | /users | MENTOR | Liệt kê/tìm kiếm/phân trang |
| POST | /users | ADMIN | Tạo mentor/admin |
| GET | /users/{id} | MENTOR | Chi tiết user |
| PATCH | /users/{id}/profile | MENTOR | Cập nhật hồ sơ Intern |
| PATCH | /users/{id}/lock | MENTOR | Khóa tài khoản |
| PATCH | /users/{id}/unlock | MENTOR | Mở khóa |
| PATCH | /users/{id}/approve | ADMIN | Duyệt tài khoản Mentor chờ duyệt |
| DELETE | /users/{id} | ADMIN | Xóa mềm |
| GET | /role-requests/me | INTERN/MENTOR | Yêu cầu chuyển vai trò của mình |
| POST | /role-requests | INTERN/MENTOR | Gửi yêu cầu chuyển vai trò |
| DELETE | /role-requests/me | INTERN/MENTOR | Rút lại yêu cầu chưa duyệt |
| GET | /role-requests | ADMIN | Hàng đợi yêu cầu chuyển vai trò |
| PATCH | /role-requests/{id}/approve | ADMIN | Duyệt (đổi vai trò ngay) |
| PATCH | /role-requests/{id}/reject | ADMIN | Từ chối (giữ nguyên vai trò) |
| POST | /exam-attempts | INTERN/MENTOR | Nộp kết quả một lần thi thử |
| GET | /exam-attempts/me | INTERN/MENTOR | Lịch sử làm bài của mình |
| GET | /exam-attempts/me/summary | INTERN/MENTOR | Điểm TB + điểm từng đề của mình |
| GET | /exam-attempts/overview | MENTOR | Điểm TB toàn bộ Thực tập sinh |
| GET | /users/{id}/roadmaps | MENTOR | Lộ trình + tiến độ của một người |
| GET | /users/{id}/roadmaps/{assignment_id} | MENTOR | Người đó đã học xong bài nào |
| GET | /users/{id}/exam-attempts | MENTOR | Lịch sử làm bài của một người |
| GET | /users/{id}/exam-attempts/summary | MENTOR | Điểm từng đề của một người |
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
| PATCH | /comments/{id}/resolve | MENTOR | Đánh dấu đã giải quyết |
| DELETE | /comments/{id} | chủ comment/MENTOR | Xóa comment |
| GET | /projects | INTERN (của mình)/MENTOR | Danh sách dự án |
| POST | /projects | MENTOR | Tạo dự án |
| GET | /projects/{id} | thành viên/MENTOR | Chi tiết + thành viên |
| PATCH | /projects/{id} | MENTOR | Sửa dự án |
| DELETE | /projects/{id} | MENTOR | Xóa mềm dự án |
| POST | /projects/{id}/members | MENTOR | Thêm nhiều thành viên |
| POST | /projects/{id}/members/group | MENTOR | Gán cả một nhóm vào dự án |
| DELETE | /projects/{id}/members/{user_id} | MENTOR | Kick thành viên |
| GET | /tasks | INTERN (của mình)/MENTOR | Danh sách công việc |
| POST | /tasks | MENTOR | Tạo công việc |
| GET | /tasks/{id} | người được gán/MENTOR | Chi tiết công việc |
| PATCH | /tasks/{id} | MENTOR (mọi field) / INTERN (status, pr_url) | Cập nhật công việc |
| DELETE | /tasks/{id} | MENTOR | Xóa công việc |
| GET | /daily-reports | INTERN (của mình)/MENTOR | Danh sách báo cáo |
| POST | /daily-reports | INTERN/MENTOR | Tạo báo cáo hằng ngày |
| GET | /daily-reports/{id} | chủ báo cáo/MENTOR | Chi tiết báo cáo |
| PATCH | /daily-reports/{id} | chủ báo cáo | Sửa báo cáo của mình |
| PATCH | /daily-reports/{id}/review | MENTOR | Duyệt báo cáo |

---

## Ghi chú thực thi cho Backend
- Kiểm tra quyền ở **mọi endpoint** bằng Dependency (ví dụ `require_role(MENTOR)`), không tin frontend.
- Với các API "của tôi" (`/me/...`), luôn kiểm tra tài nguyên thuộc về user trong token, tránh Intern xem được dữ liệu người khác.
- Các thao tác hàng loạt (`assign-group`, thêm nhiều thành viên) nên chạy trong một transaction và bỏ qua bản ghi trùng thay vì báo lỗi.
- Tận dụng Swagger tự sinh tại `/docs` làm bản hợp đồng sống cho Frontend.