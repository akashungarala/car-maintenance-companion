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
