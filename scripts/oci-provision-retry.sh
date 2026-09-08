#!/usr/bin/env bash
# Provision the cluster, walking availability domains until one has capacity.
#
# Always Free Ampere A1 capacity is scarce and frequently exhausted: a plan can
# be perfectly valid and still fail with "Out of host capacity". That is not an
# error to fix, it is a queue to join — so this retries across every
# availability domain in the region, then backs off and starts again.
#
# Expect this to take hours or days in a contended region (risk R2). Run it in
# a terminal multiplexer and leave it.
#
# Usage:  scripts/oci-provision-retry.sh [max_rounds] [sleep_seconds]

set -uo pipefail

MAX_ROUNDS="${1:-100}"
SLEEP_SECONDS="${2:-300}"
TOFU_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../infra/tofu" && pwd)"
AD_COUNT=3 # OCI regions have at most 3; single-AD regions simply fail 1 and 2 fast

cd "$TOFU_DIR" || exit 1

for round in $(seq 1 "$MAX_ROUNDS"); do
  for ad in $(seq 0 $((AD_COUNT - 1))); do
    echo "=== round $round/$MAX_ROUNDS · availability domain index $ad · $(date -u +%H:%M:%SZ) ==="

    if tofu apply -auto-approve -var "availability_domain_index=$ad"; then
      echo "=== provisioned in AD index $ad ==="
      tofu output
      exit 0
    fi

    # Any other failure is a real problem — a bad variable, expired
    # credentials, a syntax error — and retrying just hides it.
    if ! tofu apply -auto-approve -var "availability_domain_index=$ad" 2>&1 \
        | grep -qiE "out of host capacity|out of capacity"; then
      echo "!!! failed for a reason other than capacity. Stopping so you can read it." >&2
      exit 1
    fi

    echo "--- AD $ad is out of capacity ---"
  done

  echo "--- all ADs exhausted, sleeping ${SLEEP_SECONDS}s ---"
  sleep "$SLEEP_SECONDS"
done

echo "!!! no capacity after $MAX_ROUNDS rounds." >&2
echo "Consider a different region, or the Hetzner fallback in ADR-0002." >&2
exit 1
