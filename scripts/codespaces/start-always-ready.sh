#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
DESKTOP="$SCRIPT_DIR/start-professional-desktop.sh"
REFLEX="$SCRIPT_DIR/reflex-shadow-control.sh"
SHARED_ENV="/workspaces/.codespaces/shared/environment-variables.json"

[[ "${CODESPACES:-}" == "true" ]] || {
  echo "HAZEWAVE_ALWAYS_READY=BLOCKED_NOT_CODESPACES" >&2
  exit 20
}
[[ -x "$DESKTOP" || -f "$DESKTOP" ]] || {
  echo "HAZEWAVE_ALWAYS_READY=BLOCKED_DESKTOP_CONTROL_MISSING" >&2
  exit 21
}
[[ -x "$REFLEX" || -f "$REFLEX" ]] || {
  echo "HAZEWAVE_ALWAYS_READY=BLOCKED_REFLEX_CONTROL_MISSING" >&2
  exit 22
}

resolve_codespace_name() {
  if [[ -n "${CODESPACE_NAME:-}" ]]; then
    printf '%s\n' "$CODESPACE_NAME"
    return 0
  fi

  if [[ -f "$SHARED_ENV" ]]; then
    python3 - "$SHARED_ENV" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
try:
    value = json.loads(path.read_text(encoding="utf-8")).get("CODESPACE_NAME", "")
except (OSError, ValueError):
    value = ""
if value:
    print(value)
PY
    return 0
  fi
  return 1
}

EXPECTED_CODESPACE="$(resolve_codespace_name || true)"
[[ -n "$EXPECTED_CODESPACE" ]] || {
  echo "HAZEWAVE_ALWAYS_READY=BLOCKED_CODESPACE_IDENTITY_UNKNOWN" >&2
  exit 23
}

echo "HAZEWAVE_ALWAYS_READY_MODE=POST_START_RECONCILE"
echo "HAZEWAVE_ALWAYS_READY_CODESPACE=$EXPECTED_CODESPACE"
echo "HAZEWAVE_ALWAYS_READY_REPO=$REPO_ROOT"

bash "$DESKTOP"

HAZEWAVE_REFLEX_EXPECTED_CODESPACE="$EXPECTED_CODESPACE" \
CODESPACE_NAME="$EXPECTED_CODESPACE" \
CODESPACES=true \
bash "$REFLEX" reconcile

echo "HAZEWAVE_LOCAL_DESKTOP_READY=PASS"
echo "HAZEWAVE_REMOTE_REFLEX_READY=PASS"
echo "HAZEWAVE_WORKSTATION_READY=PASS"
