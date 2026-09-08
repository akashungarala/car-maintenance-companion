#!/usr/bin/env bash
# Read one secret from the clipboard into a gitignored env file.
#
# Exists so credentials never pass through a terminal transcript, a shell
# history, or a chat log. Only the length and a masked fingerprint are printed —
# enough to confirm something plausible was captured, not enough to reconstruct
# it.
#
#   scripts/capture-secret.sh DISCORD_WEBHOOK_URL
#   scripts/capture-secret.sh GRAFANA_OTLP_TOKEN

set -euo pipefail

KEY="${1:-}"
if [ -z "$KEY" ]; then
  echo "usage: scripts/capture-secret.sh <KEY_NAME>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$ROOT/infra/k8s/.secrets.env"

VALUE="$(pbpaste 2>/dev/null || true)"
VALUE="${VALUE#"${VALUE%%[![:space:]]*}"}"
VALUE="${VALUE%"${VALUE##*[![:space:]]}"}"

if [ -z "$VALUE" ]; then
  echo "clipboard is empty — copy the secret first" >&2
  exit 1
fi
case "$VALUE" in
  *$'\n'*) echo "clipboard contains multiple lines; expected a single secret" >&2; exit 1 ;;
esac

touch "$FILE"
chmod 600 "$FILE"
# Replace any existing entry rather than appending a second one, so re-running
# after a rotation does not leave a stale value that silently wins.
if grep -q "^${KEY}=" "$FILE" 2>/dev/null; then
  grep -v "^${KEY}=" "$FILE" > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"
  chmod 600 "$FILE"
  echo "  replaced existing $KEY"
fi
printf '%s=%s\n' "$KEY" "$VALUE" >> "$FILE"

echo "  captured $KEY: ${#VALUE} chars, starts '${VALUE:0:8}…', ends '…${VALUE: -4}'"
echo "  written to infra/k8s/.secrets.env (gitignored, mode 600)"
