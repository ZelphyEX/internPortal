"""Cloud storage wrapper (task 1.3).

Abstracts where uploaded files live. Three backends, selected by
`STORAGE_BACKEND` env:
  * "local" (default, dev): writes into STORAGE_LOCAL_DIR; the app serves
    them via the /files StaticFiles mount. content_url = STORAGE_PUBLIC_BASE_URL/<name>.
  * "gcs": Google Cloud Storage via google-cloud-storage + Application
    Default Credentials (no keys in env). content_url is the object's public
    URL, so the bucket must grant allUsers the Storage Object Viewer role.
  * "s3": pushes to an S3-compatible bucket / MinIO / GCS XML API (endpoint,
    HMAC keys, bucket from env). content_url = S3_PUBLIC_URL_BASE/<name>.

Dev B: don't call backends directly — use `get_storage().save(...)`.
It returns the public `content_url` string.
"""
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
import secrets

from app.core.config import settings


def _unique_name(original_filename: str | None) -> str:
    """Random, collision-proof object name, keeping the original extension."""
    ext = Path(original_filename or "").suffix.lower()
    return f"{secrets.token_hex(16)}{ext}"


class Storage(ABC):
    @abstractmethod
    def save(
        self, data: bytes, *, original_filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Persist `data` and return a public content_url."""


class LocalStorage(Storage):
    def __init__(self, directory: str, public_base_url: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.public_base_url = public_base_url.rstrip("/")

    def save(self, data, *, original_filename=None, content_type=None) -> str:
        name = _unique_name(original_filename)
        (self.directory / name).write_bytes(data)
        return f"{self.public_base_url}/{name}"


class GCSStorage(Storage):
    """Google Cloud Storage backend.

    Credentials come from Application Default Credentials, so no key material
    lives in env: on Cloud Run it is the service account attached to the
    service; locally run `gcloud auth application-default login` or point
    GOOGLE_APPLICATION_CREDENTIALS at a service-account JSON key.

    The returned content_url is the object's public URL, so the bucket must
    grant `allUsers` the Storage Object Viewer role (see docs/DEPLOYMENT.md).
    """

    def __init__(self) -> None:
        from google.cloud import storage as gcs  # lazy: only this backend needs it

        if not settings.GCS_BUCKET:
            raise RuntimeError("STORAGE_BACKEND=gcs but GCS_BUCKET is empty")
        client = gcs.Client(project=settings.GCS_PROJECT_ID or None)
        self.bucket = client.bucket(settings.GCS_BUCKET)
        self.prefix = settings.GCS_PREFIX.strip("/")
        self.public_base = (
            settings.GCS_PUBLIC_URL_BASE.rstrip("/")
            or f"https://storage.googleapis.com/{settings.GCS_BUCKET}"
        )

    def _object_name(self, filename: str | None) -> str:
        name = _unique_name(filename)
        return f"{self.prefix}/{name}" if self.prefix else name

    def save(self, data, *, original_filename=None, content_type=None) -> str:
        object_name = self._object_name(original_filename)
        blob = self.bucket.blob(object_name)
        if settings.GCS_CACHE_CONTROL:
            blob.cache_control = settings.GCS_CACHE_CONTROL
        blob.upload_from_string(
            data, content_type=content_type or "application/octet-stream",
        )
        return f"{self.public_base}/{object_name}"


class S3Storage(Storage):
    """S3-compatible / GCS backend. boto3 imported lazily so local dev needs
    no AWS SDK. NOTE: not exercised in CI (no bucket credentials here)."""

    def __init__(self) -> None:
        import boto3  # lazy

        self.bucket = settings.S3_BUCKET
        self.public_base = settings.S3_PUBLIC_URL_BASE.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
            region_name=settings.S3_REGION or None,
        )

    def save(self, data, *, original_filename=None, content_type=None) -> str:
        name = _unique_name(original_filename)
        extra = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self.bucket, Key=name, Body=data, **extra)
        base = self.public_base or f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{self.bucket}"
        return f"{base}/{name}"


@lru_cache
def get_storage() -> Storage:
    """Backend picked by STORAGE_BACKEND; built once, on first upload."""
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "gcs":
        return GCSStorage()
    if backend == "s3":
        return S3Storage()
    return LocalStorage(settings.STORAGE_LOCAL_DIR, settings.STORAGE_PUBLIC_BASE_URL)
