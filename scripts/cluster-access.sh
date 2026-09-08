#!/usr/bin/env bash
# Open an SSH tunnel to the Kubernetes API and write a kubeconfig that uses it.
#
# The API server is not exposed to the internet, and could not usefully be:
# k3s issues its serving certificate for the node's internal addresses and
# 127.0.0.1, so connecting to the public IP fails verification, and the public
# hostnames are Cloudflare-proxied — Cloudflare does not forward 6443.
#
# Tunnelling is therefore both the working option and the safer one. Routine
# deployment does not use this at all; Argo CD reconciles from inside the
# cluster (ADR-0008). This is for bootstrap and debugging.
#
#   eval "$(scripts/cluster-access.sh)"

set -euo pipefail

TOFU_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../infra/tofu" && pwd)"
KEY="${CMC_SSH_KEY:-$HOME/.ssh/cmc_k3s}"
KUBECONFIG_PATH="$TOFU_DIR/kubeconfig"
LOCAL_PORT="${CMC_K8S_PORT:-6443}"

IP="$(cd "$TOFU_DIR" && tofu output -raw public_ip)"

# Reuse an existing tunnel, but only if it actually works. A port can stay bound
# by a dead forwarder — after a laptop sleeps, say — and a liveness check based
# on binding alone happily reuses a tunnel that refuses every connection.
tunnel_alive() {
  curl -sk --max-time 5 "https://127.0.0.1:${LOCAL_PORT}/version" >/dev/null 2>&1
}

if ! tunnel_alive; then
  pkill -f "${LOCAL_PORT}:127.0.0.1:6443" 2>/dev/null || true
  ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ExitOnForwardFailure=yes \
    -f -N -L "${LOCAL_PORT}:127.0.0.1:6443" "ubuntu@${IP}"
  echo "# tunnel opened to ${IP}:6443 on localhost:${LOCAL_PORT}" >&2
else
  echo "# reusing existing tunnel on localhost:${LOCAL_PORT}" >&2
fi

# The kubeconfig already points at 127.0.0.1, which is exactly what the
# certificate covers — no rewriting needed.
ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o BatchMode=yes \
  "ubuntu@${IP}" 'sudo cat /etc/rancher/k3s/k3s.yaml' > "$KUBECONFIG_PATH"
chmod 600 "$KUBECONFIG_PATH"

echo "export KUBECONFIG=$KUBECONFIG_PATH"
