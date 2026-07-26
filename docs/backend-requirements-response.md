# Phản hồi yêu cầu của Frontend — đã triển khai

Trả lời cho `docs/backend-requirements.md`. Trạng thái: **mục 1, 2, 3, 4, 6, 7, 8 đã xong**; mục 5 xong phần "tối thiểu", phần mở rộng kiến trúc vẫn chờ họp.

Chi tiết request/response đầy đủ: `docs/API_SPEC.md` (mục 3, 6, 9, 10, 11, 12, 13) và Swagger `/docs`. Migration: `alembic/versions/20260726_1321_..._1a20809b9ce9.py` (đã `upgrade head` trên DB dev).

---

## Tóm tắt theo từng mục

| Mục | Nội dung | Trạng thái |
|---|---|---|
| 1 | Field hồ sơ Intern trên `users` | ✅ Xong — thêm cả list + detail, sửa qua `PATCH /users/{id}/profile` |
| 2 | Resource `Projects` | ✅ Xong — 7 endpoint |
| 3 | Resource `Tasks` | ✅ Xong — 5 endpoint (thêm `GET /tasks/{id}`) |
| 4 | Resource `Daily Reports` | ✅ Xong — 5 endpoint (thêm `GET`/`PATCH` cho chủ báo cáo) |
| 5 | Metadata `Module` | ✅ Xong 4 field đề xuất. ⏸ "major task → section": chưa làm, cần họp |
| 6 | `code_snippet`, `is_resolved` cho comment | ✅ Xong + `PATCH /comments/{id}/resolve` |
| 7 | Field bổ sung cho Dashboard | ✅ Xong |
| 8 | `description` null + ghi rõ giới hạn `size` | ✅ Xong (xem ghi chú bên dưới) |

---

## 1. Users — hồ sơ Intern

Đã thêm đúng bộ field FE đề xuất vào **cả** `GET /users` (list) và `GET /users/{id}`:
`department`, `mentor_id`, `mentor_name`, `mentor_email`, `phone`, `start_date`, `end_date`, `university`, `major`, `bio`, `github_url`, `score`, `attendance_rate`.

- Endpoint sửa: **`PATCH /users/{id}/profile`** (quyền MENTOR/ADMIN), tách khỏi `PATCH /auth/me` đúng như đề xuất.
- `mentor_name`/`mentor_email` là **read-only**, backend tự resolve từ `mentor_id` (1 query, không N+1).
- `department` là enum với **đúng 5 nhãn FE đang hiển thị** (`Java Back-End`, `React Front-End`, `Cloud & DevOps`, `Salesforce/ERP`, `AI & Data Science`) → FE không cần map.
- `score`, `attendance_rate`: `number`, ràng buộc `0..100` (gửi ngoài khoảng → 422). Nếu thang điểm thực tế là 1–10 thì vẫn gửi được (8.5), chỉ là backend không chặn ở 10.
- Gửi `null` tường minh để **xóa** một field (`{"mentor_id": null}`).
- `mentor_id` phải là tài khoản MENTOR/ADMIN đang tồn tại, và `end_date >= start_date`, nếu không → `400` kèm `detail` rõ nguyên nhân.

## 2/3/4. Projects, Tasks, Daily Reports

Đúng các endpoint FE đề xuất, cộng vài endpoint bổ sung (đánh dấu ⭐) mà workflow bắt buộc phải có:

```
GET    /projects                      GET    /tasks                 GET    /daily-reports
POST   /projects                      POST   /tasks                 POST   /daily-reports
GET    /projects/{id}                 GET    /tasks/{id}      ⭐     GET    /daily-reports/{id}       ⭐
PATCH  /projects/{id}                 PATCH  /tasks/{id}            PATCH  /daily-reports/{id}     ⭐
DELETE /projects/{id}                 DELETE /tasks/{id}            PATCH  /daily-reports/{id}/review
POST   /projects/{id}/members
DELETE /projects/{id}/members/{user_id}
```

⭐ `PATCH /daily-reports/{id}` là cần thiết: mentor trả `Needs Revision` thì Intern phải sửa lại được. Sau khi Intern sửa, báo cáo **tự về `Pending`**; báo cáo đã `Approved` thì bị đóng băng (`400`).

**Ba điểm FE cần lưu ý khi nối:**

1. **Backend tự thu hẹp dữ liệu theo role** (luật bảo mật, `CLAUDE.md` mục 6) — FE không cần tự lọc:
   - `/projects`: INTERN chỉ thấy dự án mình là `lead_user_id` hoặc thành viên. Xem chi tiết dự án không thuộc mình → `403`.
   - `/tasks`: INTERN chỉ thấy task `assigned_intern_id` = chính mình. Truyền `assigned_intern_id` của người khác cũng bị bỏ qua.
   - `/daily-reports`: INTERN chỉ thấy báo cáo của mình. `intern_id` trong body `POST` không được dùng — tác giả **luôn** là user trong token.
2. **`PATCH /tasks/{id}` phân quyền theo field**: MENTOR sửa mọi field; INTERN chỉ được sửa `status` và `pr_url` **trên task của mình**. Gửi field khác (vd `mentor_feedback`) → `403` kèm danh sách field bị từ chối. Kéo task sang `Done` thì backend tự set `completed_at` (rời `Done` thì xóa) — FE không cần gửi field này.
3. **`DELETE /projects/{id}` là xóa mềm** (vì `tasks` còn tham chiếu): sau khi xóa thì mất khỏi list và `GET` chi tiết trả `404`, nhưng task cũ không bị mồ côi. `DELETE /tasks/{id}` là xóa thật.

Ghi chú thêm:
- `projects.code` là **UNIQUE** → tạo/sửa trùng code trả `409`.
- `projects.tags` dùng chung bảng `tags` với Documents: ghi bằng `tag_ids`, đọc ra là mảng tên tag (giống `ApiDocument.tags`).
- `projects.progress_percent` là số **do Mentor tự nhập** (0..100), không tự suy ra từ tasks. Số theo task nằm ở `task_completion_percent` của `/dashboard/me`.
- `tasks.project_id` **nullable** để mentor giao được task ngoài dự án; `mentor_id` mặc định = người tạo task.
- `daily_reports` có **UNIQUE(intern_id, date)** → tạo trùng ngày trả `409`. `hours_logged` ràng buộc `0..24`, `rating` ràng buộc `1..5`.
- Review chỉ nhận `Approved` hoặc `Needs Revision` (gửi `Pending` → `400`); response có thêm `reviewed_by`, `reviewer_name`, `reviewed_at`.

## 5. Module — metadata course card

Đã thêm 4 field đề xuất: `track` (enum `department`), `week_number` (int ≥ 1), `duration_text` (string tự do, vd `"2 tuần"`), `key_skills` (`string[]`, mặc định `[]`). Có mặt ở `POST /roadmaps/{id}/modules`, `PATCH /modules/{id}`, `GET /roadmaps/{id}` **và** `GET /me/roadmaps/{assignment_id}` (view của Intern).

Gửi `key_skills` (kể cả `[]`) là thay toàn bộ danh sách.

**Chưa làm — cần họp:**
- `resourcesCount`: hiện FE tính được bằng `modules[].documents.length` (roadmap detail) hoặc `lessons.length` (learning detail), nên chưa thêm field riêng. Nếu muốn có field, nói để backend thêm.
- Link Skilljar riêng cho từng khoá: chưa có field. Nếu chỉ là 1 URL/khoá thì thêm `external_url` vào `modules` là xong — chờ FE xác nhận.
- **"major task → section"**: chưa làm. Đây là thêm 1 cấp trong cây dữ liệu (`module → module_document → section`) và ảnh hưởng tới cả `lesson_progress` + `comments` (đang khoá vào `module_document_id`), nên cần thống nhất trước:
  - `ModuleDocument` hiện tại map thành "major task" — đúng ý FE không?
  - Checkbox hoàn thành nằm ở **section** thì `progress_percent` tính theo section hay theo task? (`total_lessons` hiện đang đếm `module_documents`.)
  - Thảo luận riêng theo từng task thì giữ nguyên `comments.module_document_id`; nếu cần comment theo từng section thì phải thêm cột/bảng mới.

## 6. Comments

- Thêm `code_snippet` (string | null) và `is_resolved` (bool, default `false`) vào response của **cả 4** endpoint comment.
- `POST` nhận thêm `code_snippet`; `PATCH /comments/{id}` (chủ comment) nhận `content` + `code_snippet` (gửi `null` để bỏ đoạn code).
- **`PATCH /comments/{id}/resolve`** — quyền MENTOR, tách khỏi quyền sửa nội dung đúng như FE đề xuất. Body **không bắt buộc** (gọi trống = resolve); gửi `{"is_resolved": false}` để mở lại. INTERN gọi → `403`.

## 7. Dashboard

- `GET /dashboard/me`: thêm `task_completion_percent` (task `Done` / tổng task của chính mình, 0 nếu chưa có task) và `pending_reports_count` (báo cáo của mình đang `Pending`).
- `GET /dashboard/overview`: thêm `avg_score` (trung bình `users.score` của Intern **đã có điểm**, `0` nếu chưa ai có), `completed_tasks_this_week` (task sang `Done` từ **thứ Hai 00:00 UTC** tuần này), `pending_reviews_count` (tổng báo cáo `Pending`).

## 8. Sửa nhanh

- **`ApiDocument.description`**: kiểm tra lại trên code hiện tại thì **schema đã đúng rồi** — `description` là `anyOf: [string, null]` và **không** nằm trong `required`. Có thể lúc test FE đang gọi vào bản deploy cũ hơn commit hiện tại. Sau khi deploy lại, generate type từ `/openapi.json` sẽ ra `description?: string | null` — FE bỏ được đoạn fallback `''` nếu muốn. Backend giữ nguyên `null` (không đổi thành `""`) để phân biệt "chưa nhập" với "để trống".
- **Giới hạn `size`**: đã ghi rõ trong `description` của param trên Swagger: *"Items per page, 1..100 (default 20). A value above 100 is rejected with 422."* Áp dụng đồng loạt cho **mọi** list endpoint (`/users`, `/groups`, `/documents`, `/roadmaps`, `/roadmap-assignments`, và 3 resource mới) qua một kiểu param dùng chung, nên các endpoint sau này cũng tự có mô tả này. Ràng buộc `maximum: 100` trong JSON schema vẫn giữ nguyên.

---

## Đã kiểm thử

Chạy smoke test qua ASGI app + DB thật: **112 assertion, pass hết**, gồm cả các case phân quyền (INTERN không sửa được `mentor_feedback`, không xem được dự án/báo cáo của người khác, không spoof được filter `assigned_intern_id`/`intern_id`), các case lỗi (`400`/`403`/`409`/`422`), `completed_at` tự set/xóa, và vòng đời `Pending → Needs Revision → Pending → Approved` của báo cáo.
