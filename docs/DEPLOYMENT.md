# DEPLOYMENT.md — CI/CD GitHub → Google Cloud Run

> Repo: backend FastAPI. Mỗi lần push lên `main` → tự build Docker → push Artifact Registry → deploy Cloud Run.
> File này có 2 mục đích: (1) **checklist tay** cho người làm, (2) **spec** cho Claude Code sinh Dockerfile + workflow.
> ⚠️ TUYỆT ĐỐI không ghi giá trị secret (key, mật khẩu, DATABASE_URL thật) vào file này hay bất kỳ file nào trong repo. Chỉ ghi TÊN secret.

---

## 1. Quyết định cấu hình (người điền — agent đọc để sinh file cho khớp)

| Thông số | Giá trị của bạn |
|---|---|
| Region | `asia-southeast1` |
| Artifact Registry repo name | `intern-portal-repo` |
| Cloud Run service name | `intern-portal-api` |
| Image path | `asia-southeast1-docker.pkg.dev/$GCP_PROJECT_ID/intern-portal-repo/intern-portal-api` |
| Cổng app | Nghe theo env `PORT` do Cloud Run cấp (mặc định 8080) |
| Phương thức auth | Workload Identity Federation (đã chốt) |

**GitHub Secrets/Variables cần có (người tạo trong Settings, agent chỉ tham chiếu tên):**
- `GCP_PROJECT_ID`
- `WIF_PROVIDER` — resource name của Workload Identity Provider
- `WIF_SERVICE_ACCOUNT` — email service account deploy
- `CLOUD_SQL_CONNECTION_NAME` — connection name Cloud SQL, dạng `PROJECT:REGION:INSTANCE`
- `DATABASE_URL`, `JWT_SECRET`, và biến bucket — biến chạy app, inject vào Cloud Run lúc deploy.
  - App đọc JWT secret ở env **`SECRET_KEY`**; workflow map `SECRET_KEY = ${{ secrets.JWT_SECRET }}`.
  - Cloud SQL: `DATABASE_URL` dùng dạng **socket** (không dùng IP):
    `postgresql+psycopg://<user>:<password>@/<db>?host=/cloudsql/PROJECT:REGION:INSTANCE`

---

## 2. Việc PHẢI làm tay (ngoài repo — agent không làm được)

- [ ] Tạo/chọn GCP project, bật billing.
- [ ] Bật API: `run`, `artifactregistry`, `iam`, `sts`, `iamcredentials`.
- [ ] Tạo Artifact Registry repo (Docker, đúng region ở mục 1).
- [ ] Tạo Service Account, gán role: **Artifact Registry Writer**, **Cloud Run Developer**, **Service Account User**, **Cloud SQL Client** (DB là Cloud SQL).
- [ ] Tạo Workload Identity Pool + Provider (OIDC, issuer `https://token.actions.githubusercontent.com`), giới hạn đúng repo, bind vào Service Account.
- [ ] Thêm GitHub Secrets ở mục 1.
- [ ] `git remote add origin <URL>` và push lần đầu.
- [ ] Sau khi Actions chạy xong: lấy URL Cloud Run, gọi thử `/docs`, `/health`.

---

## 3. Việc agent sinh trong repo

1. **Dockerfile** (multi-stage nhẹ, python 3.11-slim). App chạy `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`.
2. **entrypoint**: chạy `alembic upgrade head` rồi mới start uvicorn (để migration tự áp khi deploy). Nếu DB không reachable lúc build/deploy thì cần chạy migration ở bước riêng — xem mục 4.
3. **.dockerignore** (loại `.venv`, `__pycache__`, `.env`, `.git`, `tests`...).
4. **.github/workflows/deploy.yml**:
   - trigger: push `main`.
   - `permissions: { contents: read, id-token: write }` (bắt buộc cho WIF).
   - `google-github-actions/auth` (WIF) → `auth` → build & push image → `google-github-actions/deploy-cloudrun`.
   - deploy kèm `--set-env-vars`/`--set-secrets` cho `DATABASE_URL`, `JWT_SECRET`, bucket...
   - **Dùng major version mới nhất**: `actions/checkout@v6`, `google-github-actions/auth@v3`, `google-github-actions/deploy-cloudrun@v3` (kiểm tra release mới nhất trước khi chốt).
5. **/health** endpoint đơn giản để kiểm tra sau deploy.

---

## 4. Điểm dễ vướng (nhắc agent xử lý)

- **PORT**: Cloud Run cấp cổng qua env `PORT`; app phải nghe `0.0.0.0:$PORT`, không hardcode 8000.
- **Secret**: không hardcode. Ưu tiên **Secret Manager** + `--set-secrets`, hoặc `--set-env-vars` lấy từ GitHub secret. Không commit `.env`.
- **Kết nối DB**: nếu Postgres là **Cloud SQL**, Cloud Run phải nối qua Cloud SQL connector (`--add-cloudsql-instances=<CONN_NAME>`) và service account cần role **Cloud SQL Client**; `DATABASE_URL` dùng đúng dạng socket. Nếu DB ở nơi khác thì mở IP/allowlist tương ứng.
- **Migration**: chạy `alembic upgrade head` lúc container start là đơn giản nhất, nhưng chỉ chạy khi Cloud Run nối được DB. Nếu muốn tách, tạo một Cloud Run **Job** riêng để migrate.
- **WIF quyền**: nhớ `id-token: write` trong workflow, nếu không sẽ lỗi xác thực.