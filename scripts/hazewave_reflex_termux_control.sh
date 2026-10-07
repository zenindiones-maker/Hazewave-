#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

REPO_SLUG="${HAZEWAVE_REFLEX_REPO:-zenindiones-maker/Hazewave-}"
DEFAULT_CS="hazewave-zero-cost-4jxp45676rq6279xx"
REF="${HAZEWAVE_REFLEX_REF:-work/hazewave-always-ready-v1}"
MAIN_REPO="/workspaces/Hazewave-"
RUN_ROOT="${HOME}/.local/share/hazewave/reflex-shadow-runtime"
WORKTREE="${RUN_ROOT}/checkout"
REMOTE_SELF="/tmp/hazewave-reflex-control.sh"
SHARED_ENV="/workspaces/.codespaces/shared/environment-variables.json"
CS=""

fail() {
    printf '%s\n' "HAZEWAVE_REFLEX_CONTROL=FAIL:$*" >&2
    exit 20
}

attest_codespace_control_plane() {
    local actual_name actual_repo actual_state

    ensure_codespace

    actual_name="$(gh codespace view -c "$CS" --json name --jq '.name')" \
      || fail "CONTROL_PLANE_CODESPACE_NAME_UNAVAILABLE"
    actual_repo="$(gh codespace view -c "$CS" --json repository --jq '.repository')" \
      || fail "CONTROL_PLANE_CODESPACE_REPO_UNAVAILABLE"
    actual_state="$(gh codespace view -c "$CS" --json state --jq '.state')" \
      || fail "CONTROL_PLANE_CODESPACE_STATE_UNAVAILABLE"

    [[ "$actual_name" == "$CS" ]] \
      || fail "CONTROL_PLANE_CODESPACE_NAME_MISMATCH"
    [[ "$actual_repo" == "$REPO_SLUG" ]] \
      || fail "CONTROL_PLANE_CODESPACE_REPO_MISMATCH"
    [[ "$actual_state" == "Available" ]] \
      || fail "CONTROL_PLANE_CODESPACE_NOT_AVAILABLE:$actual_state"

    echo "REFLEX_CONTROL_PLANE_IDENTITY=PASS" >&2
    echo "REFLEX_CONTROL_PLANE_CODESPACE=$actual_name" >&2
    echo "REFLEX_CONTROL_PLANE_REPOSITORY=$actual_repo" >&2
}

verify_remote_repository_identity() {
    local expected_repo="$1"
    local origin

    [[ -d "$MAIN_REPO/.git" ]] || fail "REMOTE_HAZEWAVE_REPO_MISSING"

    origin="$(git -C "$MAIN_REPO" remote get-url origin 2>/dev/null || true)"
    case "$origin" in
        "https://github.com/$expected_repo"|"https://github.com/$expected_repo.git"|"git@github.com:$expected_repo"|"git@github.com:$expected_repo.git")
            ;;
        *)
            echo "REFLEX_REMOTE_ORIGIN=$origin" >&2
            echo "REFLEX_REMOTE_EXPECTED_REPO=$expected_repo" >&2
            fail "REMOTE_REPOSITORY_IDENTITY_MISMATCH"
            ;;
    esac

    echo "REFLEX_REMOTE_REPOSITORY_IDENTITY=PASS"
    echo "REFLEX_REMOTE_REPOSITORY=$expected_repo"
}

remote_main() {
    local action="${1:-doctor}"
    local argument="${2:-}"
    local expected_codespace="${HAZEWAVE_REFLEX_EXPECTED_CODESPACE:-}"
    local expected_repo="${HAZEWAVE_REFLEX_EXPECTED_REPO:-}"
    local control_plane_attested="${HAZEWAVE_REFLEX_CONTROL_PLANE_ATTESTED:-}"

    [[ "$(uname -s)" == "Linux" ]] || fail "REMOTE_LINUX_REQUIRED"
    [[ "$(uname -m)" == "x86_64" ]] || fail "REMOTE_X86_64_REQUIRED"
    [[ -n "$expected_codespace" ]] || fail "REMOTE_EXPECTED_CODESPACE_REQUIRED"
    [[ -n "$expected_repo" ]] || fail "REMOTE_EXPECTED_REPO_REQUIRED"
    [[ "$control_plane_attested" == "1" ]] || fail "REMOTE_CONTROL_PLANE_ATTESTATION_REQUIRED"

    verify_remote_repository_identity "$expected_repo"

    # gh codespace ssh -c selected the exact control-plane-attested Codespace.
    # Export the verified identity for downstream runtime contracts whose process
    # environment may not inherit GitHub's default Codespaces variables over SSH.
    export CODESPACE_NAME="$expected_codespace"
    export CODESPACES=true
    export GITHUB_REPOSITORY="$expected_repo"

    echo "REFLEX_REMOTE_IDENTITY_SOURCE=TERMUX_GITHUB_CONTROL_PLANE"
    echo "REFLEX_REMOTE_CODESPACE_IDENTITY=PASS"
    echo "REFLEX_REMOTE_CODESPACE=$expected_codespace"

    cd "$MAIN_REPO"

    git fetch --no-tags origin \
      "refs/heads/$REF:refs/remotes/origin/$REF" \
      || fail "REMOTE_REF_FETCH_FAILED"

    local remote_sha current_sha
    remote_sha="$(git rev-parse --verify "refs/remotes/origin/$REF^{commit}")" \
      || fail "REMOTE_REF_VERIFY_FAILED"

    mkdir -p "$RUN_ROOT"
    chmod 700 "$RUN_ROOT"

    if [[ ! -e "$WORKTREE/.git" ]]; then
        [[ ! -e "$WORKTREE" ]] || fail "REMOTE_WORKTREE_PATH_OCCUPIED"
        git worktree add --detach "$WORKTREE" "$remote_sha" \
          || fail "REMOTE_WORKTREE_ADD_FAILED"
    else
        [[ -z "$(git -C "$WORKTREE" status --porcelain)" ]] \
          || fail "REMOTE_ISOLATED_WORKTREE_DIRTY"
        current_sha="$(git -C "$WORKTREE" rev-parse HEAD)"
        if [[ "$current_sha" != "$remote_sha" ]]; then
            git -C "$WORKTREE" checkout --detach "$remote_sha" \
              || fail "REMOTE_WORKTREE_UPDATE_FAILED"
        fi
    fi

    [[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$remote_sha" ]] \
      || fail "REMOTE_HEAD_MISMATCH"
    [[ -z "$(git -C "$WORKTREE" status --porcelain)" ]] \
      || fail "REMOTE_WORKTREE_DIRTY_AFTER_SYNC"

    local control="$WORKTREE/scripts/codespaces/reflex-shadow-control.sh"
    [[ -f "$control" ]] || fail "REMOTE_REFLEX_CONTROL_MISSING"

    echo "REFLEX_REMOTE_HEAD=$remote_sha"
    echo "REFLEX_REMOTE_ACTION=$action"

    export HAZEWAVE_REFLEX_EXPECTED_CODESPACE="$expected_codespace"
    export HAZEWAVE_REFLEX_CANDIDATE_REF="refs/remotes/origin/$REF"

    case "$action" in
        doctor|prepare|serve|serve-stop|reconcile|runtime-status|smoke|report|latency-profiles|latency-selected|latency-tune|latency-report|latency-engine-tune|latency-engine-report)
            exec bash "$control" "$action"
            ;;
        observe)
            [[ -n "$argument" && -f "$argument" ]] \
              || fail "REMOTE_OBSERVE_EVENT_MISSING"
            exec bash "$control" observe "$argument"
            ;;
        *)
            fail "REMOTE_ACTION_INVALID:$action"
            ;;
    esac
}

if [[ "${1:-}" == "_remote" ]]; then
    shift
    remote_main "${1:-doctor}" "${2:-}"
    exit $?
fi

command -v gh >/dev/null 2>&1 || fail "TERMUX_GH_MISSING"
[[ -f "${BASH_SOURCE[0]}" ]] || fail "TERMUX_CONTROLLER_SOURCE_MISSING"

resolve_codespace() {
    local configured="${HAZEWAVE_REFLEX_CODESPACE:-}"
    local rows=()
    local name

    if [[ -n "$configured" ]]; then
        if gh codespace view -c "$configured" --json name >/dev/null 2>&1; then
            printf '%s\n' "$configured"
            return 0
        fi
        fail "CONFIGURED_CODESPACE_NOT_ACCESSIBLE:$configured"
    fi

    if gh codespace view -c "$DEFAULT_CS" --json name >/dev/null 2>&1; then
        printf '%s\n' "$DEFAULT_CS"
        return 0
    fi

    while IFS= read -r name; do
        [[ -n "$name" ]] && rows+=("$name")
    done < <(
        gh codespace list \
          -R "$REPO_SLUG" \
          --limit 20 \
          --json name \
          --jq '.[].name'
    )

    if [[ "${#rows[@]}" -eq 0 ]]; then
        echo "REFLEX_CODESPACE_DISCOVERY=NONE" >&2
        echo "REFLEX_CODESPACE_REPO=$REPO_SLUG" >&2
        fail "NO_EXISTING_HAZEWAVE_CODESPACE"
    fi

    if [[ "${#rows[@]}" -gt 1 ]]; then
        echo "REFLEX_CODESPACE_DISCOVERY=MULTIPLE" >&2
        printf 'REFLEX_CODESPACE_CANDIDATE=%s\n' "${rows[@]}" >&2
        echo "Set HAZEWAVE_REFLEX_CODESPACE to the intended existing Codespace." >&2
        fail "MULTIPLE_HAZEWAVE_CODESPACES_REQUIRE_SELECTION"
    fi

    printf '%s\n' "${rows[0]}"
}

ensure_codespace() {
    if [[ -z "$CS" ]]; then
        CS="$(resolve_codespace)"
    fi
}


ensure_codespace_available() {
    ensure_codespace
    local current_state
    current_state="$(gh codespace view -c "$CS" --json state --jq '.state')" \
      || fail "CODESPACE_VIEW_FAILED"

    case "$current_state" in
        Available)
            ;;
        Shutdown)
            echo "REFLEX_CODESPACE_WAKE_REASON=$current_state"
            gh api \
              --method POST \
              -H "Accept: application/vnd.github+json" \
              -H "X-GitHub-Api-Version: 2026-03-10" \
              "/user/codespaces/$CS/start" >/dev/null \
              || fail "CODESPACE_START_FAILED"
            ;;
        Starting|Provisioning|Rebuilding)
            echo "REFLEX_CODESPACE_WAKE_REASON=WAIT_TRANSITION:$current_state"
            ;;
        *)
            fail "CODESPACE_STATE_NOT_STARTABLE:$current_state"
            ;;
    esac

    for _ in $(seq 1 60); do
        current_state="$(gh codespace view -c "$CS" --json state --jq '.state')" \
          || fail "CODESPACE_VIEW_FAILED"
        echo "REFLEX_CODESPACE_STATE=$current_state"
        [[ "$current_state" == "Available" ]] && break
        sleep 2
    done

    [[ "$current_state" == "Available" ]] || fail "CODESPACE_START_TIMEOUT"
    echo "REFLEX_CODESPACE_WAKE=PASS"
}

copy_controller() {
    ensure_codespace
    gh codespace ssh -c "$CS" \
      "umask 077; cat > '$REMOTE_SELF' && chmod 700 '$REMOTE_SELF'" \
      < "${BASH_SOURCE[0]}" \
      || fail "TERMUX_CONTROLLER_COPY_FAILED"
}

run_remote() {
    local action="$1"
    ensure_codespace
    attest_codespace_control_plane
    copy_controller
    gh codespace ssh -c "$CS" \
      "HAZEWAVE_REFLEX_CONTROL_PLANE_ATTESTED=1 HAZEWAVE_REFLEX_EXPECTED_CODESPACE='$CS' HAZEWAVE_REFLEX_EXPECTED_REPO='$REPO_SLUG' bash '$REMOTE_SELF' _remote '$action'" \
      || fail "REMOTE_ACTION_FAILED:$action"
}

action="${1:-status}"

case "$action" in
    install-check)
        echo "CONTROLLER=PASS"
        echo "PATH=${BASH_SOURCE[0]}"
        bash -n "${BASH_SOURCE[0]}" || fail "TERMUX_CONTROLLER_SYNTAX_INVALID"
        ;;

    status)
        echo "=== HAZEWAVE REFLEX / TERMUX COCKPIT ==="
        gh auth status --hostname github.com || fail "TERMUX_GITHUB_AUTH_INVALID"
        ensure_codespace
        echo "REFLEX_CODESPACE_DISCOVERY=PASS"
        gh codespace view \
          -c "$CS" \
          --json name,state,machineDisplayName,lastUsedAt,idleTimeoutMinutes,repository \
          || fail "CODESPACE_VIEW_FAILED"
        echo "REFLEX_CONTROL_PATH=${BASH_SOURCE[0]}"
        echo "REFLEX_TARGET_CODESPACE=$CS"
        echo "REFLEX_TARGET_REF=$REF"
        ;;

    list)
        gh auth status --hostname github.com || fail "TERMUX_GITHUB_AUTH_INVALID"
        gh codespace list \
          -R "$REPO_SLUG" \
          --limit 20 \
          --json name,state,repository,lastUsedAt,machineName
        ;;

    wake)
        gh auth status --hostname github.com >/dev/null || fail "TERMUX_GITHUB_AUTH_INVALID"
        ensure_codespace_available
        echo "REFLEX_TARGET_CODESPACE=$CS"
        ;;

    ready)
        gh auth status --hostname github.com >/dev/null || fail "TERMUX_GITHUB_AUTH_INVALID"
        ensure_codespace_available
        run_remote reconcile
        echo "HAZEWAVE_REMOTE_READY=PASS"
        echo "HAZEWAVE_WORKSTATION_READY=PASS"
        ;;

    stop)
        gh auth status --hostname github.com >/dev/null || fail "TERMUX_GITHUB_AUTH_INVALID"
        ensure_codespace
        current_state="$(gh codespace view -c "$CS" --json state --jq '.state')" \
          || fail "CODESPACE_VIEW_FAILED"
        if [[ "$current_state" == "Available" ]]; then
            gh codespace stop -c "$CS" || fail "CODESPACE_STOP_FAILED"
        fi
        echo "REFLEX_CODESPACE_STOP_REQUESTED=PASS"
        echo "REFLEX_TARGET_CODESPACE=$CS"
        ;;

    doctor|prepare|serve-stop|reconcile|runtime-status|smoke|report|latency-profiles|latency-selected|latency-tune|latency-report|latency-engine-tune|latency-engine-report)
        gh auth status --hostname github.com >/dev/null || fail "TERMUX_GITHUB_AUTH_INVALID"
        run_remote "$action"
        ;;

    serve)
        gh auth status --hostname github.com >/dev/null || fail "TERMUX_GITHUB_AUTH_INVALID"
        echo "REFLEX_SERVE_SESSION=ATTACHED"
        echo "REFLEX_SERVE_NOTE=keep_this_termux_tab_open"
        run_remote serve
        ;;

    observe)
        gh auth status --hostname github.com >/dev/null || fail "TERMUX_GITHUB_AUTH_INVALID"
        event="${2:-}"
        [[ -n "$event" && -f "$event" ]] || {
            echo "usage: hazewave-reflex observe /caminho/event.json" >&2
            exit 2
        }
        ensure_codespace
        attest_codespace_control_plane
        copy_controller
        remote_event="/tmp/hazewave-reflex-event-${BASHPID}.json"
        gh codespace ssh -c "$CS" \
          "umask 077; cat > '$remote_event' && chmod 600 '$remote_event'" \
          < "$event" \
          || fail "TERMUX_EVENT_COPY_FAILED"
        set +e
        gh codespace ssh -c "$CS" \
          "HAZEWAVE_REFLEX_CONTROL_PLANE_ATTESTED=1 HAZEWAVE_REFLEX_EXPECTED_CODESPACE='$CS' HAZEWAVE_REFLEX_EXPECTED_REPO='$REPO_SLUG' bash '$REMOTE_SELF' _remote observe '$remote_event'; rc=\$?; rm -f '$remote_event'; exit \$rc"
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || fail "REMOTE_ACTION_FAILED:observe:$rc"
        ;;

    *)
        cat >&2 <<'USAGE'
usage: hazewave-reflex {status|list|wake|ready|stop|doctor|prepare|serve|serve-stop|reconcile|runtime-status|smoke|observe EVENT.json|report|latency-profiles|latency-selected|latency-tune|latency-report|latency-engine-tune|latency-engine-report|install-check}
USAGE
        exit 2
        ;;
esac
