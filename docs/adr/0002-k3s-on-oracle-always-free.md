# ADR-0002: k3s on Oracle Cloud Always Free

**Status:** Accepted · 2026-09-07

## Context

Kubernetes is a deliberate goal of this project, and the target running cost is $0/month. Surveying
the options: managed control planes (GKE/EKS/AKS/DOKS) all cost money or expire. Oracle Cloud
Always Free is the only provider offering a durable, no-expiry allocation capable of running a real
cluster.

Oracle **silently halved** the Always Free Ampere A1 allocation from 4 OCPU / 24 GB to
2 OCPU / 12 GB, effective 15 June 2026, with no announcement or customer notification. The
remaining 2 OCPU / 12 GB still comfortably fits our workload (~2.5 GB resident), but the episode
establishes that this provider will change terms unilaterally and without warning.

## Decision

Run **k3s** (not OKE) on Oracle Cloud Always Free ARM instances, provisioned by OpenTofu.

k3s over OKE because it is a single binary, has a far smaller control-plane footprint on a 2-OCPU
node, and — critically — is **provider-agnostic**, so the migration path below is real.

## Consequences

**Good:** genuinely $0; a real multi-node-capable cluster; full control; ships with Traefik and a
local-path storage provisioner.

**Bad:** we own control-plane availability — there is no managed SLA. A1 capacity is frequently
unavailable at provision time in popular regions, so provisioning needs a retry loop. Oracle may
reduce or reclaim the allocation again (see risk R1).

**Mitigation, and the reason for k3s:** every manifest is plain Kubernetes and every resource is
OpenTofu-managed, so migrating to a Hetzner CAX21 (4 vCPU / 8 GB, ~€6.49/mo) is a documented
half-day of work requiring no manifest changes. We plan for that migration without paying for it.

**Reversal cost:** half a day, by design.
