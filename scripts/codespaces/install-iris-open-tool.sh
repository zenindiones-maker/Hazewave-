#!/usr/bin/env bash
# HAZEWAVE/WAVE: isolated Iris camera from exact upstream MIT release.
# No remote shell scripts, privileged installs, arbitrary target URLs, stock
# service restarts, direct MCP registration, or new Codespaces.
set -euo pipefail

IRIS_VERSION="0.4.1"
IRIS_TAG="v0.4.1"
IRIS_TARGET="iris-x86_64-unknown-linux-musl.tar.gz"
IRIS_RELEASE_SHA256="aa6073ba255c0bcf09364a5503cbd4794791b832e5934a52b169a455d66101c7"
IRIS_RELEASE_URL="https://github.com/brijr/iris/releases/download/$IRIS_TAG/$IRIS_TARGET"
ROOT="$HOME/.local/share/hazewave/iris"
IRIS_BIN="$ROOT/v0.4.1/bin/iris"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPOSITORY="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
PROOF_ROOT="$HOME/.local/state/hazewave"

fail() {
  printf 'IRIS_CODESPACE_INSTALL=BLOCKED:%s\n' "$1" >&2
  exit 20
}
[[ "$#" -eq 1 ]] || fail "EXPLICIT_MODE_REQUIRED"
case "$1" in
  --preflight|--install|--doctor|--smoke) mode="$1" ;;
  *) fail "UNRECOGNIZED_MODE" ;;
esac
[[ "${CODESPACE_NAME:-}" == "hazewave-zero-cost-4jxp45676rq6279xx" ]] || fail "WRONG_CODESPACE"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || fail "UNSUPPORTED_PLATFORM"
[[ -f "$REPOSITORY/pyproject.toml" && -f "$REPOSITORY/tests/fixtures/iris-proof.html" ]] || fail "REVIEWED_WORKTREE_REQUIRED"
[[ -d "$REPOSITORY/.git" || -f "$REPOSITORY/.git" ]] || fail "GIT_WORKTREE_REQUIRED"
remote="$(git -C "$REPOSITORY" remote get-url origin)" || fail "GIT_REMOTE_UNAVAILABLE"
case "$remote" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git)
    ;;
  *) fail "REPOSITORY_IDENTITY_MISMATCH" ;;
esac
actual_sha="$(git -C "$REPOSITORY" rev-parse HEAD)" || fail "HEAD_UNAVAILABLE"
[[ "${HAZEWAVE_IRIS_EXPECTED_SHA:-}" =~ ^[a-f0-9]{40}$ ]] || fail "REVIEWED_SHA_REQUIRED"
[[ "$actual_sha" == "$HAZEWAVE_IRIS_EXPECTED_SHA" ]] || fail "HEAD_DRIFT"
[[ -z "$(git -C "$REPOSITORY" status --porcelain)" ]] || fail "DIRTY_WORKTREE"
[[ -x "$(command -v python3)" ]] || fail "PYTHON3_UNAVAILABLE"

chrome=""
if [[ -n "${CHROME:-}" && -x "${CHROME:-}" ]]; then
  chrome="$CHROME"
else
  for tool in chromium chromium-browser google-chrome google-chrome-stable brave-browser microsoft-edge; do
    if command -v "$tool" >/dev/null 2>&1; then
      chrome="$(command -v "$tool")"
      break
    fi
  done
fi
[[ -n "$chrome" ]] || fail "CHROMIUM_BROWSER_NOT_FOUND"
disk_kib="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
ram_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ "$disk_kib" =~ ^[0-9]+$ && "$ram_kib" =~ ^[0-9]+$ ]] || fail "RESOURCE_BUDGET_UNKNOWN"
(( disk_kib >= 2 * 1024 * 1024 )) || fail "DISK_BELOW_2GIB"
(( ram_kib >= 1 * 1024 * 1024 )) || fail "RAM_BELOW_1GIB"
printf 'HAZEWAVE_IRIS_EXPECTED_SHA=%s\n' "$actual_sha"
printf 'HAZEWAVE_IRIS_CHROME=%s\n' "$chrome"
printf 'HAZEWAVE_IRIS_DISK_FREE_KIB=%s\n' "$disk_kib"
printf 'HAZEWAVE_IRIS_RAM_FREE_KIB=%s\n' "$ram_kib"

if [[ "$mode" == "--preflight" ]]; then
  echo "IRIS_CODESPACE_PREFLIGHT=PASS"
  echo "IRIS_CODESPACE_INSTALL=NOT_ATTEMPTED"
  echo "IRIS_MCP_CONNECTED=NOT_PROVEN"
  exit 0
fi

if [[ "$mode" == "--install" ]]; then
  command -v curl >/dev/null 2>&1 || fail "CURL_UNAVAILABLE"
  command -v sha256sum >/dev/null 2>&1 || fail "SHA256SUM_UNAVAILABLE"
  command -v tar >/dev/null 2>&1 || fail "TAR_UNAVAILABLE"
  if [[ -x "$IRIS_BIN" ]]; then
    current="$("$IRIS_BIN" --version)" || fail "EXISTING_BINARY_UNHEALTHY"
    [[ "$current" == *"$IRIS_VERSION"* ]] || fail "EXISTING_VERSION_CONFLICT"
    echo "IRIS_CODESPACE_INSTALL=PASS:EXISTING_PINNED_VERSION"
    echo "IRIS_MCP_CONNECTED=NOT_PROVEN"
    exit 0
  fi
  stage="$(mktemp -d)"
  trap 'rm -rf "$stage"' EXIT
  curl -fsSL --retry 2 --max-time 90 "$IRIS_RELEASE_URL" -o "$stage/iris.tar.gz" || fail "RELEASE_DOWNLOAD_FAILED"
  printf '%s  %s\n' "$IRIS_RELEASE_SHA256" "$stage/iris.tar.gz" | sha256sum -c - >/dev/null || fail "RELEASE_SHA256_MISMATCH"
  entries="$(tar -tzf "$stage/iris.tar.gz")" || fail "RELEASE_ARCHIVE_UNREADABLE"
  [[ "$entries" == "iris" || "$entries" == "./iris" ]] || fail "UNEXPECTED_ARCHIVE_LAYOUT"
  mkdir -p "$stage/extracted"
  tar -xzf "$stage/iris.tar.gz" -C "$stage/extracted" --no-same-owner --no-same-permissions || fail "ARCHIVE_EXTRACTION_FAILED"
  [[ -f "$stage/extracted/iris" && ! -L "$stage/extracted/iris" ]] || fail "BINARY_TYPE_UNSAFE"
  chmod 0700 "$stage/extracted/iris"
  version="$("$stage/extracted/iris" --version)" || fail "UPSTREAM_BINARY_UNHEALTHY"
  [[ "$version" == *"$IRIS_VERSION"* ]] || fail "UPSTREAM_VERSION_DRIFT"
  mkdir -p "$ROOT/v0.4.1/bin"
  chmod 0700 "$ROOT/v0.4.1/bin"
  [[ ! -e "$IRIS_BIN" && ! -L "$IRIS_BIN" ]] || fail "DESTINATION_OCCUPIED"
  install -m 0700 "$stage/extracted/iris" "$IRIS_BIN" || fail "BINARY_INSTALL_FAILED"
  echo "IRIS_CODESPACE_INSTALL=PASS:PINNED_BINARY_INSTALLED"
  echo "IRIS_UPSTREAM_RELEASE_DIGEST_VERIFIED=PASS"
  echo "IRIS_MCP_CONNECTED=NOT_PROVEN"
  exit 0
fi

[[ -x "$IRIS_BIN" && ! -L "$IRIS_BIN" ]] || fail "PINNED_BINARY_NOT_INSTALLED"
"$IRIS_BIN" --version | grep -F "$IRIS_VERSION" >/dev/null || fail "PINNED_BINARY_VERSION_MISMATCH"
"$IRIS_BIN" mcp --help >/dev/null || fail "MCP_COMMAND_UNAVAILABLE"

if [[ "$mode" == "--doctor" ]]; then
  echo "IRIS_CODESPACE_DOCTOR=PASS:CLI_AND_BROWSER_PRESENT"
  echo "IRIS_CODESPACE_CAPTURE=NOT_TESTED"
  echo "IRIS_MCP_CONNECTED=NOT_PROVEN"
  exit 0
fi

PYTHONPATH="$REPOSITORY/src" python3 -m hazewave.iris_capture \
  --workspace "$REPOSITORY" \
  --iris "$IRIS_BIN" \
  --chrome "$chrome" \
  --state-root "$PROOF_ROOT" || fail "OWNED_FIXTURE_CAPTURE_FAILED"
echo "IRIS_CODESPACE_SMOKE=PASS:FIRST_PARTY_FIXTURE"
echo "IRIS_MCP_CONNECTED=NOT_PROVEN"
echo "IRIS_HARNESS_LIVE_EXECUTION=NOT_PROVEN"
