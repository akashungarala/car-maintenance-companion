# syntax=docker/dockerfile:1.9
#
# Build context is the repository root, because the uv workspace lockfile lives
# there:  docker build -f apps/api/Dockerfile .
#
# Targets linux/arm64 to match the production cluster (ADR-0002). CI builds it
# natively on an arm64 runner rather than under QEMU (ADR-0001).

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    # Build the venv at the path it will occupy at runtime. Script shebangs and
    # pyvenv.cfg bake in absolute paths, so a venv built elsewhere and copied
    # fails with "no such file or directory" on exec.
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build

# Dependencies resolve from the lockfile alone, so this layer is cached until
# the lockfile changes — source edits do not re-resolve the dependency tree.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable --package cmc-api

COPY apps/api/src apps/api/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package cmc-api


FROM python:3.13-slim-bookworm AS runtime

# Non-root with a fixed high uid: the Kubernetes securityContext pins
# runAsUser to the same value, and a numeric uid keeps that working even if
# the image's /etc/passwd changes.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder --chown=root:root /opt/venv /opt/venv

USER 10001

EXPOSE 8000

# Container-level liveness for `docker run` and compose. Kubernetes uses its own
# probes against the same endpoint (F5) and ignores this.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# --no-access-log: the RequestContextMiddleware already emits a structured
# access log. Uvicorn's own line is plain text, so leaving it on puts
# non-JSON records into the log pipeline and double-counts every request.
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
