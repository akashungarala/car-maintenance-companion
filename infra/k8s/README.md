# Kubernetes

Everything above the bare k3s node is installed from this directory by Argo CD (ADR-0008).

```
bootstrap/      applied by hand exactly once — Argo CD itself, plus the root Application
applications/   Argo CD Applications, watched by the root app ("app of apps")
platform/       cluster infrastructure: cert-manager, Sealed Secrets, issuers
apps/           the product's own workloads
```

## Why there is a manual step at all

Argo CD cannot install itself. Something has to create the first controller, and that is the only
`kubectl apply` in the whole system. After it, the root Application points Argo CD at
`applications/`, and every subsequent change — including changes to Argo CD's own configuration —
arrives through git.

See [`bootstrap/README.md`](bootstrap/README.md).

## Branches

| Branch   | Written by          | Meaning                             |
| -------- | ------------------- | ----------------------------------- |
| `main`   | humans, through PRs | the source of truth for code        |
| `deploy` | CI only             | what production is actually running |

Argo CD watches `deploy` for the application. CI merges `main` into it and pins the image tag to the
commit's SHA, so the branch is a literal, readable history of every deployment.

`main` is fully protected with no bypass actor — nothing automated can push to it, and that property
is worth more than the convenience of committing the tag there. GitHub only allows a GitHub Actions
bypass on organisation-owned repositories, so on a personal repo the alternatives were a deploy key
or a personal access token with elevated rights. A machine-owned branch needs neither.

**Rolling back is `git revert` on `deploy`.** No kubectl, no registry surgery, and the revert itself
is the audit record.

## The rule this directory exists to enforce

No human runs `kubectl apply` to deploy. CI builds an image, pushes it, and commits a tag bump;
Argo CD notices and reconciles. There is no kubeconfig in any GitHub secret, and the API server is
not reachable from the internet at all (see `infra/tofu/README.md`).
