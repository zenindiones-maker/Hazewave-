#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

CS="${HAZEWAVE_REFLEX_CODESPACE:-redesigned-space-bassoon-gxp67g5g7r739w59}"
REF="${HAZEWAVE_REFLEX_REF:-work/reflex-robustness-risk-v3}"
MAIN_REPO="/workspaces/Hazewave-"
RUN_ROOT="${HOME}/.local/share/hazewave/reflex-shadow-runtime"
WORKTREE="${RUN_ROOT}/checkout"
REMOTE_SELF="/tmp/hazewave-reflex-control.sh"

fail() {
    printf '%s\n' "HAZEWAVE_REFLEX_CONTROL=FAIL:$*" >&2
    exit 20
}

remote_main() {
    local action="${1:-doctor}"
    local argument="${2:-}"

    [[ "$(uname -s)" == "Linux" ]] || fail "REMOTE_LINUX_REQUIRED"
    [[ "$(uname -m)" == "x86_64" ]] || fail "REMOTE_X86_64_REQUIRED"
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

    [[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$remote_sha" ]]       || fail "REMOTE_HEAD_MISMATCH"
    [[ -z "$(git -C "$WORKTREE" status --porcelain)" ]]       || fail "REMOTE_WORKTREE_DIRTY_AFTER_SYNC"

    local control="$WORKTREE/scripts/codespaces/reflex-shadow-control.sh"
    [[ -f "$control" ]] || fail "REMOTE_REFLEX_CONTROL_MISSING"

    echo "REFLEX_REMOTE_HEAD=$remote_sha"
    echo "REFLEX_REMOTE_ACTION=$action"

    case "$action" in
        doctor|prepare|serve|smoke|report)
            exec bash "$control" "$action"
            ;;
        observe)
            [[ -n "$argument" && -f "$argument" ]]               || fail "REMOTE_OBSERVE_EVENT_MISSING"
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

copy_controller() {
    gh codespace cp       -c "$CS"       "${BASH_SOURCE[0]}"       "remote:$REMOTE_SELF"       || fail "TERMUX_CONTROLLER_COPY_FAILED"
}

run_remote() {
    local action="$1"
    copy_controller
    gh codespace ssh -c "$CS"       "bash '$REMOTE_SELF' _remote '$action'"       || fail "REMOTE_ACTION_FAILED:$action"
}

action="${1:-status}"

case "$action" in
    status)
        echo "=== HAZEWAVE REFLEX / TERMUX COCKPIT ==="
        gh auth status --hostname github.com || fail "TERMUX_GITHUB_AUTH_INVALID"
        gh codespace view           -c "$CS"           --json name,state,machineDisplayName,lastUsedAt,idleTimeoutMinutes,repository           || fail "CODESPACE_VIEW_FAILED"
        echo "REFLEX_CONTROL_PATH=${BASH_SOURCE[0]}"
        echo "REFLEX_TARGET_CODESPACE=$CS"
        echo "REFLEX_TARGET_REF=$REF"
        ;;

    doctor|prepare|smoke|report)
        run_remote "$action"
        ;;

    serve)
        echo "REFLEX_SERVE_SESSION=ATTACHED"
        echo "REFLEX_SERVE_NOTE=keep_this_termux_tab_open"
        run_remote serve
        ;;

    observe)
        event="${2:-}"
        [[ -n "$event" && -f "$event" ]] || {
            echo "usage: hazewave-reflex observe /caminho/event.json" >&2
            exit 2
        }
        copy_controller
        remote_event="/tmp/hazewave-reflex-event-$$.json"
        gh codespace cp -c "$CS" "$event" "remote:$remote_event"           || fail "TERMUX_EVENT_COPY_FAILED"
        set +e
        gh codespace ssh -c "$CS"           "bash '$REMOTE_SELF' _remote observe '$remote_event'; rc=\$?; rm -f '$remote_event'; exit \$rc"
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || fail "REMOTE_ACTION_FAILED:observe:$rc"
        ;;

    install-check)
        echo "CONTROLLER=PASS"
        echo "PATH=${BASH_SOURCE[0]}"
        bash -n "${BASH_SOURCE[0]}" || fail "TERMUX_CONTROLLER_SYNTAX_INVALID"
        ;;

    *)
        cat >&2 <<'USAGE'
usage: hazewave-reflex {status|doctor|prepare|serve|smoke|observe EVENT.json|report|install-check}
USAGE
        exit 2
        ;;
esac
