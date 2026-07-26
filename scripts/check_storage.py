"""Smoke-test the configured storage backend end to end.

Uploads a tiny text file through app.services.storage, then (for gcs)
downloads the resulting public URL to confirm the bucket really is readable
by anonymous clients — which is what frontend needs for content_url.

    python -m scripts.check_storage
"""
import sys
import urllib.error
import urllib.request

from app.core.config import settings
from app.services.storage import get_storage

PROBE = b"intern-portal storage check\n"


def main() -> int:
    print(f"STORAGE_BACKEND = {settings.STORAGE_BACKEND}")
    if settings.STORAGE_BACKEND.lower() == "gcs":
        print(f"GCS_BUCKET      = {settings.GCS_BUCKET or '(empty!)'}")
        print(f"GCS_PREFIX      = {settings.GCS_PREFIX or '(bucket root)'}")

    try:
        url = get_storage().save(
            PROBE, original_filename="storage-check.txt", content_type="text/plain",
        )
    except Exception as exc:  # noqa: BLE001 - surface the raw cause to the operator
        print(f"\nUPLOAD FAILED: {type(exc).__name__}: {exc}")
        print("\nHints:")
        print("  * 403 / DefaultCredentialsError -> run: gcloud auth application-default login")
        print("  * 404 NotFound                  -> GCS_BUCKET name is wrong")
        print("  * 403 on the bucket             -> the account needs roles/storage.objectAdmin")
        return 1

    print(f"\nUPLOAD OK -> {url}")

    if not url.startswith("http"):
        print("(relative URL: local backend, nothing to fetch)")
        return 0

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 - our own URL
            body = resp.read()
    except urllib.error.HTTPError as exc:
        print(f"\nPUBLIC READ FAILED: HTTP {exc.code}")
        print("  Grant anonymous read on the bucket:")
        print(f"    gcloud storage buckets add-iam-policy-binding gs://{settings.GCS_BUCKET} \\")
        print("      --member=allUsers --role=roles/storage.objectViewer")
        return 1
    except urllib.error.URLError as exc:
        print(f"\nPUBLIC READ FAILED: {exc.reason}")
        return 1

    if body != PROBE:
        print("\nPUBLIC READ returned unexpected content")
        return 1

    print("PUBLIC READ OK - the URL is usable as content_url")
    return 0


if __name__ == "__main__":
    sys.exit(main())
