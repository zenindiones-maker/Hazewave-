#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

REPO_SLUG="${HAZEWAVE_REFLEX_REPO:-zenindiones-maker/Hazewave-}"
DEFAULT_CS="redesigned-space-bassoon-gxp67g5g7r739w59"
REF="${HAZEWAVE_REFLEX_REF:-work/reflex-robustness-risk-v3}"
MAIN_REPO="/workspaces/Hazewave-"
RUN_ROOT="${HOME}/.local/share/hazewave/reflex-shadow-runtime"
WORKTREE="${RUN_ROOT}/checkout"
REMOTE_SELF="/tmp/hazewave-reflex-control.sh"
CS=""

fail() {
    printf '%s\n' "HAZEWAVE_REFLEX_CONTROL=FAIL:$*" >&2
    exit 20
}

remote_main() {
    local action="${1:-doctor}"
    local argument="${2:-}"
    local expected_codespace="${HAZEWAVE_REFLEX_EXPECTED_CODESPACE:-}"

    [[ "$(uname -s)" == "Linux" ]] || fail "REMOTE_LINUX_REQUIRED"
    [[ "$(uname -m)" == "x86_64" ]] || fail "REMOTE_X86_64_REQUIRED"
    [[ -n "$expected_codespace" ]] || fail "REMOTE_EXPECTED_CODESPACE_REQUIRED"
    [[ "${CODESPACE_NAME:-}" == "$expected_codespace" ]] || fail "REMOTE_CODESPACE_IDENTITY_MISMATCH"
    [[ -d "$MAIN_REPO/.git" ]] || fail "REMOTE_HAZEWAVE_REPO_MISSING"

    cd "$MAIN_REPO"

    git fetch --no-tags origin       "refs/heads/$REF:refs/remotes/origin/$REF"       || fail "REMOTE_REF_FETCH_FAILED"

    local remote_sha current_sha
    remote_sha="$(git rev-parse --verify "refs/remotes/origin/$REF^{commit}")"       || fail "REMOTE_REF_VERIFY_FAILED"

    mkdir -p "$RUN_ROOT"
    chmod 700 "$RUN_ROOT"

    if [[ ! -e "$WORKTREE/.git" ]]; then
        [[ ! -e "$WORKTREE" ]] || fail "REMOTE_WORKTREE_PATH_OCCUPIED"
        git worktree add --detach "$WORKTREE" "$remote_sha"           || fail "REMOTE_WORKTREE_ADD_FAILED"
    else
        [[ -z "$(git -C "$WORKTREE" status --porcelain)" ]]           || fail "REMOTE_ISOLATED_WORKTREE_DIRTY"
        current_sha="$(git -C "$WORKTREE" rev-parse HEAD)"
        if [[ "$current_sha" != "$remote_sha" ]]; then
            git -C "$WORKTREE" checkout --detach "$remote_sha"               || fail "REMOTE_WORKTREE_UPDATE_FAILED"
        fi
    fi

    [[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$remote_sha" ]] || fail "REMOTE_HEAD_MISMATCH"
    [[ -z "$(git -C "$WORKTREE" status --porcelain)" ]] || fail "REMOTE_WORKTREE_DIRTY_AFTER_SYNC"

    local control="$WORKTREE/scripts/codespaces/reflex-shadow-control.sh"
    [[ -f "$control" ]] || fail "REMOTE_REFLEX_CONTROL_MISSING"

    echo "REFLEX_REMOTE_CODESPACE=$expected_codespace"
    echo "REFLEX_REMOTE_HEAD=$remote_sha"
    echo "REFLEX_REMOTE_ACTION=$action"

    export HAZEWAVE_REFLEX_EXPECTED_CODESPACE="$expected_codespace"

    case "$action" in
        doctor|prepare|serve|smoke|report)
            exec bash "$control" "$action"
            ;;
        observe)
            [[ -n "$argument" && -f "$argument" ]] || fail "REMOTE_OBSERVE_EVENT_MISSING"
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
        gh codespace list           -R "$REPO_SLUG"           --limit 20           --json name           --jq '.[].name'
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

copy_controller() {
    ensure_codespace
    gh codespace cp       -c "$CS"       "${BASH_SOURCE[0]}"       "remote:$REMOTE_SELF"       || fail "TERMUX_CONTROLLER_COPY_FAILED"
}

run_remote() {
    local action="$1"
    ensure_codespace
    copy_controller
    gh codespace ssh -c "$CS"       "HAZEWAVE_REFLEX_EXPECTED_CODESPACE='$CS' bash '$REMOTE_SELF' _remote '$action'"       || fail "REMOTE_ACTION_FAILED:$action"
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
        gh codespace view           -c "$CS"           --json name,state,machineDisplayName,lastUsedAt,idleTimeoutMinutes,repository           || fail "CODESPACE_VIEW_FAILED"
        echo "REFLEX_CONTROL_PATH=${BASH_SOURCE[0]}"
        echo "REFLEX_TARGET_CODESPACE=$CS"
        echo "REFLEX_TARGET_REF=$REF"
        ;;

    list)
        gh auth status --hostname github.com || fail "TERMUX_GITHUB_AUTH_INVALID"
        gh codespace list           -R "$REPO_SLUG"           --limit 20           --json name,state,repository,lastUsedAt,machineName
        ;;

    doctor|prepare|smoke|report)
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
        copy_controller
        remote_event="/tmp/hazewave-reflex-event-$$.json"
        gh codespace cp -c "$CS" "$event" "remote:$remote_event" || fail "TERMUX_EVENT_COPY_FAILED"
        set +e
        gh codespace ssh -c "$CS"           "HAZEWAVE_REFLEX_EXPECTED_CODESPACE='$CS' bash '$REMOTE_SELF' _remote observe '$remote_event'; rc=\$?; rm -f '$remote_event'; exit \$rc"
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || fail "REMOTE_ACTION_FAILED:observe:$rc"
        ;;

    *)
        cat >&2 <<'USAGE'
usage: hazewave-reflex {status|list|doctor|prepare|serve|smoke|observe EVENT.json|report|install-check}
USAGE
        exit 2
        ;;
esac
