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

## The rule this directory exists to enforce

No human runs `kubectl apply` to deploy. CI builds an image, pushes it, and commits a tag bump;
Argo CD notices and reconciles. There is no kubeconfig in any GitHub secret, and the API server is
not reachable from the internet at all (see `infra/tofu/README.md`).
