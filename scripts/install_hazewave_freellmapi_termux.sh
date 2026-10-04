#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FREELLMAPI_REMOTE="${FREELLMAPI_REMOTE:-https://github.com/tashfeenahmed/freellmapi.git}"
FREELLMAPI_REF="${FREELLMAPI_REF:-716948f20b12ec1c9b7c6fcebd22a3e7233cda1b}"
FREELLMAPI_PROVIDER_ROOT="${FREELLMAPI_PROVIDER_ROOT:-$HOME/.local/share/hazewave/providers/freellmapi}"
FREELLMAPI_DEPLOY_ROOT="$FREELLMAPI_PROVIDER_ROOT/deploy"
FREELLMAPI_REPO_GIT="$FREELLMAPI_DEPLOY_ROOT/repo.git"
FREELLMAPI_RELEASES_ROOT="$FREELLMAPI_DEPLOY_ROOT/releases"
FREELLMAPI_CURRENT="$FREELLMAPI_DEPLOY_ROOT/current"
FREELLMAPI_STATE_ROOT="${FREELLMAPI_STATE_ROOT:-$HOME/.local/state/hazewave/providers/freellmapi}"
FREELLMAPI_CONFIG_ROOT="${FREELLMAPI_CONFIG_ROOT:-$HOME/.config/hazewave/providers/freellmapi}"
FREELLMAPI_ENCRYPTION_KEY_FILE="$FREELLMAPI_CONFIG_ROOT/encryption-key"

for cmd in git node npm; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "HAZEWAVE_FREELLMAPI_INSTALL=FAIL missing_$cmd" >&2
    exit 2
  }
done

node - <<'NODE'
const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 22 || (major === 22 && minor < 13)) {
  console.error("HAZEWAVE_FREELLMAPI_INSTALL=FAIL node_22_13_required");
  process.exit(2);
}
NODE

mkdir -p "$FREELLMAPI_DEPLOY_ROOT" "$FREELLMAPI_RELEASES_ROOT"   "$FREELLMAPI_STATE_ROOT" "$FREELLMAPI_CONFIG_ROOT"
chmod 700 "$FREELLMAPI_STATE_ROOT" "$FREELLMAPI_CONFIG_ROOT"

if [ ! -s "$FREELLMAPI_ENCRYPTION_KEY_FILE" ]; then
  umask 077
  node -e "process.stdout.write(require('crypto').randomBytes(32).toString('hex') + '\n')"     > "$FREELLMAPI_ENCRYPTION_KEY_FILE"
fi
chmod 600 "$FREELLMAPI_ENCRYPTION_KEY_FILE"

if [ ! -d "$FREELLMAPI_REPO_GIT" ]; then
  git init --bare -q "$FREELLMAPI_REPO_GIT"
  git --git-dir="$FREELLMAPI_REPO_GIT" remote add origin "$FREELLMAPI_REMOTE"
else
  git --git-dir="$FREELLMAPI_REPO_GIT" remote set-url origin "$FREELLMAPI_REMOTE"
fi

git --git-dir="$FREELLMAPI_REPO_GIT" fetch --quiet --no-tags origin "$FREELLMAPI_REF"
DESIRED_SHA="$(git --git-dir="$FREELLMAPI_REPO_GIT" rev-parse FETCH_HEAD)"
test "$DESIRED_SHA" = "$FREELLMAPI_REF"
RELEASE_DIR="$FREELLMAPI_RELEASES_ROOT/$DESIRED_SHA"

if [ ! -d "$RELEASE_DIR" ]; then
  git --git-dir="$FREELLMAPI_REPO_GIT" worktree add --detach "$RELEASE_DIR" "$DESIRED_SHA" >/dev/null
  (
    cd "$RELEASE_DIR"
    npm ci --no-audit --no-fund
    npm run build
  )
fi

test "$(git -C "$RELEASE_DIR" rev-parse HEAD)" = "$DESIRED_SHA"
test -f "$RELEASE_DIR/server/dist/index.js"

NEXT_LINK="$FREELLMAPI_DEPLOY_ROOT/.current.$DESIRED_SHA"
rm -f "$NEXT_LINK"
ln -s "$RELEASE_DIR" "$NEXT_LINK"
mv -Tf "$NEXT_LINK" "$FREELLMAPI_CURRENT" 2>/dev/null || {
  rm -f "$FREELLMAPI_CURRENT"
  mv "$NEXT_LINK" "$FREELLMAPI_CURRENT"
}

printf '%s\n' "$DESIRED_SHA" > "$FREELLMAPI_STATE_ROOT/active-sha"
printf '%s\n' "$FREELLMAPI_REMOTE" > "$FREELLMAPI_CONFIG_ROOT/upstream-remote"
printf '%s\n' "$FREELLMAPI_REF" > "$FREELLMAPI_CONFIG_ROOT/upstream-ref"

echo "HAZEWAVE_FREELLMAPI_INSTALL=PASS"
echo "HAZEWAVE_FREELLMAPI_SHA=$DESIRED_SHA"
echo "HAZEWAVE_FREELLMAPI_CURRENT=$FREELLMAPI_CURRENT"
echo "HAZEWAVE_FREELLMAPI_STATE_ROOT=$FREELLMAPI_STATE_ROOT"
echo "HAZEWAVE_FREELLMAPI_CONFIG_ROOT=$FREELLMAPI_CONFIG_ROOT"
