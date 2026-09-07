# Phase 0 — Production Foundation

**Goal:** prove the entire production platform before the first product feature exists.

At the end of Phase 0 the visible application is exactly: the frontend says **"Hello World"** and
the backend serves **`GET /health`**. Everything else built here is infrastructure, delivery,
testing, security and observability.

**Why this order.** Retrofitting observability, migrations and deployment onto a working prototype
is where most solo projects accumulate the debt they never repay. Building the platform first costs
more up front and nothing afterwards.

## Slices

Each slice is independently mergeable and deployable, and ends green in CI.

| ID     | Slice                                                                                    | Depends on | Status |
| ------ | ---------------------------------------------------------------------------------------- | ---------- | ------ |
| **F1** | Monorepo scaffold, tooling, CI skeleton, docs & ADR tree                                 | —          | Done   |
| **F2** | `api`: FastAPI, `/health`, `/ready`, structlog, settings, arm64 Dockerfile               | F1         | Next   |
| **F3** | `web`: Next.js Hello World, Vitest, Playwright smoke, Vercel deploy                      | F1         | Todo   |
| **F4** | OpenTofu: Oracle Cloud VM + network, Cloudflare DNS, k3s, Traefik, cert-manager          | F1         | Todo   |
| **F5** | Argo CD, Kustomize base + prod overlay, Sealed Secrets, `api` live with probes           | F2, F4     | Todo   |
| **F6** | CloudNativePG, Alembic migration Job, R2 backups, **restore drill**                      | F5         | Todo   |
| **F7** | Redis, ARQ worker, CronJob enqueuing a heartbeat job (no product logic)                  | F5, F6     | Todo   |
| **F8** | OTel → Collector → Grafana Cloud, Alloy, 4 dashboards, 7 alerts → Discord                | F5, F7     | Todo   |
| **F9** | Rate limiting, security headers, image/dependency scanning, **rollback drill**, runbooks | F8         | Todo   |

**Critical path:** F1 → F2 → F4 → F5 → F6 → F8 → F9
**Parallel:** F3 alongside F2/F4 · dashboards alongside F7 · docs and ADRs throughout

> F4 should start early despite sitting mid-path: Oracle Ampere A1 capacity is frequently
> unavailable at provision time and acquisition may take several retries over days (risk R2).

---

## F1 — Monorepo scaffold (done)

**Delivered**

- pnpm workspace (Node 22 LTS pinned) + uv workspace (Python 3.13)
- Centralised tooling: ruff (incl. bandit security rules), mypy `--strict`, pytest, coverage
  gate at 85% with a ratchet, prettier
- `make check` runs exactly what CI runs
- CI skeleton: `backend`, `frontend`, `security` jobs behind a single aggregate `ci-passed` gate,
  so a new job cannot silently become non-blocking
- Secret defence in depth: `gitleaks` in pre-commit **and** CI, `detect-private-key`,
  `.gitignore` denies `.env`/`*.key`/`kubeconfig*` while permitting Sealed Secrets
- Dependabot for actions, npm, uv and docker
- PR template enforcing the Definition of Done
- Docs tree, UX process + specification template, and **ADRs 0001-0010**

**Acceptance**

- [x] `make check` passes locally
- [x] `uv sync --all-packages` resolves; package importable; mypy strict clean
- [x] Coverage gate enforced (100% on the scaffold)
- [x] Ten ADRs recording every locked decision, including rejected alternatives

**Deliberately not here:** any FastAPI or Next.js code. `apps/web` is a workspace placeholder whose
scripts are honest no-ops until F3.

---

## F2 — Backend service skeleton

**Scope:** FastAPI app; `GET /health` (liveness, process-only) and `GET /ready` (readiness, checks
dependencies); `structlog` JSON logging with request/trace ID middleware; typed settings via
pydantic-settings; multi-stage arm64 Dockerfile running as non-root; `docker compose` for local dev.

**TDD:** the first commit is a failing test asserting `GET /health` returns `200 {"status":"ok"}`.

**Acceptance**

- [ ] `/health` returns 200 and **never** touches Postgres or Redis — a database blip must not
      trigger a pod-kill cascade
- [ ] `/ready` reports per-dependency status and returns 503 when any is unavailable
- [ ] Every log line is JSON carrying `timestamp, service, env, level, request_id, method, route,
status, duration_ms`
- [ ] A redaction filter drops `authorization` headers, tokens and full email addresses
- [ ] Image builds for `linux/arm64`, runs as non-root, and passes a Trivy scan with no HIGH/CRITICAL
- [ ] Coverage ≥ 85%

## F3 — Frontend skeleton

**Scope:** Next.js App Router + TypeScript strict + Tailwind + shadcn/ui; a Hello World page;
Vitest + React Testing Library; MSW wiring; one Playwright smoke test; Vercel project and deploy;
a production Dockerfile and a `web` Kustomize overlay scaled to zero (the ADR-0007 escape hatch).

**Acceptance**

- [ ] `tsc --noEmit` clean under `strict`
- [ ] Vitest and Playwright both run in CI; coverage ≥ 80%
- [ ] Deployed and publicly reachable; PR preview deploys work
- [ ] Security headers set (CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`)

## F4 — Infrastructure as code

**Scope:** OpenTofu for the Oracle Cloud VM (Ampere arm64), VCN, security lists and the Cloudflare
DNS zone; k3s install; Traefik ingress; cert-manager with Let's Encrypt; Cloudflare proxy enabled so
the origin IP is hidden. Remote state, not local.

**Acceptance**

- [ ] `tofu apply` from scratch produces a working cluster with no manual steps
- [ ] Capacity-retry documented for A1 unavailability (risk R2)
- [ ] TLS valid; HTTP redirects to HTTPS; origin IP not publicly resolvable
- [ ] Hetzner migration path documented and costed (ADR-0002)

## F5 — GitOps delivery

**Scope:** Argo CD; Kustomize base + `prod` overlay; Sealed Secrets controller; the `api` Deployment
with liveness, readiness **and** startup probes, resource requests/limits and an HPA; GHCR image
push and automated tag bump from CI.

**Acceptance**

- [ ] Merge to `main` reaches production with no human `kubectl`
- [ ] No kubeconfig or cluster credential exists in any GitHub secret
- [ ] All three probe types configured and passing
- [ ] `git revert` of the tag bump rolls back, and the rollback is timed

## F6 — Database

**Scope:** CloudNativePG cluster; Alembic wired with an initial empty revision; migration Job
ordered ahead of the rollout by Argo sync-wave; WAL archiving and base backups to Cloudflare R2;
`/ready` gains a DB connectivity and migration-version check.

**Acceptance**

- [ ] Migrations run automatically before the new image serves traffic
- [ ] `alembic upgrade head` and `downgrade` round-trip verified in CI
- [ ] **Restore drill:** a backup is restored from R2 into a scratch namespace and verified.
      A backup that has never been restored is not a backup (ADR-0003)
- [ ] Backup age is a monitored metric with a 26-hour staleness alert

## F7 — Async foundation

**Scope:** Redis; ARQ worker deployment; a Kubernetes CronJob enqueuing a **heartbeat job only**;
retry policy, dead-letter handling and idempotency keys established as patterns.

**No product logic.** The heartbeat exists to prove the async path, its tracing and its dashboards
before any real job depends on them.

**Acceptance**

- [ ] CronJob enqueues; worker consumes; the job appears in traces linked to the enqueue span
- [ ] A deliberately failing job retries, then lands in the dead-letter list
- [ ] Queue depth and job duration are exported metrics

## F8 — Observability

**Scope:** OpenTelemetry SDK in `api` and `worker` (FastAPI, SQLAlchemy, httpx, Redis, ARQ
auto-instrumentation); OTel Collector as the sole egress; Grafana Alloy for Kubernetes metrics and
pod logs; four dashboards; seven alerts routed to Discord.

**Cardinality is a design constraint, not an afterthought.** Grafana Cloud free allows 10,000
active series and a default Kubernetes scrape exceeds that alone. Therefore: allowlist relabelling
rather than drop-lists; metrics labelled on the **route template** (`/vehicles/{id}`) never the raw
path; `request_id`, `trace_id`, `user_id`, `vin` and `email` are **never** metric labels; ~6
histogram buckets; and a CI check that fails above 7,000 series.

**Acceptance**

- [ ] A single request produces a metric, a log line carrying its `trace_id`, and a trace showing
      `api → postgres` spans — and the log links to the trace in Grafana
- [ ] Trace context propagates browser → api → worker (injected into the job payload)
- [ ] Four dashboards live: service health, infrastructure, database, async
- [ ] Seven alerts fire correctly when provoked and reach Discord
- [ ] Exported series count below 7,000

## F9 — Hardening

**Scope:** Redis-backed rate limiting (auth 5/min/IP, API 100/min/user); security headers at
Traefik; Trivy image scanning and `pip-audit`/`npm audit` as blocking gates; a rollback drill; and
the runbooks.

**Acceptance**

- [ ] Rate limits enforced and observable
- [ ] No HIGH/CRITICAL vulnerabilities in shipped images
- [ ] Rollback drill executed and timed, with the procedure written down
- [ ] Runbooks exist for: deploy, rollback, database restore, incident triage

---

## Phase 0 exit — the acceptance demo

Phase 0 is complete when this runs end-to-end in one sitting, with evidence captured in
`docs/runbook/phase-0-acceptance.md`:

1. Trivial change on a branch → PR opened
2. CI runs: lint, types, backend tests, frontend tests, coverage, dependency audit, Trivy,
   OpenAPI contract diff, migration round-trip
3. Both builds pass; arm64 images built natively
4. Merge → images pushed to GHCR → image tag bump committed
5. Argo CD syncs; the migration Job runs first; rolling update respects probes
6. `/health` returns 200; `/ready` reports database and Redis healthy
7. `kubectl get pods` shows liveness, readiness and startup probes passing
8. In Grafana: the request appears as a **metric**; its **log line** carries a `trace_id`; that link
   opens the **trace** showing api → Postgres spans; the heartbeat job appears as a linked trace
9. Kill a pod → the crash-loop alert fires → a Discord message arrives
10. `git revert` the tag bump → Argo CD rolls back → health restored, duration recorded
11. A database backup is restored from R2 into a scratch namespace and verified
12. `gitleaks` confirms no secret exists in plaintext anywhere in the repository

**Only when all twelve pass does story E1-001 begin.**
