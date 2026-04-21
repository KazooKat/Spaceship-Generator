# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Spaceship Generator — container image
#
# Two-stage build:
#   1. builder  — compiles the project into a wheel using build deps
#   2. runtime  — minimal slim image with just the wheel + gunicorn
#
# Final image targets < 250 MB. Run `docker build -t spaceship-generator .`
# ---------------------------------------------------------------------------

# ----------------------------- Stage 1: builder ----------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build toolchain for any pure-Python / sdist-only deps that need compilation.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only what's needed to build the wheel. This keeps the builder cache
# stable across unrelated file changes (docs, tests, etc.).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip wheel \
 && pip wheel . --wheel-dir /wheels --no-deps

# ----------------------------- Stage 2: runtime ----------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GUNICORN_WORKERS=2 \
    PORT=8000

# curl is needed for HEALTHCHECK; everything else stays out of the image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /usr/sbin/nologin --uid 1000 app

WORKDIR /app

# Install the wheel (pulls runtime deps from PyPI) plus gunicorn.
COPY --from=builder /wheels/*.whl /tmp/wheels/
RUN pip install --upgrade pip \
 && pip install /tmp/wheels/spaceship_generator-*.whl gunicorn \
 && rm -rf /tmp/wheels

# WSGI shim — gunicorn's CLI does not support the `factory()` call syntax,
# so we write a tiny wrapper that invokes create_app() once at import time.
RUN printf '%s\n' \
    'from spaceship_generator.web.app import create_app' \
    '' \
    'app = create_app()' \
    > /app/wsgi.py \
 && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/ || exit 1

# Use shell form so ${GUNICORN_WORKERS} / ${PORT} expand at runtime, letting
# operators scale workers via `-e GUNICORN_WORKERS=4` without rebuilding.
ENTRYPOINT ["/bin/sh", "-c", "exec gunicorn wsgi:app --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS} --access-logfile -"]
