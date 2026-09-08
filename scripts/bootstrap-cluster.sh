#!/usr/bin/env bash
# Install Argo CD and hand the cluster over to git. Run once, on a new cluster.
#
# Two phases, unavoidably: the root Application is a custom resource whose CRD
# is installed by the same manifests. A single `kubectl apply -k` therefore
# always fails on a fresh cluster — the API server rejects the Application
# because its kind does not exist yet. Splitting it is the fix; retrying the
# whole apply would also work but hides a predictable ordering problem behind a
# transient-looking error.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> phase 1: Argo CD"
# Server-side apply: the bundled CRDs exceed the annotation size limit that
# client-side apply uses to store its last-applied state.
kubectl apply -k "$ROOT/infra/k8s/bootstrap" --server-side --force-conflicts \
  --prune=false 2>&1 | grep -vE "^Warning: metadata.finalizers" || true

echo "==> waiting for the Application CRD to register"
kubectl wait --for condition=established --timeout=120s crd/applications.argoproj.io

echo "==> waiting for Argo CD"
kubectl -n argocd wait --for=condition=Available --timeout=300s \
  deploy/argocd-server deploy/argocd-repo-server
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=300s

echo "==> phase 2: the root Application — git takes over from here"
kubectl apply -f "$ROOT/infra/k8s/bootstrap/root-application.yaml"

echo
echo "Bootstrapped. Everything from now on arrives through git:"
kubectl -n argocd get applications
