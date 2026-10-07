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
SHARED_ENV="/workspaces/.codespaces/shared/environment-variables.json"
CS=""

fail() {
    printf '%s\n' "HAZEWAVE_REFLEX_CONTROL=FAIL:$*" >&2
    exit 20
}

shared_env_value() {
    local key="$1"
    [[ -f "$SHARED_ENV" ]] || return 0
    command -v python >/dev/null 2>&1 || return 0
    python -c '
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        value = json.load(handle).get(sys.argv[2], "")
except (OSError, ValueError, TypeError):
    value = ""
print(value if isinstance(value, str) else "")
' "$SHARED_ENV" "$key"
}

verify_remote_codespace_identity() {
    local expected_codespace="$1"
    local expected_repo="$2"
    local env_name="${CODESPACE_NAME:-}"
    local env_codespaces="${CODESPACES:-}"
    local env_repo="${GITHUB_REPOSITORY:-}"
    local shared_name=""
    local shared_codespaces=""
    local shared_repo=""
    local actual_name=""
    local actual_repo=""

    if [[ -f "$SHARED_ENV" ]]; then
        shared_name="$(shared_env_value CODESPACE_NAME)"
        shared_codespaces="$(shared_env_value CODESPACES)"
        shared_repo="$(shared_env_value GITHUB_REPOSITORY)"
    fi

    if [[ "$env_name" == "$expected_codespace" ]]; then
        actual_name="$env_name"
        echo "REFLEX_REMOTE_IDENTITY_SOURCE=PROCESS_ENV"
    elif [[ "$shared_name" == "$expected_codespace" ]]; then
        actual_name="$shared_name"
        echo "REFLEX_REMOTE_IDENTITY_SOURCE=GITHUB_SHARED_ENV"
    else
        echo "REFLEX_REMOTE_EXPECTED_CODESPACE=$expected_codespace" >&2
        echo "REFLEX_REMOTE_PROCESS_CODESPACE_NAME=${env_name:-UNSET}" >&2
        echo "REFLEX_REMOTE_SHARED_CODESPACE_NAME=${shared_name:-UNSET}" >&2
        fail "REMOTE_CODESPACE_IDENTITY_MISMATCH"
    fi

    if [[ "$env_repo" == "$expected_repo" ]]; then
        actual_repo="$env_repo"
    elif [[ "$shared_repo" == "$expected_repo" ]]; then
        actual_repo="$shared_repo"
    else
        echo "REFLEX_REMOTE_EXPECTED_REPO=$expected_repo" >&2
        echo "REFLEX_REMOTE_PROCESS_REPO=${env_repo:-UNSET}" >&2
        echo "REFLEX_REMOTE_SHARED_REPO=${shared_repo:-UNSET}" >&2
        fail "REMOTE_REPOSITORY_IDENTITY_MISMATCH"
    fi

    if [[ -n "$env_codespaces" && "$env_codespaces" != "true" ]]; then
        fail "REMOTE_CODESPACES_FLAG_INVALID"
    fi
    if [[ -n "$shared_codespaces" && "$shared_codespaces" != "true" ]]; then
        fail "REMOTE_SHARED_CODESPACES_FLAG_INVALID"
    fi

    export CODESPACE_NAME="$actual_name"
    export CODESPACES=true
    export GITHUB_REPOSITORY="$actual_repo"

    echo "REFLEX_REMOTE_CODESPACE_IDENTITY=PASS"
    echo "REFLEX_REMOTE_CODESPACE=$actual_name"
    echo "REFLEX_REMOTE_REPOSITORY=$actual_repo"
}

remote_main() {
    local action="${1:-doctor}"
    local argument="${2:-}"
    local expected_codespace="${HAZEWAVE_REFLEX_EXPECTED_CODESPACE:-}"
    local expected_repo="${HAZEWAVE_REFLEX_EXPECTED_REPO:-}"

    [[ "$(uname -s)" == "Linux" ]] || fail "REMOTE_LINUX_REQUIRED"
    [[ "$(uname -m)" == "x86_64" ]] || fail "REMOTE_X86_64_REQUIRED"
    [[ -n "$expected_codespace" ]] || fail "REMOTE_EXPECTED_CODESPACE_REQUIRED"
    [[ -n "$expected_repo" ]] || fail "REMOTE_EXPECTED_REPO_REQUIRED"

    verify_remote_codespace_identity "$expected_codespace" "$expected_repo"

    [[ -d "$MAIN_REPO/.git" ]] || fail "REMOTE_HAZEWAVE_REPO_MISSING"

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

    case "$action" in
        doctor|prepare|serve|smoke|report)
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
    copy_controller
    gh codespace ssh -c "$CS" \
      "HAZEWAVE_REFLEX_EXPECTED_CODESPACE='$CS' HAZEWAVE_REFLEX_EXPECTED_REPO='$REPO_SLUG' bash '$REMOTE_SELF' _remote '$action'" \
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
        ensure_codespace
        current_state="$(gh codespace view -c "$CS" --json state --jq '.state')" \
          || fail "CODESPACE_VIEW_FAILED"
        if [[ "$current_state" != "Available" ]]; then
            gh api \
              --method POST \
              -H "Accept: application/vnd.github+json" \
              -H "X-GitHub-Api-Version: 2026-03-10" \
              "/user/codespaces/$CS/start" >/dev/null \
              || fail "CODESPACE_START_FAILED"
        fi
        for _ in $(seq 1 60); do
            current_state="$(gh codespace view -c "$CS" --json state --jq '.state')" \
              || fail "CODESPACE_VIEW_FAILED"
            echo "REFLEX_CODESPACE_STATE=$current_state"
            [[ "$current_state" == "Available" ]] && break
            sleep 2
        done
        [[ "$current_state" == "Available" ]] || fail "CODESPACE_START_TIMEOUT"
        echo "REFLEX_CODESPACE_WAKE=PASS"
        echo "REFLEX_TARGET_CODESPACE=$CS"
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
        remote_event="/tmp/hazewave-reflex-event-${BASHPID}.json"
        gh codespace ssh -c "$CS" \
          "umask 077; cat > '$remote_event' && chmod 600 '$remote_event'" \
          < "$event" \
          || fail "TERMUX_EVENT_COPY_FAILED"
        set +e
        gh codespace ssh -c "$CS" \
          "HAZEWAVE_REFLEX_EXPECTED_CODESPACE='$CS' HAZEWAVE_REFLEX_EXPECTED_REPO='$REPO_SLUG' bash '$REMOTE_SELF' _remote observe '$remote_event'; rc=\$?; rm -f '$remote_event'; exit \$rc"
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || fail "REMOTE_ACTION_FAILED:observe:$rc"
        ;;

    *)
        cat >&2 <<'USAGE'
usage: hazewave-reflex {status|list|wake|stop|doctor|prepare|serve|smoke|observe EVENT.json|report|install-check}
USAGE
        exit 2
        ;;
esac
