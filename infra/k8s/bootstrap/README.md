# Bootstrap

The one manual step in the entire delivery pipeline. Run once, on a new cluster.

```bash
eval "$(scripts/cluster-access.sh)"
scripts/bootstrap-cluster.sh
```

It runs in two phases because it has to: the root Application is a custom resource whose CRD is
installed by the same manifests, so a single `kubectl apply -k` always fails on a fresh cluster with
`no matches for kind "Application"`. The script installs Argo CD, waits for the CRD to register,
then applies the root Application.

That installs Argo CD and the root Application. From then on Argo CD manages everything in
`applications/`, including itself — so upgrading Argo CD is a git commit, not another manual apply.

## After it settles

```bash
kubectl -n argocd get pods
kubectl -n argocd get applications
```

The admin password is generated into a secret. Read it, log in through a port-forward, then delete
the secret — Argo CD treats its presence as "initial password not yet acknowledged":

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

The UI is deliberately **not** exposed through the ingress. It is a cluster-admin surface with no
business being on the public internet; a port-forward over the existing SSH tunnel is enough for one
operator.

## Resource shape

This node has 2 CPUs and 12 GB. The overlay trims Argo CD accordingly:

- **Dex is scaled to zero** — it exists for SSO against an external identity provider, and there is
  one local admin.
- **ApplicationSet and notifications controllers are scaled to zero** — no generated applications,
  and alerting goes through Grafana (F8), not Argo.

All three can be scaled back up by editing this overlay; they are disabled for resource reasons,
not deleted.
