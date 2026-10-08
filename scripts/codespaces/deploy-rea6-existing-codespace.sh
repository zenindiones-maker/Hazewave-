#!/usr/bin/env bash
# Owner-invoked, exact-bound REA6 deployment into the EXISTING Hazewave Codespace.
# Side by side with any existing REA installation. Never touches the Reflex server.
set -euo pipefail

EXPECTED_CODESPACE="hazewave-zero-cost-4jxp45676rq6279xx"
EXPECTED_REMOTE_REF="refs/heads/work/reverse-engineering-rea6-harness-v1"
EXPECTED_REPO="zenindiones-maker/Hazewave-"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"

fail() {
  printf 'HAZEWAVE_REA6_DEPLOY=BLOCKED:%s\n' "$1" >&2
  exit 20
}

[[ "$#" -eq 1 ]] || fail "EXPLICIT_MODE_REQUIRED"
mode="$1"
case "$mode" in
  --preflight|--install|--deep) ;;
  *) fail "UNKNOWN_MODE" ;;
esac

[[ "${CODESPACE_NAME:-}" == "$EXPECTED_CODESPACE" ]] || fail "WRONG_CODESPACE"
[[ -n "${HAZEWAVE_RE_EXPECTED_SHA:-}" ]] || fail "EXPECTED_SHA_REQUIRED"
[[ "$HAZEWAVE_RE_EXPECTED_SHA" =~ ^[a-f0-9]{40}$ ]] || fail "EXPECTED_SHA_INVALID"
command -v git >/dev/null 2>&1 || fail "GIT_REQUIRED"
[[ "$(git -C "$REPO_ROOT" rev-parse --is-inside-work-tree 2>/dev/null)" == "true" ]] || fail "NOT_A_WORKTREE"
observed="$(git -C "$REPO_ROOT" rev-parse HEAD)" || fail "HEAD_UNAVAILABLE"
[[ "$observed" == "$HAZEWAVE_RE_EXPECTED_SHA" ]] || fail "HEAD_MISMATCH"
[[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ]] || fail "WORKTREE_DIRTY"

remote="$(git -C "$REPO_ROOT" remote get-url origin)" || fail "REMOTE_UNAVAILABLE"
case "$remote" in
  "https://github.com/$EXPECTED_REPO"|"https://github.com/$EXPECTED_REPO.git"|"git@github.com:$EXPECTED_REPO"|"git@github.com:$EXPECTED_REPO.git"|"ssh://git@github.com/$EXPECTED_REPO"|"ssh://git@github.com/$EXPECTED_REPO.git") ;;
  *) fail "REMOTE_IDENTITY_MISMATCH" ;;
esac

remote_sha="$(git -C "$REPO_ROOT" ls-remote --exit-code origin "$EXPECTED_REMOTE_REF" | awk 'NR==1 {print $1}')" || fail "REMOTE_REF_UNAVAILABLE"
[[ "$remote_sha" == "$HAZEWAVE_RE_EXPECTED_SHA" ]] || fail "REMOTE_HEAD_MOVED"

[[ -f "$SCRIPT_DIR/install-reverse-engineering-foundation.sh" ]] || fail "INSTALLER_NOT_FOUND"
[[ -f "$SCRIPT_DIR/reverse-engineering-doctor.sh" ]] || fail "DOCTOR_NOT_FOUND"

printf 'HAZEWAVE_REA6_CODESPACE=%s\n' "$CODESPACE_NAME"
printf 'HAZEWAVE_REA6_REPOSITORY=%s\n' "$EXPECTED_REPO"
printf 'HAZEWAVE_REA6_HEAD=%s\n' "$observed"
printf 'HAZEWAVE_REA6_MODE=%s\n' "$mode"

# This preflight has NO install side effects. It enforces at least 8 GiB free disk.
bash "$SCRIPT_DIR/install-reverse-engineering-foundation.sh" --preflight || fail "INSTALL_PREFLIGHT_FAILED"

if [[ "$mode" == "--preflight" ]]; then
  echo "HAZEWAVE_REA6_DEPLOY=PASS:PRECHECK_ONLY"
  echo "HAZEWAVE_REA6_INSTALL=NOT_ATTEMPTED"
  exit 0
fi

if [[ "$mode" == "--install" ]]; then
  # Explicit mode only. The installer uses dedicated REA6 paths and never
  # registers MCP agents or modifies the global REA4 launcher.
  bash "$SCRIPT_DIR/install-reverse-engineering-foundation.sh" || fail "INSTALL_FAILED"
  bash "$SCRIPT_DIR/reverse-engineering-doctor.sh" || fail "DOCTOR_FAILED"
  echo "HAZEWAVE_REA6_DEPLOY=PASS:INSTALLED_DOCTOR_CHECKED"
  echo "HAZEWAVE_REA6_MCP_CONNECTED=NOT_PROVEN"
  echo "HAZEWAVE_REA6_HARNESS_PRODUCTION=NOT_APPROVED"
  exit 0
fi

# Deep runs only after an explicit install invocation. An owned fixture is
# compiled and examined with the pinned Ghidra provider, fail closed.
[[ -f "$HOME/.config/hazewave/reverse-engineering-rea6.env" ]] || fail "INSTALL_NOT_FOUND"
bash "$SCRIPT_DIR/reverse-engineering-doctor.sh" --deep || fail "DEEP_PROBE_FAILED"
echo "HAZEWAVE_REA6_DEPLOY=PASS:OWNED_GHIDRA_FIXTURE"
echo "HAZEWAVE_REA6_MCP_CONNECTED=NOT_PROVEN"
echo "HAZEWAVE_REA6_HARNESS_PRODUCTION=NOT_APPROVED"
