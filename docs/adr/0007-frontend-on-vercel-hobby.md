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

## Observed cost, 2026-09-09 and 2026-09-10

**Corrected 2026-09-10.** The first version of this note said frontend changes "stall for up to a
day". That was too gentle, and it was based on reading the wrong signal.

The limit applies to **production** deployments only. Preview deployments from pull requests keep
working, so every PR check reports `Vercel: pass — Deployment has completed` and the frontend
appears to be shipping. It is not. The production alias -- which the portfolio proxies to -- stays
pinned to whatever deployed before the limit was hit.

That combination is the problem: a green check on every pull request, a stale site, and nothing
anywhere saying so. It was found by loading the live page and noticing it showed a screen from two
epics ago, not by any alert or failing build. The signal that would have said so is on the _main_
commit rather than the PR:

```
gh api repos/<owner>/<repo>/commits/<sha>/status
  Vercel: failure — Deployment rate limited — retry in 24 hours.
```

Worse, every merge re-attempts and re-fails, so a project that merges small PRs often -- which this
one does deliberately -- may never leave the window.

## Original note

Vercel Hobby rate-limits **deployments**, not just bandwidth. During E2 the account was locked out
for 24 hours after a day of ordinary work — every merge to `main` triggers a frontend deployment,
and this project merges often by design.

This was not in the plan's assessment of the tier, which considered the commercial-use terms and
the absence of a cost, and missed that the limit is on how often you may ship.

**What it costs:** frontend changes stall for up to a day. Backend deploys go through Argo CD and
are unaffected, so the API and worker continue shipping normally — the two halves of the system
now have materially different deployment cadences, which is a property worth remembering when a
frontend change and a backend change need to land together.

**What it does not cost:** availability. The previously deployed frontend keeps serving.

**Mitigations, in order of preference:** batch frontend changes rather than merging each one
separately; or move the frontend into the cluster using the containerised image and dormant
overlay already maintained for exactly this reason, which removes the limit entirely at the cost
of the Vercel CDN.
