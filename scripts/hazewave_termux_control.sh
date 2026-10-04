#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HAZEWAVE_DEPLOY_ROOT="${HAZEWAVE_DEPLOY_ROOT:-$HOME/.local/share/hazewave/deploy}"
HAZEWAVE_STATE_ROOT="${HAZEWAVE_STATE_ROOT:-$HOME/.local/state/hazewave}"
HAZEWAVE_CONFIG_ROOT="${HAZEWAVE_CONFIG_ROOT:-$HOME/.config/hazewave}"
HAZEWAVE_CURRENT="$HAZEWAVE_DEPLOY_ROOT/current"

current_release() {
  test -L "$HAZEWAVE_CURRENT" || {
    echo "HAZEWAVE_RUNTIME=NOT_INSTALLED"
    return 1
  }
  readlink -f "$HAZEWAVE_CURRENT"
}

doctor() {
  local release sha recorded
  release="$(current_release)"
  test -d "$release"
  test -f "$release/config/project-profile-v2.json"
  test -f "$release/src/hazewave/harness.py"\n  test -f "$release/docs/DOCUMENTATION_REGISTRY_V2.json"

  sha="$(git -C "$release" rev-parse HEAD)"
  recorded="$(cat "$HAZEWAVE_STATE_ROOT/active-sha" 2>/dev/null || true)"
  test -n "$recorded"
  test "$sha" = "$recorded"

  echo "HAZEWAVE_RUNTIME=ONLINE"
  echo "HAZEWAVE_RUNTIME_SHA=$sha"
  echo "HAZEWAVE_RUNTIME_RELEASE=$release"
  echo "HAZEWAVE_RUNTIME_IMMUTABLE_RELEASE=PASS"
  echo "HAZEWAVE_RUNTIME_STATE_ROOT=$HAZEWAVE_STATE_ROOT"
  echo "HAZEWAVE_RUNTIME_CONFIG_ROOT=$HAZEWAVE_CONFIG_ROOT"
  PYTHONPATH="$release/src" python -m hazewave.harness doctor
}

sync_runtime() {
  local release installer
  if release="$(current_release 2>/dev/null)"; then
    installer="$release/scripts/install_hazewave_termux_runtime.sh"
  else
    installer="./scripts/install_hazewave_termux_runtime.sh"
  fi
  test -f "$installer" || {
    echo "HAZEWAVE_RUNTIME_SYNC=FAIL installer_not_found" >&2
    exit 3
  }
  bash "$installer"
}

case "${1:-doctor}" in
  doctor|status)
    doctor
    ;;
  harness)
    release="$(current_release)"
    PYTHONPATH="$release/src" python -m hazewave.harness doctor
    ;;
  sync)
    sync_runtime
    ;;
  where)
    echo "HAZEWAVE_DEPLOY_ROOT=$HAZEWAVE_DEPLOY_ROOT"
    echo "HAZEWAVE_CURRENT=$HAZEWAVE_CURRENT"
    echo "HAZEWAVE_STATE_ROOT=$HAZEWAVE_STATE_ROOT"
    echo "HAZEWAVE_CONFIG_ROOT=$HAZEWAVE_CONFIG_ROOT"
    ;;
  *)
    echo "usage: $0 {doctor|status|harness|sync|where}" >&2
    exit 2
    ;;
esac
