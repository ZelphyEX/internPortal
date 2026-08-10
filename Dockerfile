# syntax=docker/dockerfile:1

# ---- builder: install deps into an isolated venv ----
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---- runtime: slim image with only the venv + app code ----
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . .

# Cloud Run provides $PORT (default 8080). Migrations -> tài khoản admin -> server.
# NOTE: alembic runs at container start; needs the DB reachable (Cloud SQL socket
# is mounted via --add-cloudsql-instances at deploy time).
#
# `ensure_admin` phải chạy SAU alembic (cần bảng users) và TRƯỚC uvicorn. Nó luôn
# thoát 0 (kể cả khi lỗi hoặc chưa đặt BOOTSTRAP_ADMIN_PASSWORD) nên không chặn
# server khởi động — xem scripts/ensure_admin.py.
EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.ensure_admin && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
