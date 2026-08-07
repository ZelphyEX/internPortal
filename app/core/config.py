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
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    GOOGLE_CLIENT_ID: str | None = None

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
