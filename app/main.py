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

# Bắt mọi exception không lường trước (vd lỗi DB) để trả JSON 500 thay vì để
# Starlette's ServerErrorMiddleware xử lý mặc định.
#
# QUAN TRỌNG: phải là middleware HTTP thường (@app.middleware("http")), KHÔNG
# phải @app.exception_handler(Exception) — Starlette đặc cách handler đăng ký
# cho key `Exception`/500 làm `error_handler` của ServerErrorMiddleware (xem
# Starlette.build_middleware_stack), mà ServerErrorMiddleware LUÔN nằm NGOÀI
# CORSMiddleware bất kể handler đó là gì. Middleware bên dưới bắt exception
# TRƯỚC khi nó bay tới ServerErrorMiddleware, trả response ngay tại đây — response
# này đi ra qua CORSMiddleware như bình thường nên có đủ header. Thiếu header là
# trình duyệt chặn response, JS thấy "network error" y hệt mất mạng dù server đã
# xử lý xong (chỉ là bị lỗi) — người dùng lẫn Mentor debug tưởng nhầm là lỗi mạng.
#
# Đăng ký middleware này TRƯỚC CORSMiddleware: Starlette xếp middleware đăng ký
# sau cùng ra ngoài cùng, nên CORSMiddleware (đăng ký sau) bọc ngoài middleware
# này (đăng ký trước) — đúng thứ tự cần.
@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
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


# CORS: allow the (separate) frontend origin(s) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All v1 endpoints live under /api/v1.
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
