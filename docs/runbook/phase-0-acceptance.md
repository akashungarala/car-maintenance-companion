# Phase 0 acceptance

Run end-to-end on **2026-09-09** against production. The change under test was a
version bump to `0.1.2` — deliberately trivial, but visible in `/health` and in
the OpenAPI document, so one commit exercises the deploy path and the
contract-diff gate together.

Eleven of twelve steps passed as written. One passed with a documented
limitation, explained under step 8.

---

## 1. Change on a branch, PR opened

Branch `phase0/acceptance`, PR **#78**. Four files: the API version, the web
package version, the generated-types package version, and the lockfile.

## 2. CI gates

| Gate                                                        | Result |
| ----------------------------------------------------------- | ------ |
| Format (repo-wide prettier)                                 | pass   |
| Backend: ruff, `mypy --strict`, pytest, coverage ≥ 85%      | pass   |
| Frontend: eslint, `tsc --noEmit`, vitest, build, Playwright | pass   |
| **API contract (generated types)**                          | pass   |
| Security: gitleaks, `pip-audit`, `pnpm audit --prod`        | pass   |
| Image: build, Trivy HIGH/CRITICAL, container smoke test     | pass   |
| CI passed (aggregate gate)                                  | pass   |

The migration up/down round-trip runs inside the backend test suite
(`test_upgrade_then_downgrade_round_trips`) rather than as a separate step.

**This step found a real gap.** The acceptance criteria named an "OpenAPI
contract diff", the plan specified committed generated types with a CI diff
check, and a comment in `main.py` claimed docs stayed enabled so the contract
pipeline was wired before there was a contract. None of it existed. It was
built and verified in both directions — change the API and the gate fails,
restore it and the gate passes — before the demo continued.

## 3. Native arm64 builds

`OS/Arch: linux/arm64` in both image builds, on `ubuntu-24.04-arm` runners. No
QEMU emulation.

## 4. Merge, publish, tag bump

Merged as `a0c77b9`. Both images present in GHCR at that digest. The deploy job
committed `2c5ce51 deploy: api a0c77b9…`, pinning the same tag in **both** the
API and worker overlays — they must never drift apart.

## 5. Argo sync, migration first, rolling update

```
api-migrate   Complete   1/1   5s
alembic.runtime.migration: Context impl PostgresqlImpl
deployment "api": 1 old replicas are pending termination...
deployment "api" successfully rolled out
```

The migration Job is a PreSync hook, so it completes before any new pod
receives traffic. The rollout replaced one replica at a time.

## 6. Health and readiness

```
/health  {"status":"ok","service":"cmc-api","version":"0.1.2"}
/ready   {"status":"ready","checks":{"database":{"healthy":true},"redis":{"healthy":true}}}
```

`0.1.2` is the change under test, so this is also the proof it reached
production.

## 7. Probes

Both API pods: `liveness, readiness, startup` defined; `Ready=True`,
`ContainersReady=True`, **0 restarts**.

## 8. One request: metric, log, trace

A single request to `/v1/acceptance-1788969676` produced all three:

- **Metric** — `http_server_duration_milliseconds_count` incremented
- **Log** — `event=http_request route=__unmatched__ status=404
trace_id=fb999bb516196ab5c1f1e1159686b046`. The route is the _template_, never
  the raw path
- **Trace** — that `trace_id` resolved in Tempo to the HTTP span, with a Redis
  `EVALSHA` span nested inside it (the rate limiter's script)

The heartbeat appears as a **linked** trace, not an orphan: one trace
containing `heartbeat.enqueue` (root, `app.cli`, in the CronJob) and
`heartbeat` (child, `app.tasks`, in the worker) — two processes, one trace.

**Limitation, stated plainly.** The criterion asks for `api → Postgres` spans.
Phase 0 has no product route that touches Postgres: the only database access is
the readiness probe, and that is deliberately excluded from instrumentation so
probe traffic does not bury real traces. The Redis span demonstrates the same
mechanism — a datastore client span nested under an HTTP span — through the
identical instrumentation path, and SQLAlchemy is wired the same way
(`instrument(app, engine=...)`). The Postgres span will appear with the first
route that queries the database, in E2. Recorded as a gap in the criterion
rather than a gap in the system, and deliberately not papered over.

## 9. Crash-loop alert reaches Discord

A throwaway `crashloop-drill` deployment was created in the `cmc` namespace —
the real workloads were left alone. Restart count climbed 1 → 5.

```
metric=5.6   rule=pending → firing        (after the 5m `for` duration)
alertname=Container restart loop  severity=page
receivers=['discord']  state=active
notifications_total 319 → 324    notifications_failed_total 0
```

Deleting the drill deployment cleared the alert on its own after ~6.5 minutes,
as the 15-minute increase window decayed — a real fire-and-resolve cycle, not a
rule deleted out from under the alertmanager.

Worth recording: two earlier attempts to inject this fault by patching the
**worker** deployment were reverted by Argo CD within seconds, including with
`selfHeal` disabled. GitOps self-healing working correctly is itself a result.

## 10. Rollback

```
ROLLBACK:     healthy on 831dcc84 after 23s
ROLL FORWARD: healthy on a0c77b98 after 18s
```

Only the image tag is reverted; manifests stay put. Migrations are
expand/contract, so the previous image runs against the current schema and
rolling code back never requires rolling schema back.

## 11. Database restore

`scripts/restore-drill.sh` restored the latest backup from OCI Object Storage
into a scratch namespace, verified the marker row `drill-20260908T125933Z`, and
tore the namespace down. The running database was never touched.

CloudNativePG warns that native Barman Cloud backup is removed in 1.31.0;
migrating to the Barman Cloud Plugin is required before that version bump.

## 12. No secrets in the repository

```
177 commits scanned. no leaks found
```

**Control:** the same configuration against a file containing a realistic
GitHub token and Stripe key reports `leaks found: 2`. A clean scan from a
scanner that never detects anything would prove nothing.

---

## Result

Phase 0 is complete. The production foundation is proven before the first
product endpoint exists, which was the entire point: every failure found during
Phase 0 — and there were many — was found against a Hello World, where the cost
of being wrong is a few minutes rather than a user's data.
