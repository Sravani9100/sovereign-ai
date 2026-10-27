# Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SOVEREIGN_STORAGE_DIR=/data/storage \
    HF_HOME=/data/models

WORKDIR /app
COPY backend/pyproject.toml backend/
COPY backend/src backend/src
# Editable so the demo seed can find demo-data/ next to the source tree.
RUN pip install --no-cache-dir -e ./backend

COPY backend/alembic.ini backend/
COPY backend/migrations backend/migrations
COPY demo-data demo-data

RUN useradd --create-home app && mkdir -p /data && chown app /data
USER app
WORKDIR /app/backend
EXPOSE 8100
CMD ["sh", "-c", "alembic upgrade head && uvicorn sovereign.main:create_app --factory --host 0.0.0.0 --port 8100"]
