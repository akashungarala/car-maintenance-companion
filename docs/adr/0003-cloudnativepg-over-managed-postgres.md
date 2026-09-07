# ADR-0003: CloudNativePG in-cluster, not managed Postgres

**Status:** Accepted · 2026-09-07

## Context

The obvious free managed option is Neon. Its free plan allows **100 compute-hours per month per
project** and 0.5 GB of storage; when compute-hours are exhausted the project's compute is
**suspended until the next billing period**. Compute scales to zero after 5 minutes idle, so a
low-traffic app may stay under — but a production database whose availability depends on not
exceeding a monthly compute budget has an outage mode we neither control nor can page on.

Supabase's free tier pauses projects after a week of inactivity, which is the same class of problem.

## Decision

Run **PostgreSQL 17 in-cluster via the CloudNativePG operator**, with continuous WAL archiving and
base backups to **Cloudflare R2** (10 GB free, zero egress fees).

## Consequences

**Good:** no compute-hour cliff, no storage cap beyond the node's disk, genuinely $0. The operator
provides PITR, failover, connection pooling and backup CronJobs, so this is real Postgres
operations rather than a hand-rolled StatefulSet. It also makes the Kubernetes foundation
substantive — StatefulSets, PVCs, probes and scheduled jobs all become real rather than decorative.

**Bad:** we own backup correctness, upgrades and disk headroom. Single-node k3s means a node loss is
a database outage; we accept that at this stage and mitigate with off-cluster backups.

**Non-negotiable consequence:** a backup that has never been restored is not a backup. A restore
drill into a scratch namespace is an explicit exit criterion of slice F6 and is repeated quarterly.
The "backup stale > 26h" alert exists for the same reason.

**Reversal cost:** low. `pg_dump`/restore into any managed provider.
