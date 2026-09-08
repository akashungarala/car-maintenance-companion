#!/usr/bin/env bash
# Restore the latest backup into a scratch namespace and verify it.
#
# A backup that has never been restored is not a backup (ADR-0003). This proves
# the whole chain: WAL and base backups actually reached object storage, the
# credentials work from a fresh namespace, and the data comes back.
#
# Run quarterly, and after any change to backup configuration.
#
#   eval "$(scripts/cluster-access.sh)"
#   scripts/restore-drill.sh
#
# It tears the scratch namespace down on exit, including on failure.

set -euo pipefail

NS="${DRILL_NAMESPACE:-cmc-restore-drill}"
SOURCE_CLUSTER="${SOURCE_CLUSTER:-cmc-db}"
SOURCE_NS="${SOURCE_NS:-cmc}"
TOFU_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../infra/tofu" && pwd)"

cleanup() {
  echo "==> tearing down $NS"
  kubectl delete namespace "$NS" --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> scratch namespace $NS"
kubectl create namespace "$NS" >/dev/null 2>&1 || true

echo "==> object storage credentials"
# Read straight from tofu rather than copying the production secret: the drill
# should prove the credentials work, not that a copy of them does.
ACCESS_KEY="$(cd "$TOFU_DIR" && tofu output -raw s3_access_key_id)"
SECRET_KEY="$(cd "$TOFU_DIR" && tofu output -raw s3_secret_access_key)"
ENDPOINT="$(cd "$TOFU_DIR" && tofu output -raw s3_endpoint)"

kubectl -n "$NS" create secret generic pg-backup-s3 \
  --from-literal=ACCESS_KEY_ID="$ACCESS_KEY" \
  --from-literal=ACCESS_SECRET_KEY="$SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

echo "==> restoring $SOURCE_CLUSTER from object storage"
kubectl apply -f - >/dev/null <<CLUSTER
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: restored
  namespace: $NS
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:17.2
  storage:
    size: 5Gi
    storageClass: local-path
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      memory: 512Mi
  bootstrap:
    recovery:
      source: $SOURCE_CLUSTER
  externalClusters:
    - name: $SOURCE_CLUSTER
      barmanObjectStore:
        destinationPath: s3://cmc-pg-backups/
        endpointURL: $ENDPOINT
        # serverName must match the cluster the backup was taken from — that is
        # the directory the archive lives under, not the name being restored to.
        serverName: $SOURCE_CLUSTER
        s3Credentials:
          accessKeyId:
            name: pg-backup-s3
            key: ACCESS_KEY_ID
          secretAccessKey:
            name: pg-backup-s3
            key: ACCESS_SECRET_KEY
CLUSTER

echo "==> waiting for the restored cluster (recovery replays WAL, so this is not instant)"
for _ in $(seq 1 60); do
  READY="$(kubectl -n "$NS" get cluster restored -o jsonpath='{.status.readyInstances}' 2>/dev/null || echo 0)"
  [ "${READY:-0}" = "1" ] && break
  sleep 10
done

if [ "${READY:-0}" != "1" ]; then
  echo "!!! restored cluster never became ready" >&2
  kubectl -n "$NS" get cluster restored -o jsonpath='{.status.phase}{"\n"}' >&2 || true
  kubectl -n "$NS" get pods >&2 || true
  exit 1
fi

echo "==> verifying the data came back"
kubectl -n "$NS" exec restored-1 -c postgres -- \
  psql -U postgres -d cmc -tAc \
  "SELECT marker FROM restore_drill ORDER BY id DESC LIMIT 1"
