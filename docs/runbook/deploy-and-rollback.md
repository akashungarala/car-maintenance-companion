# Deploy and rollback

## How a deploy happens

```
PR merged to main
  → CI passed (lint, types, tests, coverage, audit, Trivy, image smoke)
  → Publish   (arm64 images to GHCR, tagged with the commit SHA)
  → Deploy    (merge main into `deploy`, pin newTag to that SHA, push)
  → Argo CD reconciles `deploy`
  → rolling update, gated by readiness
```

No human runs `kubectl`. There is no kubeconfig in any GitHub secret, and the Kubernetes API is not
reachable from the internet at all.

**`main` is never written by a machine.** GitHub only allows a GitHub Actions bypass actor on
organisation-owned repositories, so on a personal repo automating a push to a protected `main` would
have required a deploy key or an elevated PAT. A machine-owned `deploy` branch needs neither, and
doubles as a readable history of what production has run.

## Rolling back

Revert the deploy commit on the `deploy` branch. That is the whole procedure.

```bash
git clone --branch deploy <repo> /tmp/rollback && cd /tmp/rollback
git revert --no-edit HEAD          # or the specific deploy commit
git push origin deploy
```

Argo CD picks it up and rolls back. To roll forward again, revert the revert.

### Timing, measured rather than assumed

A drill on 2026-09-08 rolled back from one image to the previous one:

| Stage                     | Time     |
| ------------------------- | -------- |
| push → Argo notices       | ~207s    |
| rolling update to healthy | ~5s      |
| **total**                 | **212s** |

Almost all of it is Argo CD's default 180-second reconciliation poll, not the rollout. If that is
ever too slow, the options are:

- **Shorten `timeout.reconciliation`** in `argocd-cm` — simple, costs a little more polling.
- **A push webhook from GitHub to Argo** — near-instant, but requires exposing the Argo CD API to
  the internet, which contradicts keeping the cluster unreachable. Not worth it for a three-minute
  worst case.

### When you need it faster than that

For a genuine emergency, scaling down is immediate and needs no git round-trip:

```bash
eval "$(scripts/cluster-access.sh)"
kubectl -n cmc scale deploy/api --replicas=0
```

Argo CD has `selfHeal: true` and **will scale it back up**, which is correct behaviour and worth
knowing before relying on this. To make it stick, disable auto-sync first:

```bash
kubectl -n argocd patch application api --type merge -p '{"spec":{"syncPolicy":null}}'
```

Remember to restore the sync policy afterwards, or the next deploy will silently do nothing.

## Checking what is actually running

```bash
eval "$(scripts/cluster-access.sh)"
kubectl -n argocd get applications
kubectl -n cmc get pods
kubectl -n cmc get deploy api -o jsonpath='{.spec.template.spec.containers[0].image}'
```

The image tag is a commit SHA, so it maps directly back to a commit on `main`.

---

# Database

## Migrations

`alembic upgrade head` runs as an Argo CD **PreSync hook** before the Deployment is touched. A
PreSync hook must complete successfully before the rest of the sync begins, so a failed migration
stops the deployment rather than racing an image that expects a schema which is not there.

This has been observed working: a broken migration job left the previous pods serving and the new
ones never rolled.

The job runs the same image being deployed, so the migrations applied are exactly the ones that
shipped with the code.

```bash
eval "$(scripts/cluster-access.sh)"
kubectl -n cmc get jobs
kubectl -n cmc logs -l app.kubernetes.io/name=api-migrate
kubectl -n cmc exec cmc-db-1 -- psql -U postgres -d cmc -tAc "select version_num from alembic_version"
```

## Backups

Continuous WAL archiving plus a nightly base backup to OCI Object Storage, retained 14 days by
Barman. The bucket deliberately has neither versioning nor a retention rule — both would fight
Barman for control of the lifecycle (see `infra/tofu/storage.tf`).

```bash
kubectl -n cmc get backup
kubectl -n cmc get cluster cmc-db \
  -o jsonpath='{.status.firstRecoverabilityPoint} .. {.status.lastSuccessfulBackup}{"\n"}'
```

## Restore drill

**A backup that has never been restored is not a backup** (ADR-0003). Run this quarterly, and after
any change to backup configuration.

```bash
eval "$(scripts/cluster-access.sh)"
scripts/restore-drill.sh
```

It restores the latest backup into a scratch namespace, prints the marker row it recovered, and
tears the namespace down — including on failure.

To make the drill meaningful, write a fresh marker first and force a backup that contains it:

```bash
MARKER="drill-$(date -u +%Y%m%dT%H%M%SZ)"
kubectl -n cmc exec cmc-db-1 -- psql -U postgres -d cmc -c \
  "INSERT INTO restore_drill (marker) VALUES ('$MARKER');"
kubectl -n cmc create -f - <<YAML
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata: { generateName: drill-, namespace: cmc }
spec: { cluster: { name: cmc-db } }
YAML
```

### Result of the last drill

|                       |                          |
| --------------------- | ------------------------ |
| Date                  | 2026-09-08               |
| Restored into         | `cmc-restore-drill`      |
| Time to verified data | **44s**                  |
| Marker recovered      | `drill-20260908T125933Z` |

### Known future work

CloudNativePG 1.30 warns that native Barman Cloud backup and recovery is **deprecated and removed in
1.31.0**, in favour of the Barman Cloud Plugin. The operator is pinned, so nothing breaks until it is
deliberately upgraded — but the migration must happen before that bump, and the restore drill is how
it gets verified.

## Rollback drill

Executed, not described. `./scripts/rollback-drill.sh` reverts the tag bump on
the `deploy` branch, waits for the API to come back healthy on the previous
image, then rolls forward again.

Measured on 2026-09-09:

| Direction                  | Time to healthy |
| -------------------------- | --------------- |
| Rollback to previous image | **18s**         |
| Roll forward again         | **17s**         |

Both include triggering the Argo sync, which is what an operator would do
rather than waiting for the poll interval. Left alone, Argo picks the change up
within three minutes.

Only the image tag is reverted. Manifests stay as they are, because migrations
are expand/contract: the previous image runs against the current schema, and
rolling code back must never require rolling schema back.

Run it after any change to the deploy pipeline. A rollback path that has never
been exercised is a plan, not a capability.

## Testing an alert without leaving a ghost

To prove an alert path end to end, create a temporary rule that fires, then **clear its condition
while the rule still exists** — raise the threshold past the value the query returns. That produces
a real resolved notification.

Do not finish by deleting a rule while it is firing. Deletion removes it from the alertmanager
without emitting a resolved notification, so the alert never clears: it simply stops existing.
Discord messages are static, so the firing message stays in the channel looking like an open
incident indefinitely. Delete the rule only once it reads `inactive`.

Delivery can be checked without reading Discord:

```
grafanacloud_instance_alertmanager_notifications_total         # must increase
grafanacloud_instance_alertmanager_notifications_failed_total  # must not
```

Both are on the `grafanacloud-usage` datasource. A firing alert routed to the wrong receiver still
increments the first, so check the receiver too:

```
GET /api/alertmanager/grafana/api/v2/alerts   ->  receivers: ['discord']
```

## Cloudflare origin lock

80 and 443 accept connections only from Cloudflare's published IPv4 ranges
(`infra/tofu/cloudflare_origin.tf`). The list is fetched at apply time rather
than hardcoded, because Cloudflare adds ranges occasionally and a stale list
fails in the worst way: visitors routed through a new range are blocked while
everything looks healthy from here.

**Re-run `tofu apply` periodically** — that is what refreshes the list. Nothing
detects drift automatically: doing so would need OCI credentials in CI, which
is a larger exposure than the problem it solves.

The apply refuses if Cloudflare publishes fewer than 10 ranges or the fetch
fails. An empty list would generate zero ingress rules and take the site off
the internet, so failing loudly is the correct outcome.

Breaking glass, if Cloudflare itself is the problem:

```
tofu apply -var 'http_ingress_cidrs=["0.0.0.0/0"]'
```

Set it back to `null` afterwards. While it is open, `CF-Connecting-IP` becomes
forgeable and the rate limiter can be bypassed by anyone who sets that header.

IPv4 only, deliberately: the origin has no IPv6 address, so Cloudflare always
reaches it over IPv4 regardless of how the visitor arrived.
