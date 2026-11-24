FROM node:22-alpine AS webapp-build
WORKDIR /build
COPY frontend/webapp/package*.json ./
RUN npm ci
COPY frontend/webapp/ ./
RUN npm run build

FROM node:22-alpine AS admin-build
WORKDIR /build
COPY frontend/admin/package*.json ./
RUN npm ci
COPY frontend/admin/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite+aiosqlite:////data/app.db \
    MEDIA_DIR=/app/media \
    LOG_DIR=/app/logs \
    BACKUP_DIR=/app/backups

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini main.py ./
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY docker/ ./docker/
COPY --from=webapp-build /build/dist/ ./frontend/webapp/dist/
COPY --from=admin-build /build/dist/ ./frontend/admin/dist/

RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /data /app/media /app/logs /app/backups \
    && chmod 755 /app/docker/entrypoint.sh \
    && chown -R appuser:appuser /app /data

USER appuser
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
