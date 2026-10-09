#!/usr/bin/env bash
# Opt-in, exact-remote-bound proof. Run ONLY inside existing Hazewave Codespace.
# Never installs dependencies, changes git checkout, restarts stock or registers MCP globally.
set -euo pipefail

fail() { printf 'WAVE_RESEARCH_HOST=BLOCKED:%s\n' "$1" >&2; exit 20; }
[[ "$#" -eq 1 ]] || fail "EXPLICIT_MODE_REQUIRED"
case "$1" in
  --inventory|--prove|--client-probe|--wave-scroll) MODE="$1";;
  *) fail "MODE_DENIED";;
esac

EXPECTED_CS="hazewave-zero-cost-4jxp45676rq6279xx"
REF="refs/heads/work/wave-host-mcp-qualification-v1"
[[ "${CODESPACES:-}" == "true" ]] || fail "EXISTING_CODESPACE_REQUIRED"
[[ -z "${CODESPACE_NAME:-}" || "$CODESPACE_NAME" == "$EXPECTED_CS" ]] || fail "CODESPACE_NAME_CONFLICT"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
EXPECTED="${HAZEWAVE_RESEARCH_EXPECTED_SHA:-}"
[[ "$EXPECTED" =~ ^[a-f0-9]{40}$ ]] || fail "REVIEWED_SHA_REQUIRED"
[[ "$(git -C "$ROOT" rev-parse --is-inside-work-tree 2>/dev/null)" == "true" ]] || fail "WORKTREE_REQUIRED"
[[ "$(git -C "$ROOT" rev-parse HEAD)" == "$EXPECTED" ]] || fail "CHECKOUT_NOT_REVIEWED_SHA"
[[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=normal)" ]] || fail "WORKTREE_DIRTY"
case "$(git -C "$ROOT" remote get-url origin 2>/dev/null)" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git) ;;
  *) fail "GITHUB_REMOTE_WRONG";;
esac
REMOTE_SHA="$(git -C "$ROOT" ls-remote --exit-code origin "$REF" | awk 'NR==1 {print $1}')" || fail "REMOTE_REF_MISSING"
[[ "$REMOTE_SHA" == "$EXPECTED" ]] || fail "REMOTE_SHA_DRIFT"
command -v python3 >/dev/null || fail "PYTHON_MISSING"
REA="$HOME/.local/share/hazewave/reverse-engineering/rea-6.0.0/bin/rea"
IRIS="$HOME/.local/share/hazewave/iris/v0.4.1/bin/iris"
STATE="$HOME/.local/state/hazewave"
CHROME=""
for command in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$command" >/dev/null 2>&1; then
    CHROME="$(command -v "$command")"
    break
  fi
done
printf 'WAVE_GIT_REMOTE_MATCH=PASS\n'
printf 'WAVE_REVIEWED_SHA=%s\n' "$EXPECTED"
printf 'WAVE_REVIEWED_TREE=%s\n' "$(git -C "$ROOT" rev-parse HEAD^{tree})"
printf 'WAVE_EXISTING_CODESPACE_CONTEXT=PASS\n'
if [[ "${CODESPACE_NAME:-}" == "$EXPECTED_CS" ]]; then
  echo "WAVE_CODESPACE_NAME_ENV=EXPECTED_VALUE_PRESENT_NOT_INDEPENDENT_AUTH"
else
  echo "WAVE_CODESPACE_NAME_ENV=UNSET_REQUIRES_AUTHENTICATED_SSH_CONTROL_PLANE"
fi
echo "WAVE_RESEARCH_TARGETS=NO_EXTERNAL_TARGETS"
echo "WAVE_STOCK_HEALTH=NOT_CHECKED"
echo "WAVE_AGENT_SESSION=NOT_PROVEN"
echo "WAVE_HOST_IDENTITY_INDEPENDENTLY_ATTESTED=FALSE"

if [[ "$MODE" == "--inventory" ]]; then
  for pair in "REA:$REA" "IRIS:$IRIS" "CHROME:$CHROME"; do
    name="${pair%%:*}"; binary="${pair#*:}"
    if [[ -n "$binary" && -x "$binary" ]]; then
      printf 'WAVE_TOOL_%s=PRESENT_BINARY\n' "$name"
      sha256sum "$binary" | awk -v name="$name" '{print "WAVE_TOOL_SHA256_" name "=" $1}'
    else
      printf 'WAVE_TOOL_%s=NOT_INSTALLED_OR_NOT_EXECUTABLE\n' "$name"
    fi
  done
  echo "WAVE_RUNTIME_EXECUTION=NOT_ATTEMPTED"
  exit 0
fi

[[ -x "$REA" && -x "$IRIS" && -n "$CHROME" && -x "$CHROME" ]] || fail "PINNED_RUNTIME_MISSING"
"$REA" --version | grep -F "6.0.0" >/dev/null || fail "REA6_VERSION_DRIFT"
"$IRIS" --version | grep -F "0.4.1" >/dev/null || fail "IRIS_VERSION_DRIFT"
RAM_KIB="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
DISK_KIB="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
[[ "$RAM_KIB" =~ ^[0-9]+$ && "$DISK_KIB" =~ ^[0-9]+$ ]] || fail "RESOURCES_UNOBSERVED"
(( RAM_KIB >= 4 * 1024 * 1024 && DISK_KIB >= 4 * 1024 * 1024 )) || fail "LOW_HEADROOM_NO_INSTALL"
export PYTHONPATH="$ROOT/src"

case "$MODE" in
  --prove)
    python3 -m hazewave.harness_research_execution \
      --kind rea_owned_js --task-id owned-cs-rea6-v1 \
      --workspace "$ROOT" --expected-sha "$EXPECTED" --state-root "$STATE" \
      --rea "$REA" || fail "REA6_OWNED_PROOF_FAILED"
    python3 -m hazewave.harness_research_execution \
      --kind iris_owned_page --task-id owned-cs-iris-v1 \
      --workspace "$ROOT" --expected-sha "$EXPECTED" --state-root "$STATE" \
      --iris "$IRIS" --chrome "$CHROME" || fail "IRIS_OWNED_PROOF_FAILED"
    echo "WAVE_RESEARCH_HOST=PASS_FIRST_PARTY_EXECUTION"
    echo "WAVE_AGENT_SESSION=NOT_PROVEN"
    ;;
  --client-probe)
    python3 -m hazewave.wave_mcp_client_probe \
      --workspace "$ROOT" --expected-sha "$EXPECTED" \
      --state-root "$STATE" --rea "$REA" --iris "$IRIS" \
      --chrome "$CHROME" || fail "MCP_INDEPENDENT_CLIENT_FAILED"
    echo "WAVE_MCP_CLIENT=PASS_INDEPENDENT_PROBE_ONLY"
    echo "WAVE_EXISTING_AGENT_SESSION=NOT_PROVEN"
    ;;
  --wave-scroll)
    command -v node >/dev/null || fail "NODE_MISSING"
    node -e 'require("playwright")' >/dev/null 2>&1 || fail "PLAYWRIGHT_NOT_INSTALLED"
    WORK="$STATE/wave-scroll-$(date -u +%Y%m%dT%H%M%SZ)-$$"
    mkdir -m 700 -p "$WORK"
    node "$ROOT/scripts/research/scroll-owned-fixture.cjs" \
      "$WORK/frames" "$ROOT/tests/fixtures/wave-scroll-owned.html" || fail "BROWSER_CAPTURE_FAILED"
    "$REA" analyze-javascript-application \
      "$ROOT/tests/fixtures/wave-scroll-js-owned" --json \
      > "$WORK/rea-evidence.json" || fail "REA_SAME_TARGET_FAILED"
    chmod 600 "$WORK/rea-evidence.json"
    for target in mobile393 mobile360 desktop; do
      python3 -m hazewave.wave_scroll_evidence \
        --input "$WORK/frames/$target/browser-capture.json" \
        --capture-root "$WORK/frames/$target" --repo-sha "$EXPECTED" \
        || fail "WAVE_BROWSER_EVIDENCE_FAILED"
    done
    python3 -m hazewave.wave_scroll_learning \
      --capture "$WORK/frames/mobile393/browser-capture.json" \
      --capture-root "$WORK/frames/mobile393" \
      --rea-evidence "$WORK/rea-evidence.json" \
      --repo-sha "$EXPECTED" --state-root "$STATE" \
      || fail "WAVE_LEARNING_FAILED"
    echo "WAVE_RESEARCH_HOST=PASS_OWNED_CROSS_LAYER_EXECUTION"
    echo "WAVE_EXTERNAL_SITES=NOT_PROVEN"
    ;;
esac
echo "WAVE_PRODUCTION_APPROVED=FALSE"
