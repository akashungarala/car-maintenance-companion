# ADR-0007: Frontend on Vercel Hobby, outside the cluster

**Status:** Accepted · 2026-09-07

## Context

Vercel's Hobby plan is free and offers the best Next.js developer experience available. Its terms
restrict it to **non-commercial personal use**; Vercel defines commercial usage broadly, explicitly
including deployments intended for the financial gain of anyone involved and sites built by a paid
person. A pre-revenue startup intending to monetise is arguably in scope.

The alternatives are Vercel Pro ($20/mo, breaks the $0 target) or running Next.js as a container in
the k3s cluster (free, ToS-clean, and keeps one deployment model — but forgoes Vercel's DX and edge
network).

## Decision

Deploy the frontend to **Vercel Hobby**, as the founder's explicit choice, while treating this
project as a learning/portfolio platform.

## Consequences

**Good:** best-in-class Next.js DX, preview deployments per PR, edge CDN, zero cost, no cluster
resources consumed on a 2-OCPU node.

**Bad — stated plainly rather than buried:**

1. If this monetises, we are out of terms and must move to Pro or into the cluster.
2. The Phase 0 acceptance criterion "the application is deployed to Kubernetes" becomes
   **backend + worker + database + observability on Kubernetes; frontend on Vercel**. We do not
   claim otherwise.
3. Frontend→backend traces cross the public internet rather than staying in-cluster, so
   `traceparent` propagation must survive Vercel's edge and CORS must be configured deliberately.

**Mitigation:** `apps/web` ships a production Dockerfile from F3, and a `web` Kustomize overlay is
written but scaled to zero. Migrating into the cluster is then a config change and a DNS switch,
not a rewrite.

**Reversal cost:** hours, by design.
