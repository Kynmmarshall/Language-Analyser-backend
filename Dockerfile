# syntax=docker/dockerfile:1

### Builder: resolve dependencies and build the package as a wheel ##########################
FROM python:3.13-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir --upgrade pip build

# Copied separately from src/ so dependency resolution isn't invalidated by source edits.
COPY pyproject.toml ./
COPY src ./src

RUN python -m build --wheel --outdir /build/dist


### Runtime ###################################################################################
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="Francanglais Studio API" \
      org.opencontainers.image.description="Lexical/syntactic analyzer backend for Cameroonian Francanglais"

# Runs as a non-root, non-login user; only the mounted data volume needs to be writable.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# Alembic needs its config and revision scripts at runtime; these live at the repo root,
# not inside the installed wheel (which only contains the yaounde_analyzer package).
COPY alembic.ini ./
COPY migrations ./migrations
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    YAOUNDE_ENV=production \
    YAOUNDE_DATABASE_URL=sqlite:////app/data/app.db

RUN mkdir -p /app/data && chown -R app:app /app
VOLUME ["/app/data"]

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=3)"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "yaounde_analyzer.api.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
