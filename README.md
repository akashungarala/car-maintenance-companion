# Car Maintenance Companion

Every car owner is quietly forgetting something. This keeps a running, trustworthy answer to
_"what does my car need right now?"_ — and asks almost nothing of the owner to maintain it.

> **Status: Phase 0 — Production Foundation.**
> There is no product functionality yet, deliberately. The complete production platform (Kubernetes,
> CI/CD, database, observability, security) is built and proven _before_ the first product API or
> page exists. See [`docs/backlog/phase-0.md`](docs/backlog/phase-0.md).

## The idea in one paragraph

Maintenance is mileage-driven, but mileage lives on a dashboard you have to walk outside to read.
Every competing tracker dies at that point: it demands continuous odometer entry, the user stops
after two weeks, and the reminders go stale. Instead, we take **one** odometer reading plus a usage
rate, project current mileage forward, and remind on the projected date. When the user marks an item
done we ask for the odometer — so the act of recording a service is also the act of recalibrating
the projection. The correction is free, because it rides on something the user already wanted to do.

## Stack

| Layer         | Choice                                                                            |
| ------------- | --------------------------------------------------------------------------------- |
| Frontend      | TypeScript · Next.js · Tailwind · shadcn/ui → Vercel                              |
| Backend       | Python 3.13 · FastAPI · SQLAlchemy · Pydantic v2                                  |
| Async         | Redis · ARQ worker · Kubernetes CronJob                                           |
| Data          | PostgreSQL 17 via CloudNativePG · Alembic · backups to Cloudflare R2              |
| Platform      | k3s on Oracle Cloud Always Free (arm64) · Traefik · cert-manager · Sealed Secrets |
| Delivery      | GitHub Actions → GHCR → Argo CD (pull-based GitOps)                               |
| Observability | OpenTelemetry → OTel Collector → Grafana Cloud · Alloy · alerts to Discord        |
| IaC           | OpenTofu (Oracle Cloud + Cloudflare)                                              |

Every one of these is a deliberate decision with a written rationale — including the ones that were
rejected. See **[Architecture Decision Records](docs/adr/)**.

## Quick start

Requires [uv](https://docs.astral.sh/uv/), Node 22+, [pnpm](https://pnpm.io) and Docker.

```bash
make setup   # install toolchains, dependencies and git hooks
make check   # run every gate CI runs: lint, type checks, tests, coverage
make help    # list all targets
```

`make check` runs exactly what CI runs. If it passes locally, CI passes.

## Layout

```
apps/api/        FastAPI service (and, from F7, the ARQ worker)
apps/web/        Next.js frontend
packages/        shared workspace packages (api-types is generated from OpenAPI)
infra/tofu/      OpenTofu: Oracle Cloud, Cloudflare
infra/k8s/       Kustomize bases and overlays, Argo CD applications
docs/            product, UX, engineering, backlog, runbooks, ADRs
```

## How this project works

It is run by one person, deliberately operating as if it had a small product organisation with
separated responsibilities: Product, UX, Frontend, Backend/DevOps. There is **no QA role** — the
engineer implementing a change owns its tests, and **TDD is mandatory**.

The rules that actually bind:

- A frontend story is **not ready** until a committed UX specification exists for it
  ([`docs/ux/`](docs/ux/README.md)).
- A commit that adds behaviour without a test that failed first is not acceptable
  ([`docs/engineering/testing.md`](docs/engineering/testing.md)).
- Work proceeds in **vertical slices** — product → UX → backend → frontend → integration — never
  weeks of backend followed by weeks of frontend.
- The "do not build yet" list is binding. Changing it requires an ADR.

## Documentation

[`docs/`](docs/README.md) — start there.
