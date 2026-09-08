# syntax=docker/dockerfile:1.9
#
# Build context is the repository root:  docker build -f apps/web/Dockerfile .
#
# The frontend deploys to Vercel today (ADR-0007). This image exists so that
# moving into the Kubernetes cluster — if Vercel's non-commercial terms ever
# become a problem — is a config change rather than a rewrite. It is built and
# smoke-tested in CI so it cannot rot while unused.

FROM node:22-bookworm-slim AS base
ENV PNPM_HOME=/pnpm
ENV PATH="/pnpm:$PATH"
RUN corepack enable && corepack prepare pnpm@12.3.4 --activate


FROM base AS deps
WORKDIR /build
# Manifests only, so this layer caches until a dependency actually changes.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json apps/web/package.json
RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --frozen-lockfile --filter @cmc/web...


FROM base AS builder
WORKDIR /build
COPY --from=deps /build/node_modules ./node_modules
COPY --from=deps /build/apps/web/node_modules ./apps/web/node_modules
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web ./apps/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter @cmc/web exec next build


FROM node:22-bookworm-slim AS runtime
WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# `output: standalone` emits a self-contained server plus only the node_modules
# it actually needs. Static assets are not included in it and must be copied
# alongside, or every asset 404s — a failure that looks like a broken deploy.
COPY --from=builder --chown=root:root /build/apps/web/.next/standalone ./
COPY --from=builder --chown=root:root /build/apps/web/.next/static ./apps/web/.next/static

USER 10001

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]

CMD ["node", "apps/web/server.js"]
