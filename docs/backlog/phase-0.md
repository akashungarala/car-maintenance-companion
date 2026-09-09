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
| **F2** | `api`: FastAPI, `/health`, `/ready`, structlog, settings, arm64 Dockerfile               | F1         | Done   |
| **F3** | `web`: Next.js Hello World, Vitest, Playwright smoke, Vercel deploy                      | F1         | Done   |
| **F4** | OpenTofu: Oracle Cloud VM + network, Cloudflare DNS, k3s, Traefik, cert-manager          | F1         | Done   |
| **F5** | Argo CD, Kustomize base + prod overlay, Sealed Secrets, `api` live with probes           | F2, F4     | Done   |
| **F6** | CloudNativePG, Alembic migration Job, R2 backups, **restore drill**                      | F5         | Done   |
| **F7** | Redis, ARQ worker, CronJob enqueuing a heartbeat job (no product logic)                  | F5, F6     | Done   |
| **F8** | OTel → Collector → Grafana Cloud, agent, 4 dashboards, 7 alerts → Discord                | F5, F7     | Done   |
| **F9** | Rate limiting, security headers, image/dependency scanning, **rollback drill**, runbooks | F8         | Next   |

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

**Delivered**

- FastAPI application factory with typed settings (`pydantic-settings`, `CMC_` prefix)
- `GET /health` — liveness, provably dependency-free
- `GET /ready` — readiness registry running checks concurrently under a timeout,
  returning 503 with per-dependency detail. Empty in F2; F6 registers Postgres and
  F7 registers Redis
- `structlog` JSON logging, with stdlib records (uvicorn) routed through the same
  renderer so no plain-text line reaches the log pipeline
- Redaction processor dropping authorization/token/secret keys and masking emails
- Request-id middleware binding correlation into log context and echoing
  `X-Request-ID`; route logged as a **template**, never a raw path
- Multi-stage arm64 Dockerfile, non-root uid 10001, 54 MB; `compose.yaml`
- CI `image` job on a native arm64 runner: build, Trivy scan, container smoke test

**Acceptance**

- [x] `/health` returns 200 and never touches Postgres or Redis — asserted by a test
      that registers a spy check and proves it is not called
- [x] `/ready` reports per-dependency status and returns 503 when any is unavailable,
      including when a check raises or hangs
- [x] Every log line is JSON carrying the required correlation fields
- [x] Redaction verified for authorization headers, token/secret keys and emails
- [x] Image builds for `linux/arm64`, runs as non-root, Trivy gate in CI
- [x] Coverage 100% (gate 85%)

---

## F3 — Frontend skeleton

**Scope:** Next.js App Router + TypeScript strict + Tailwind + shadcn/ui; a Hello World page;
Vitest + React Testing Library; MSW wiring; one Playwright smoke test; Vercel project and deploy;
a production Dockerfile and a `web` Kustomize overlay scaled to zero (the ADR-0007 escape hatch).

**Acceptance**

- [ ] `tsc --noEmit` clean under `strict`
- [ ] Vitest and Playwright both run in CI; coverage ≥ 80%
- [ ] Deployed and publicly reachable; PR preview deploys work
- [ ] Security headers set (CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`)

**Delivered (code)**

- Next.js 16 App Router, TypeScript strict (plus `noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`), Tailwind 4
- Six Vitest + React Testing Library tests at 100% coverage (gate 80%), querying by accessible role
- MSW wired with `onUnhandledRequest: 'error'`, so a stray real network call in a test fails loudly
- Four Playwright tests against the **standalone production build**, asserting the rendered page,
  the security headers, the absence of `X-Powered-By`, and a 404 route
- Six security headers including a deliberately strict CSP — easier to start strict than to tighten
  later once third-party scripts exist
- Multi-stage arm64 Dockerfile, non-root uid 10001, 88 MB (the ADR-0007 escape hatch, built and
  smoke-tested in CI so it cannot rot while unused)
- CI: `image` job is now a matrix over `api` and `web`; frontend job builds and runs E2E

**Two dependencies deliberately pinned below latest** — TypeScript 6 (typescript-eslint has no TS 7
support) and ESLint 9 (`eslint-plugin-react` crashes on ESLint 10). Rationale recorded in
[`apps/web/README.md`](../../apps/web/README.md) so the bumps get rejected rather than re-attempted.

**Deferred by design:** the `web` Kustomize overlay moves to F5, which creates the Kustomize base —
an overlay with no base would be fiction. shadcn/ui is deferred to the first real component (E2)
rather than scaffolding unused code now.

**Deployed:** <https://car-maintenance-companion.vercel.app> — Root Directory `apps/web`, auto-deploy
on push to `main`, preview deploys per branch (guarded by Vercel Deployment Protection).

- [x] Deployed and publicly reachable, serving all six security headers through Vercel's edge
- [x] PR preview deploys work

**One trap worth remembering:** `output: 'standalone'` breaks Vercel. Its build pipeline emits trace
files (`next-server.js.nft.json`) that standalone never produces, so the build fails at
`onBuildComplete` _after_ compiling successfully — which reads like an infrastructure fault. It is
now opt-in via `BUILD_STANDALONE=1`, set only by the Dockerfile and the Playwright web server.

---

## F4 — Infrastructure as code

**Scope:** OpenTofu for the Oracle Cloud VM (Ampere arm64), VCN, security lists and the Cloudflare
DNS zone; k3s install; Traefik ingress; cert-manager with Let's Encrypt; Cloudflare proxy enabled so
the origin IP is hidden. Remote state, not local.

**Acceptance**

- [ ] `tofu apply` from scratch produces a working cluster with no manual steps
- [ ] Capacity-retry documented for A1 unavailability (risk R2)
- [ ] TLS valid; HTTP redirects to HTTPS; origin IP not publicly resolvable
- [ ] Hetzner migration path documented and costed (ADR-0002)

**Delivered (code)**

- OpenTofu for the VCN, internet gateway, route table, public subnet and security list
- Ampere A1 instance sized to the Always Free ceiling, with **variable validation** rejecting
  configurations that would silently make it billable (>2 OCPU, >12 GB, >180 GB boot)
- `admin_cidr` validation refusing `0.0.0.0/0` — SSH and the Kubernetes API are never
  internet-facing
- cloud-init installing a pinned k3s, hardening SSH, enabling unattended security upgrades, and
  inserting iptables ACCEPT rules **ahead of** Oracle's default REJECT (the most common reason an
  OCI instance looks unreachable on 80/443)
- Proxied Cloudflare DNS records for the app and API hostnames
- Remote state in Cloudflare R2; `.terraform.lock.hcl` committed for reproducible providers
- `scripts/oci-provision-retry.sh` walking availability domains for capacity (risk R2), stopping
  immediately on any non-capacity failure so real errors are not buried
- CI `infra` job running `tofu fmt -check` and `tofu validate` with no cloud credentials

**Applied.** Cluster live in `us-ashburn-1` AD-1: 2 OCPU / 12 GB Ampere, k3s v1.31.4+k3s1, node
Ready, all system components running including Traefik. Capacity was available on the first attempt
— the retry script was not needed, but stays for the rebuild that will eventually need it.

- [x] `tofu apply` from scratch produces a working cluster with no manual steps
- [x] Origin IP not publicly resolvable — both hostnames resolve to Cloudflare, and TLS terminates
      at the edge. Verified end to end: `https://garage.akashungarala.com` reaches Traefik and gets
      its 404, proving the security list, the host iptables rules and the Cloudflare proxy all work.

**Two bugs found by running it, both now fixed and verified**

1. `curl -sfL … | sh` installed nothing. DNS is unavailable for the first seconds of an OCI
   instance's life; curl failed silently, the pipe delivered an empty script, and `sh` succeeded on
   nothing. The node came up looking healthy with no Kubernetes on it.
2. The verification added to catch (1) then failed on a _healthy_ cluster — `kubectl wait` does not
   retry on NotFound and ran before the node registered. A check that cries wolf is worse than no
   check.

**Moved to F5:** cert-manager. Installing it by hand would contradict ADR-0008 — everything above
the cluster comes from git via Argo CD. F4 ends at a running, reachable k3s node.

**Deferred to F9:** narrowing 80/443 to Cloudflare's published IP ranges, so the origin cannot be
reached directly.

---

## F5 — GitOps delivery

**Scope:** Argo CD; Kustomize base + `prod` overlay; Sealed Secrets controller; the `api` Deployment
with liveness, readiness **and** startup probes, resource requests/limits and an HPA; GHCR image
push and automated tag bump from CI.

**Acceptance**

- [ ] Merge to `main` reaches production with no human `kubectl`
- [ ] No kubeconfig or cluster credential exists in any GitHub secret
- [ ] All three probe types configured and passing
- [ ] `git revert` of the tag bump rolls back, and the rollback is timed

**Delivered**

- Argo CD on the cluster, trimmed for 2 CPUs (dex, applicationset and notifications at zero), with
  an app-of-apps root Application so adding a component is adding a file
- Sealed Secrets controller at sync wave -1
- `api` deployed: 2 replicas, all three probe types, non-root, read-only root filesystem, all
  capabilities dropped, PodDisruptionBudget, HPA capped at 3
- CI publishes arm64 images to GHCR tagged with the commit SHA, then promotes `main` to a
  machine-owned `deploy` branch that Argo CD watches

**Acceptance**

- [x] Merge to `main` reaches production with no human `kubectl`
- [x] No kubeconfig or cluster credential exists in any GitHub secret — the Kubernetes API is not
      reachable from the internet at all
- [x] All three probe types configured and passing, 0 restarts
- [x] `git revert` rolls back, **timed at 212s** — of which ~207s is Argo CD's default 180s
      reconciliation poll, not the rollout. Recorded in
      [the runbook](../runbook/deploy-and-rollback.md) with the options for making it faster and why
      they were not taken.

**Why `main` is not the deploy branch.** GitHub only allows a GitHub Actions bypass actor on
organisation-owned repositories; the API rejects it on a personal repo. Writing to a protected
`main` would therefore have needed a deploy key or an elevated PAT — both of which trade away the
protection ADR-0011 just established. A machine-owned branch needs neither, and is a readable record
of what production ran.

**Two problems found by running it**

1. Bootstrap could not work in one `kubectl apply`: the root Application is a custom resource whose
   CRD the same manifests install. Split into two phases rather than told to retry, since a retry
   hides a predictable ordering problem behind a transient-looking error.
2. The overlay's default image tag was `latest`, which CI never publishes — pods sat in
   `ImagePullBackOff` on a tag that had never existed. The registry error was `not found` rather
   than `unauthorized`, which is how we know the GHCR package is publicly readable.

**Deferred to F9:** cert-manager. TLS already works — Cloudflare terminates at the edge and accepts
Traefik's default certificate at the origin. cert-manager's remaining value is enabling Cloudflare
_Full (strict)_ origin validation, which belongs with the other origin hardening in F9 (restricting
80/443 to Cloudflare's published ranges) rather than on its own.

---

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

**Delivered**

- CloudNativePG operator and a PostgreSQL 17 cluster, one instance — a second replica on a
  single-node cluster shares the node's fate and buys only memory pressure. Durability comes from
  WAL archiving off the node.
- Continuous WAL archiving and nightly base backups to OCI Object Storage, retained 14 days by
  Barman. R2 was the plan, but enabling it needs a card on file; OCI Always Free includes 10 GB and
  is S3-compatible.
- Alembic wired to application settings, with an initial empty revision. `env.py` refuses to run
  without a URL rather than defaulting — a silent default is how a migration lands on the wrong
  database.
- `/ready` reports the database; `/health` deliberately does not, so an outage removes pods from the
  Service without restarting them.
- OpenTofu state moved off a laptop into versioned object storage, closing the F4 risk.

**Acceptance**

- [x] Migrations run automatically before the new image serves traffic — a PreSync hook, which must
      _complete_ before the sync proceeds. Verified twice: once passing, and once failing, where the
      previous pods kept serving and the new ones never rolled.
- [x] `alembic upgrade head` and `downgrade base` round-trip verified in CI, against a real Postgres
      container rather than SQLite
- [x] **Restore drill passed** — the latest backup restored into a scratch namespace and the marker
      row recovered in **44 seconds**. Reusable as `scripts/restore-drill.sh`, documented in
      [the runbook](../runbook/deploy-and-rollback.md).
- [ ] Backup age as a monitored metric with a 26-hour staleness alert — deferred to F8, which is
      where metrics and alerting are built. The data is already exposed by the operator.

**Four problems found by running it**

1. **Deployments were silently skipped for backend-only changes.** GitHub propagates `skipped`
   transitively through `needs`, so once a path filter skipped the frontend job, everything
   downstream of `ci-passed` was skipped too — with a green tick on the run. The failure mode was
   exactly backwards: the more narrowly scoped the change, the less likely it was to deploy.
2. **The migration job ran from the wrong directory.** Alembic resolves `script_location` relative
   to the working directory, not the ini file, so it reported the migrations folder did not exist.
3. **gitleaks flagged the SealedSecret ciphertext.** A false positive, but confirmed as one before
   allowlisting — and the allowlist was then tested by planting a real key elsewhere. The first
   attempt used `[[allowlists]]`, which the action's gitleaks build parsed and silently ignored.
4. **The tunnel-reuse check tested only that the port was bound**, so it happily reused a dead
   forwarder that refused every connection.

**Known future work:** CloudNativePG 1.30 warns that native Barman Cloud backup and recovery is
removed in 1.31.0 in favour of the Barman Cloud Plugin. The operator is pinned, so nothing breaks
until it is deliberately upgraded — but the migration must happen before that bump, and the restore
drill is how it gets verified.

---

## F7 — Async foundation

**Scope:** Redis; ARQ worker deployment; a Kubernetes CronJob enqueuing a **heartbeat job only**;
retry policy, dead-letter handling and idempotency keys established as patterns.

**No product logic.** The heartbeat exists to prove the async path, its tracing and its dashboards
before any real job depends on them.

**Acceptance**

- [ ] CronJob enqueues; worker consumes; the job appears in traces linked to the enqueue span
- [ ] A deliberately failing job retries, then lands in the dead-letter list
- [ ] Queue depth and job duration are exported metrics

**Delivered**

- Redis with no persistence — everything in it is a queued job or a cache entry, both
  reconstructible. `noeviction` rather than `allkeys-lru`, because evicting queued jobs is worse
  than failing the write.
- ARQ worker as its own deployment (ADR-0005), one job at a time on a shared 2-CPU node.
- A CronJob enqueuing a heartbeat every 15 minutes. No product logic: from E5 this same schedule
  triggers the nightly projection recompute and digest fan-out.

**Acceptance**

- [x] CronJob enqueues, worker consumes — verified in the cluster: job `77f1d865…` enqueued at
      13:37:06 and executed at 13:37:07 with the same id in both log lines. That id is the
      correlation F8 formalises into a linked trace.
- [x] A deliberately failing job retries and lands in the dead-letter list — exercised against
      production Redis using the deployed image, without shipping a failing task. Attempts 1 and 2
      left the list clean; only the third recorded, with full context.
- [x] Queue depth is a first-class value and already logged on every enqueue; the metric and its
      alert land in F8.

**The bug worth remembering**

Every heartbeat came back `function 'heartbeat' not found`. The dead-letter wrapper set
`__name__` but not `__qualname__`, and ARQ resolves jobs by `__qualname__` — so the task registered
as `with_dead_letter.<locals>.wrapper`. The tests passed throughout, because they called the wrapper
directly and never went through registration: they proved the retry and dead-letter behaviour of a
job that could not be dispatched at all.

There is now a test asserting the name ARQ actually resolves, verified in both directions.

It also exposed a gap worth carrying into F8: the failure never reached the dead-letter list, because
ARQ could not find the function to run and fail. **A job that cannot be dispatched and a job that
fails are different states, and only the second leaves evidence.** Queue depth, not the dead-letter
list, is what would have caught this.

**Node headroom after this slice:** 8% CPU, 17% memory, no restarts — room for the observability
stack.

---

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

- [x] A single request produces a metric, a log line carrying its `trace_id`, and a trace
      (`trace_id=63da54d6…` observed in Loki alongside `route=__unmatched__`, the template rather
      than the raw path)
- [x] Trace context propagates CronJob → worker: enqueue trace `eda5abea…` matched the
      `traceparent` the worker received
- [x] Four dashboards live: service health, infrastructure, database, async
- [x] Seven alerts provisioned, all evaluating `health=ok`
- [ ] Alerts confirmed to reach Discord — the contact point and route are applied, but delivery has
      not been proven by firing one. An alert path that has never delivered is not a working alert
      path; this is the last open item.
- [x] Exported series count below 7,000 — **317** active, 6,683 of headroom, with a gate verified
      to fail (exit 1 below the limit, exit 2 when it cannot read the number at all)

**Deviation:** Grafana Alloy was replaced by a second OpenTelemetry Collector running as a
DaemonSet (ADR-0013). Alloy would also have required kube-state-metrics for restart counts; the
`contrib` image already deployed covers all three jobs with one technology.

**What this slice actually cost, and why.** Nine defects, none of which announced themselves —
every one was found by asking the running system what it had rather than trusting what was
configured:

| Defect                                         | How it presented                                                                          |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `deploy` skipped manifest-only changes         | Argo reported Synced/Healthy against a branch missing the change                          |
| ARQ Redis poll spans                           | 168 spans/min at idle, 7.2M/month with no users                                           |
| `/ready` probe spans                           | 48 spans/min of orphan roots; excluded from HTTP tracing, but the DB check inside was not |
| CronJob never propagated trace context         | `trace_carrier={}`; every job a fresh root trace                                          |
| Collector agent restart loop                   | Exit code **0**, so the pod read `1/1 Running` for 17 hours across 107 restarts           |
| Histogram buckets in seconds                   | Metric is milliseconds; 5ms ceiling made the p95 alert unfireable                         |
| Size histograms bucketed by latency boundaries | Bytes bucketed by milliseconds                                                            |
| Worker had no meter provider                   | `queue_depth` arrived, job metrics silently discarded                                     |
| `queue_depth` reported only every 15 min       | Series went stale; panel read "no data", not "empty queue"                                |

The pattern is consistent: none surfaced as an error. Everything was green throughout.

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
