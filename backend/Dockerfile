# Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SOVEREIGN_STORAGE_DIR=/data/storage \
    FASTEMBED_CACHE_PATH=/data/models \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

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
# Bake the embedding model into the image: a host that sleeps when idle would otherwise
# download it again on every cold start.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"
WORKDIR /app/backend
EXPOSE 8100
# Hosts like Render pass the port in $PORT.
CMD ["sh", "-c", "alembic upgrade head && uvicorn sovereign.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8100} --proxy-headers --forwarded-allow-ips '*'"]
