#!/usr/bin/env bash
# Roll back the API to the previously deployed image, time it, and roll forward
# again. Run it deliberately: it briefly serves the previous release.
#
# This is the documented rollback procedure, executed rather than described. A
# rollback path that has never been exercised is a plan, not a capability --
# the same reason the backup is restored rather than assumed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_URL="${HEALTH_URL:-https://garage-api.akashungarala.com/health}"
OVERLAY="infra/k8s/apps/api/overlays/prod/kustomization.yaml"
KEEP_ROLLED_BACK="${KEEP_ROLLED_BACK:-0}"

export KUBECONFIG="${KUBECONFIG:-$ROOT/infra/tofu/kubeconfig}"

pinned_sha() { git show origin/deploy:"$OVERLAY" | awk '/newTag/{print $2}'; }
running_sha() {
  kubectl get deploy -n cmc api \
    -o jsonpath='{.spec.template.spec.containers[0].image}' | sed 's/.*://'
}

wait_for() { # $1 = sha, $2 = label
  local target="$1" label="$2" start elapsed
  start=$(date +%s)
  # Argo polls on its own schedule; an operator responding to an incident would
  # not wait for it, so the drill triggers the sync the same way they would.
  kubectl annotate app -n argocd api argocd.argoproj.io/refresh=hard --overwrite >/dev/null
  while :; do
    if [ "$(running_sha)" = "$target" ] \
       && kubectl rollout status -n cmc deploy/api --timeout=10s >/dev/null 2>&1 \
       && [ "$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL")" = "200" ]; then
      elapsed=$(( $(date +%s) - start ))
      echo "  $label: healthy on ${target:0:12} after ${elapsed}s"
      return 0
    fi
    if [ $(( $(date +%s) - start )) -gt 600 ]; then
      echo "  $label: FAILED to converge within 600s" >&2
      return 1
    fi
    sleep 5
  done
}

git fetch -q origin deploy
CURRENT="$(pinned_sha)"
echo "  currently deployed: ${CURRENT:0:12}"

WORKTREE="$(mktemp -d)"
trap 'rm -rf "$WORKTREE"' EXIT
git worktree add -q --detach "$WORKTREE" origin/deploy
cd "$WORKTREE"
git checkout -q -B deploy origin/deploy

# The tag bump is the only thing being undone. Manifests stay as they are:
# migrations are expand/contract, so the previous image runs against the
# current schema, and rolling code back must never require rolling schema back.
TAG_COMMIT="$(git log -1 --format=%H --grep='^deploy: api ')"
echo "  reverting: $(git log -1 --format=%s "$TAG_COMMIT")"
git revert --no-edit "$TAG_COMMIT" >/dev/null
git push -q origin deploy
cd "$ROOT"
git fetch -q origin deploy
PREVIOUS="$(pinned_sha)"
echo "  rolled back to:     ${PREVIOUS:0:12}"

wait_for "$PREVIOUS" "ROLLBACK"

if [ "$KEEP_ROLLED_BACK" = "1" ]; then
  echo "  KEEP_ROLLED_BACK=1 — leaving the previous release deployed"
  git worktree remove --force "$WORKTREE" 2>/dev/null || true
  exit 0
fi

cd "$WORKTREE"
git revert --no-edit HEAD >/dev/null   # undo the rollback
git push -q origin deploy
cd "$ROOT"
git fetch -q origin deploy
wait_for "$CURRENT" "ROLL FORWARD"
git worktree remove --force "$WORKTREE" 2>/dev/null || true
echo "  drill complete; back on ${CURRENT:0:12}"
