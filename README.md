# Intern Portal — Backend (FastAPI)

Backend-only. Quản lý thực tập sinh, lộ trình học, tiến độ. 3 role: `ADMIN > MENTOR > INTERN`.
Nguồn sự thật API: [`docs/API_SPEC.md`](docs/API_SPEC.md). Quy ước dự án: [`CLAUDE.md`](CLAUDE.md).

---

## Chạy dự án (dev)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   *nix: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # rồi điền DATABASE_URL, SECRET_KEY, ... (.env KHÔNG commit)

alembic upgrade head          # tạo toàn bộ bảng
uvicorn app.main:app --reload # http://localhost:8000/docs
```

Tạo **admin đầu tiên** (register chỉ tạo INTERN; POST /users cần sẵn ADMIN → bootstrap bằng script):

```bash
python -m scripts.create_user --email admin@example.com --password <pw> --name "Admin" --role ADMIN
# sau đó admin login rồi dùng POST /users (Dev B) để tạo MENTOR
```

Migration mới (khi đổi model): `alembic revision --autogenerate -m "..."` → kiểm tra file trong `alembic/versions/` → `alembic upgrade head`.

---

## Trạng thái — Phase 1 (Dev A) ✅ HOÀN TẤT

- **13 bảng** + 4 enum lên DB qua migration `c91b052bfd47` (head).
- `/docs` có đủ nhóm **Auth / Documents / Tags / Roadmaps** (26 endpoint).
- Nền tảng dùng chung: `core/config.py`, `db/session.py`, `db/base.py`, `core/security.py`, `core/deps.py`, `services/storage.py`, `core/pagination.py`.
- Đã test HTTP end-to-end toàn bộ (auth flow, documents, tags, roadmaps/modules).

Phase 2 (Dev B): Users, Groups, Assignments, Learning/Progress, Dashboard, Comments — xem `docs/TEAM_TASKS.md`.

---

## 🤝 Bàn giao cho Dev B — API dùng lại (KHÔNG viết lại)

### 1. Auth & phân quyền — `app/core/deps.py`

```python
from app.core.deps import (
    get_db, get_current_user, require_role,
    DbSession, CurrentUser, MentorRequired, AdminRequired,  # Annotated shortcuts
)
from app.models.user import Role, User

# Trong router — chỉ dùng các dependency này để kiểm quyền (đừng tin frontend):
def endpoint(db: DbSession, user: CurrentUser):     ...   # bất kỳ user ACTIVE đã đăng nhập
def endpoint(db: DbSession, user: MentorRequired):  ...   # MENTOR + ADMIN
def endpoint(db: DbSession, user: AdminRequired):   ...   # chỉ ADMIN
def endpoint(user: User = Depends(require_role(Role.MENTOR))): ...   # cách tường minh
```

- `get_current_user` → trả về **ORM `User`** (đã load từ DB): 401 nếu token thiếu/sai/hết hạn hoặc user không tồn tại/đã soft-delete; **403 nếu status = LOCKED**.
- `require_role(min_role)` → dependency factory, 403 nếu quyền thấp hơn. Cấp bậc: `ADMIN(3) > MENTOR(2) > INTERN(1)`.
- Với endpoint `/me/*`: luôn kiểm tài nguyên thuộc `current_user.id` (Intern không xem được của người khác → 403).

### 2. Security helpers — `app/core/security.py`

```python
hash_password(pw) -> str;  verify_password(pw, hash) -> bool          # bcrypt
create_access_token(subject, role, expires_delta=None) -> str
decode_access_token(token) -> dict                                    # raise jwt.PyJWTError
create_refresh_token() -> str            # token thô (trả client)
hash_refresh_token(raw) -> str           # LƯU cái này vào refresh_tokens.token_hash
verify_refresh_token(raw, hash) -> bool
refresh_token_expires_at() -> datetime
```

### 3. Phân trang — `app/core/pagination.py` + `app/schemas/common.py`

```python
from app.core.pagination import paginate, DEFAULT_PAGE, DEFAULT_SIZE, MAX_SIZE
from app.schemas.common import Page

stmt = select(Model).where(...).order_by(...)
rows, total, pages = paginate(db, stmt, page=page, size=size)
return Page(items=[...], total=total, page=page, size=size, pages=pages)
```

Response chuẩn: `{ "items": [], "total", "page", "size", "pages" }`. Query params khai báo `Query(ge=1)`, `Query(ge=1, le=MAX_SIZE)`.

### 4. Cloud storage — `app/services/storage.py`

```python
from app.services.storage import get_storage
url = get_storage().save(data_bytes, original_filename=name, content_type=ctype)  # -> content_url
```

- Chọn backend qua env `STORAGE_BACKEND` = `local` (dev, ghi vào `STORAGE_LOCAL_DIR`, phục vụ qua mount `/files`) hoặc `s3` (bucket S3/GCS).
- Endpoint dựng sẵn: `POST /api/v1/documents/upload` (multipart field `file`) → `{ "content_url": ... }`.

### 5. Thêm router mới

Tạo `app/api/v1/routers/<tên>.py` (có `router = APIRouter(...)`), rồi include trong `app/api/v1/api.py`:
```python
api_router.include_router(<tên>.router)
```
Models đã có sẵn đủ 13 bảng trong `app/models/` (import registry ở `app/models/__init__.py`). Schema đầy đủ nên **thường không cần migration**; nếu phát sinh cột mới thì tạo migration nối tiếp.

---

## ⚠️ Ghi chú lệch/quyết định (Dev A)

1. **Password hash dùng thẳng `bcrypt`** (không qua `passlib`): passlib 1.7.4 không tương thích `bcrypt>=4.1` trên Python 3.14. Cùng thuật toán, cùng mức bảo mật — đừng đổi ngược về passlib.
2. **`documents.deleted_at`** được thêm để soft-delete document (đúng LUẬT BẢO MẬT §6), dù schema gốc §4 không liệt kê cột này.
3. **`POST /documents/upload` cho mọi user đã đăng nhập** (không chỉ MENTOR) vì ảnh đại diện của INTERN dùng chung endpoint này; nó chỉ lưu file + trả URL, không tạo record.
4. Refresh token là **chuỗi opaque**, chỉ lưu **SHA-256 hash**. Đổi mật khẩu sẽ **revoke toàn bộ** refresh token của user.
5. `scripts/create_user.py` để bootstrap ADMIN/MENTOR đầu tiên (register chỉ tạo INTERN).
