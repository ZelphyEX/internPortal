"""FastAPI application entrypoint.

Run: uvicorn app.main:app --reload  ->  http://localhost:8000/docs
"""
import logging
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings

logger = logging.getLogger("app")

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Local storage backend: serve uploaded files so their content_url resolves.
if settings.STORAGE_BACKEND.lower() == "local":
    _local_dir = Path(settings.STORAGE_LOCAL_DIR)
    _local_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=_local_dir), name="files")

# CORS: allow the (separate) frontend origin(s) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bắt mọi exception không lường trước (vd lỗi DB) để trả JSON 500 thay vì để
# Starlette's ServerErrorMiddleware xử lý mặc định. Lý do: handler đăng ký qua
# @app.exception_handler chạy BÊN TRONG CORSMiddleware, còn phản hồi 500 mặc
# định của ServerErrorMiddleware nằm NGOÀI CORSMiddleware nên thiếu header CORS
# -> trình duyệt chặn response, JS thấy "network error"/"failed to fetch" y hệt
# mất mạng, dù server đã xử lý xong (chỉ là bị lỗi). Người dùng lẫn Mentor debug
# đều tưởng nhầm là lỗi kết nối trong khi thực chất là lỗi 500 phía server.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Đã xảy ra lỗi phía máy chủ. Vui lòng thử lại sau."},
    )


# All v1 endpoints live under /api/v1.
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
