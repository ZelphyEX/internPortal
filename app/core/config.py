"""Application settings, read from environment / .env (pydantic-settings)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    PROJECT_NAME: str = "Intern Portal API"
    API_V1_PREFIX: str = "/api/v1"
    # Comma-separated list of allowed origins, or "*" for all (dev only).
    BACKEND_CORS_ORIGINS: str = "*"

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/intern_portal"
    )

    # --- JWT / Security ---
    # Dev-only fallback; MUST be overridden via .env in any real environment.
    SECRET_KEY: str = "CHANGE_ME__dev_only_secret__override_in_env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # ĐÂY LÀ TUỔI THỌ CỦA MỘT PHIÊN ĐĂNG NHẬP.
    # `/auth/refresh` chỉ cấp access token mới, KHÔNG gia hạn refresh token — nên
    # đây là hạn tuyệt đối tính từ lúc đăng nhập, không phải hạn trượt theo hoạt
    # động. Hết hạn là phải đăng nhập lại, dù đang thao tác liên tục.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 1

    # --- Đăng nhập bằng Google (Google Identity Services) ---
    # OAuth Consent Screen đang đặt là "External" nên Google cho phép mọi tài khoản
    # Gmail bấm đăng nhập. Vì vậy việc giới hạn tên miền PHẢI làm ở backend:
    # chỉ email thuộc các tên miền dưới đây mới đăng ký/đăng nhập được.
    GOOGLE_CLIENT_ID: str | None = None
    # Tên miền KHÔNG quyết định vai trò: ai đăng nhập lần đầu cũng là INTERN. Đây
    # chỉ là danh sách được phép vào hệ thống.
    ALLOWED_EMAIL_DOMAINS: str = "gimasys.com,edu.gimasys.com"
    # Vé đăng ký tạm (ký bằng SECRET_KEY) cấp sau khi Google xác thực xong nhưng
    # tài khoản chưa tồn tại — người dùng phải điền hồ sơ trong khoảng thời gian này.
    SIGNUP_TICKET_EXPIRE_MINUTES: int = 30
    # CHỈ dùng cho dev khi chưa có GOOGLE_CLIENT_ID. Bật lên ở môi trường thật là
    # lỗ hổng: ai cũng tự tạo credential giả để đăng nhập bằng email bất kỳ.
    ALLOW_MOCK_GOOGLE_LOGIN: bool = False

    # --- Tài khoản Quản trị viên hệ thống (bootstrap) ---
    # `scripts/ensure_admin.py` chạy mỗi lần container khởi động và đồng bộ tài
    # khoản này theo 3 biến dưới đây (xem Dockerfile CMD). Đây là tài khoản DUY
    # NHẤT được đăng nhập bằng mật khẩu — mọi vai trò khác phải qua Google.
    #
    # IMPORTANT: mật khẩu admin do biến môi trường quyết định, KHÔNG phải do UI.
    # Đổi mật khẩu trong phần Cài đặt sẽ bị ghi lại theo biến này ở lần deploy sau.
    # Muốn đổi mật khẩu thật thì đổi BOOTSTRAP_ADMIN_PASSWORD rồi deploy lại.
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@gimasys.com"
    BOOTSTRAP_ADMIN_NAME: str = "Quản trị viên Gimasys"
    # Rỗng = không tạo/không đồng bộ gì (script bỏ qua, server vẫn khởi động).
    BOOTSTRAP_ADMIN_PASSWORD: str = ""

    # --- Email verification toggle ---
    EMAIL_VERIFICATION_REQUIRED: bool = True  # Require admin approval / email verification

    # --- SMTP settings for email verification ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_TLS: bool = True
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # --- Cloud storage (bucket) ---
    # "local" (dev) | "gcs" (Google Cloud Storage) | "s3" (S3-compatible)
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_DIR: str = "./storage"      # where local-mode files are written
    # Base URL prepended to a stored file's name to form its content_url.
    # local dev: served by the /files StaticFiles mount (see app.main).
    STORAGE_PUBLIC_BASE_URL: str = "/files"
    MAX_UPLOAD_MB: int = 25                   # reject larger uploads with 413

    # Google Cloud Storage (used when STORAGE_BACKEND=gcs).
    # Auth is Application Default Credentials — no keys in env:
    #   * Cloud Run: the service account attached to the service.
    #   * local dev: `gcloud auth application-default login`, or point
    #     GOOGLE_APPLICATION_CREDENTIALS at a service-account JSON key.
    GCS_BUCKET: str = ""
    GCS_PROJECT_ID: str = ""                  # optional; inferred from ADC if empty
    GCS_PREFIX: str = "uploads"               # object name prefix ("folder"); "" = bucket root
    # Public base for the returned content_url. Empty -> https://storage.googleapis.com/<bucket>.
    # Set this when serving the bucket through a CDN / custom domain.
    GCS_PUBLIC_URL_BASE: str = ""
    GCS_CACHE_CONTROL: str = "public, max-age=31536000"   # uploads are immutable (random names)

    # S3 / MinIO / GCS XML API (used when STORAGE_BACKEND=s3)
    S3_ENDPOINT_URL: str = ""                 # e.g. https://storage.googleapis.com
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = ""
    # Public base to build the returned URL, e.g. https://storage.googleapis.com/<bucket>
    S3_PUBLIC_URL_BASE: str = ""

    # --- SMTP / Email ---
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_TLS: bool = True
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None

    @property
    def allowed_email_domains(self) -> list[str]:
        """ALLOWED_EMAIL_DOMAINS parsed thành danh sách tên miền chữ thường."""
        return [
            d.strip().lower().lstrip("@")
            for d in self.ALLOWED_EMAIL_DOMAINS.split(",")
            if d.strip()
        ]

    @property
    def cors_origins(self) -> list[str]:
        """BACKEND_CORS_ORIGINS parsed into a list for CORSMiddleware."""
        raw = self.BACKEND_CORS_ORIGINS.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Import-time singleton: `from app.core.config import settings`.
settings = get_settings()
