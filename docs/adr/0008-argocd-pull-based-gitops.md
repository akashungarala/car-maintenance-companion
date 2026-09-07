# ADR-0008: Argo CD pull-based GitOps

**Status:** Accepted · 2026-09-07

## Context

CI must deploy to the cluster. The common approach is push-based: CI holds a kubeconfig in a
repository secret and runs `kubectl apply`. That requires the Kubernetes API server to be reachable
from GitHub's runners and puts long-lived cluster-admin credentials in CI — on a **public**
repository (ADR-0001), where any workflow-injection bug is a full cluster compromise.

## Decision

**Argo CD** running in-cluster, watching the repo and reconciling. CI's only deployment
responsibility is building images, pushing to GHCR, and committing a Kustomize image tag bump.

## Consequences

**Good:** no inbound access to the API server; no cluster credentials in GitHub. Git is the single
source of truth, so cluster state and repo state cannot silently diverge. `git revert` of the tag
bump _is_ the rollback. Sync waves order the migration Job before the rollout. The UI gives a solo
operator real deployment-health visibility.

**Bad:** ~500 MB resident on a 12 GB node. One more component to upgrade and secure — its admin
password is a Sealed Secret and its UI is not publicly exposed. Deploys are eventually consistent
(reconcile loop), so "merged" and "live" are distinct moments that the pipeline must report
separately.

**Rejected alternative:** Flux is lighter and would also work. Argo's UI is worth the extra memory
for a solo founder who will be debugging deploys alone at unhelpful hours.
