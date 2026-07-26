# Yêu cầu bổ sung/điều chỉnh API Backend — Gimasys Intern Portal

Tài liệu này gửi cho team backend (FastAPI, Swagger tại `/docs`), tổng hợp từ việc rà soát Frontend (React) để nối API thật. Mục tiêu: liệt kê chính xác chỗ nào API hiện tại **chưa đủ** để Frontend hiển thị đúng những gì đang có trên UI (Roadmap học tập, Dashboard, Comment bài học, Projects/Tasks/Daily Reports), kèm đề xuất field/endpoint cụ thể để backend có thể bắt tay vào làm ngay.

**Đã nối tốt, không cần sửa**: `auth/*`, `users` (list/get/lock/unlock/remove — chỉ thiếu field, xem mục 1), `groups/*`, `documents/*`, `tags/*`, `roadmaps/modules/assignments/learning/dashboard/comments` (đã có đủ endpoint, chỉ cần bổ sung như mục 5-7 bên dưới nếu muốn khớp UI hiện tại).

---

## 1. `Users` — thiếu field hồ sơ Intern

Hiện `GET /users`, `GET /users/{id}` chỉ trả: `id, full_name, email, role, status, avatar_url`. Frontend cần thêm (optional, chỉ có ý nghĩa với `role=INTERN`):

| Field đề xuất | Kiểu | Ghi chú |
|---|---|---|
| `department` | enum | `Java Back-End \| React Front-End \| Cloud & DevOps \| Salesforce/ERP \| AI & Data Science` |
| `mentor_id`, `mentor_name`, `mentor_email` | number/string | Mentor phụ trách intern này |
| `phone` | string | |
| `start_date`, `end_date` | date | Thời gian thực tập |
| `university`, `major` | string | |
| `bio` | string | |
| `github_url` | string | |
| `score`, `attendance_rate` | number | Điểm đánh giá / tỉ lệ chuyên cần |

Đề xuất: thêm các field này vào cả `GET /users` (list) và `GET /users/{id}`, cho phép `PATCH` bởi MENTOR/ADMIN (endpoint riêng, ví dụ `PATCH /users/{id}/profile`, tách khỏi `PATCH /auth/me` vốn chỉ để tự sửa hồ sơ của chính mình).

---

## 2. `Projects` — chưa có resource này

Frontend có màn "Dự án" (Project) hoàn toàn không có endpoint tương ứng. Đề xuất:

```
GET    /projects                      (phân trang, filter department/status)
POST   /projects                      (MENTOR/ADMIN)
GET    /projects/{id}
PATCH  /projects/{id}
DELETE /projects/{id}
POST   /projects/{id}/members         { user_ids: number[] }
DELETE /projects/{id}/members/{user_id}
```

Field gợi ý: `code, title, department, status (In Planning|Active|Under Review|Completed), lead_user_id, member_ids[], progress_percent, deadline, description, tags[]`.

---

## 3. `Tasks` — chưa có resource này

```
GET    /tasks           (filter project_id, assigned_intern_id, status)
POST   /tasks
PATCH  /tasks/{id}       (đổi status, pr_url, mentor_feedback)
DELETE /tasks/{id}
```

Field gợi ý: `title, project_id, assigned_intern_id, mentor_id, status (To Do|In Progress|In Review|Done|Blocked), priority (Low|Medium|High|Urgent), due_date, description, pr_url, mentor_feedback`.

---

## 4. `Daily Reports` — chưa có resource này

```
GET    /daily-reports              (filter intern_id, khoảng ngày, status)
POST   /daily-reports               (Intern tự tạo báo cáo hằng ngày)
PATCH  /daily-reports/{id}/review   (Mentor duyệt)
```

Field gợi ý: `intern_id, date, completed_today, tomorrow_plan, blockers, hours_logged, status (Pending|Approved|Needs Revision), mentor_comment, rating (1-5)`.

---

## 5. `Roadmap`/`Module` — làm rõ mô hình dữ liệu

Frontend hiện có mô hình học tập chi tiết hơn `Module` hiện tại của backend: mỗi "khoá học" có `track` (department), `weekNumber`, `duration`, `keySkills[]`, `resourcesCount`, link Skilljar riêng; bên trong mỗi khoá lại có nhiều **major task**, mỗi major task có nhiều **section** nhỏ (checkbox hoàn thành riêng) + thảo luận riêng theo từng task.

Đề xuất tối thiểu — thêm field cho `Module`:
- `track` (department), `week_number`, `duration_text`, `key_skills: string[]`

Với phần "major task -> section", cần một buổi trao đổi riêng để thống nhất: có thể map `ModuleDocument` hiện tại thành 1 "task", và thêm 1 cấp con mới (`sections`) nếu backend đồng ý mở rộng model — đây là thay đổi kiến trúc nên không đưa quyết định sẵn ở đây, chỉ nêu vấn đề.

---

## 6. `Comments` — thiếu field

`ApiComment` hiện: `id, user, content, created_at, parent_comment_id, replies`. Frontend cần thêm (optional):
- `code_snippet: string | null` — cho phép đính kèm đoạn code khi hỏi/thảo luận bài học.
- `is_resolved: boolean` (mặc định `false`) — đề xuất endpoint riêng `PATCH /comments/{id}/resolve` (quyền MENTOR) vì đây là quyền khác với quyền sửa nội dung comment (chủ comment).

---

## 7. `Dashboard` — bổ sung sau khi có Projects/Tasks/Daily Reports

Sau khi mục 2-4 có backend, đề xuất bổ sung vào response hiện tại:
- `GET /dashboard/me`: thêm `task_completion_percent`, `pending_reports_count`
- `GET /dashboard/overview`: thêm `avg_score`, `completed_tasks_this_week`, `pending_reviews_count`

---

## 8. Sửa nhanh (không cần thiết kế lại gì)

- **`ApiDocument.description`**: OpenAPI khai `string` (bắt buộc) nhưng thực tế API trả `null` cho một số document (đã gặp khi test, ví dụ document id 16-18 trong DB hiện tại). Đề xuất: hoặc luôn trả `""` thay vì `null`, hoặc sửa schema Swagger thành `string | null` cho đúng thực tế — hiện Frontend đã tự fallback `''` để không bị lỗi, nhưng schema sai sẽ gây lỗi cho các client khác generate type từ OpenAPI.
- **Giới hạn `size` (phân trang)**: các endpoint list (`/users`, `/groups`, `/documents`...) hiện giới hạn `size <= 100`, vượt quá sẽ trả `422`. Điều này đúng và Frontend đã tuân theo, chỉ đề nghị ghi rõ constraint này trong mô tả Swagger (`description`) để client khác không phải dò lỗi mới biết.

---

## Đề xuất thứ tự ưu tiên

1. **Nhanh, nên làm ngay**: mục 8 (description null, ghi rõ giới hạn size).
2. **Trung bình**: mục 1 (field hồ sơ Users), mục 6 (field comment).
3. **Lớn, cần thiết kế**: mục 2-4 (Projects/Tasks/Daily Reports — resource hoàn toàn mới).
4. **Cần họp riêng để thống nhất mô hình**: mục 5 (Roadmap/Module mở rộng), mục 7 (Dashboard, phụ thuộc mục 2-4).
