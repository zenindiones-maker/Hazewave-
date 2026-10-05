#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HAZEWAVE_REMOTE="${HAZEWAVE_REMOTE:-https://github.com/zenindiones-maker/Hazewave-.git}"
HAZEWAVE_REF="${HAZEWAVE_REF:-work/wave-living-resonance-v1}"
HAZEWAVE_DEPLOY_ROOT="${HAZEWAVE_DEPLOY_ROOT:-$HOME/.local/share/hazewave/deploy}"
HAZEWAVE_STATE_ROOT="${HAZEWAVE_STATE_ROOT:-$HOME/.local/state/hazewave}"
HAZEWAVE_CONFIG_ROOT="${HAZEWAVE_CONFIG_ROOT:-$HOME/.config/hazewave}"
HAZEWAVE_REPO_GIT="$HAZEWAVE_DEPLOY_ROOT/repo.git"
HAZEWAVE_RELEASES_ROOT="$HAZEWAVE_DEPLOY_ROOT/releases"
HAZEWAVE_CURRENT="$HAZEWAVE_DEPLOY_ROOT/current"

command -v git >/dev/null 2>&1 || {
  echo "HAZEWAVE_TERMUX_INSTALL=FAIL missing_git" >&2
  exit 2
}
command -v python >/dev/null 2>&1 || {
  echo "HAZEWAVE_TERMUX_INSTALL=FAIL missing_python" >&2
  exit 2
}

mkdir -p "$HAZEWAVE_DEPLOY_ROOT" "$HAZEWAVE_RELEASES_ROOT" \
  "$HAZEWAVE_STATE_ROOT" "$HAZEWAVE_CONFIG_ROOT"

if [ ! -d "$HAZEWAVE_REPO_GIT" ]; then
  git init --bare -q "$HAZEWAVE_REPO_GIT"
  git --git-dir="$HAZEWAVE_REPO_GIT" remote add origin "$HAZEWAVE_REMOTE"
else
  git --git-dir="$HAZEWAVE_REPO_GIT" remote set-url origin "$HAZEWAVE_REMOTE"
fi

git --git-dir="$HAZEWAVE_REPO_GIT" fetch --quiet --no-tags origin "$HAZEWAVE_REF"
DESIRED_SHA="$(git --git-dir="$HAZEWAVE_REPO_GIT" rev-parse FETCH_HEAD)"
RELEASE_DIR="$HAZEWAVE_RELEASES_ROOT/$DESIRED_SHA"

if [ ! -d "$RELEASE_DIR" ]; then
  git --git-dir="$HAZEWAVE_REPO_GIT" worktree add --detach "$RELEASE_DIR" "$DESIRED_SHA" >/dev/null
fi

test "$(git -C "$RELEASE_DIR" rev-parse HEAD)" = "$DESIRED_SHA"
test -f "$RELEASE_DIR/config/project-profile-v2.json"
test -f "$RELEASE_DIR/src/hazewave/harness.py"
test -f "$RELEASE_DIR/docs/DOCUMENTATION_REGISTRY_V2.json"
test -f "$RELEASE_DIR/src/hazewave/telegram_gateway.py"
test -f "$RELEASE_DIR/scripts/hazewave_telegram_control.sh"
test -f "$RELEASE_DIR/scripts/configure_hazewave_telegram.sh"
test -f "$RELEASE_DIR/scripts/install_hazewave_telegram_persistence.sh"
test -f "$RELEASE_DIR/src/hazewave/freellmapi.py"
test -f "$RELEASE_DIR/scripts/install_hazewave_freellmapi_termux.sh"
test -f "$RELEASE_DIR/scripts/hazewave_freellmapi_control.sh"
test -f "$RELEASE_DIR/scripts/install_hazewave_freellmapi_persistence.sh"

NEXT_LINK="$HAZEWAVE_DEPLOY_ROOT/.current.$DESIRED_SHA"
rm -f "$NEXT_LINK"
ln -s "$RELEASE_DIR" "$NEXT_LINK"
mv -Tf "$NEXT_LINK" "$HAZEWAVE_CURRENT" 2>/dev/null || {
  rm -f "$HAZEWAVE_CURRENT"
  mv "$NEXT_LINK" "$HAZEWAVE_CURRENT"
}

printf '%s\n' "$DESIRED_SHA" > "$HAZEWAVE_STATE_ROOT/active-sha"
printf '%s\n' "$HAZEWAVE_REF" > "$HAZEWAVE_STATE_ROOT/active-ref"
printf '%s\n' "$HAZEWAVE_REMOTE" > "$HAZEWAVE_CONFIG_ROOT/remote"

PYTHONPATH="$HAZEWAVE_CURRENT/src" python -m hazewave.harness doctor

echo "HAZEWAVE_TERMUX_INSTALL=PASS"
echo "HAZEWAVE_RUNTIME_SHA=$DESIRED_SHA"
echo "HAZEWAVE_RUNTIME_REF=$HAZEWAVE_REF"
echo "HAZEWAVE_RUNTIME_CURRENT=$HAZEWAVE_CURRENT"
echo "HAZEWAVE_STATE_ROOT=$HAZEWAVE_STATE_ROOT"
echo "HAZEWAVE_CONFIG_ROOT=$HAZEWAVE_CONFIG_ROOT"
