#!/usr/bin/env bash
# Apply dashboards and alerts to Grafana Cloud.
#
# Credentials come from the gitignored secrets file, never from the command
# line, so they stay out of shell history and process listings.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS="$ROOT/infra/k8s/.secrets.env"

if [ ! -f "$SECRETS" ]; then
  echo "missing $SECRETS — capture the tokens first:" >&2
  echo "  scripts/capture-secret.sh GRAFANA_API_TOKEN" >&2
  echo "  scripts/capture-secret.sh DISCORD_WEBHOOK_URL" >&2
  exit 1
fi

set -a; . "$SECRETS"; set +a
exec uv run python "$ROOT/scripts/grafana/apply.py" "$@"
