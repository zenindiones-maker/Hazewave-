#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="0.5.95"
UPSTREAM_REPO="decolua/9router"
UPSTREAM_COMMIT="a99cf57239ff778b61e434c2786009d5ed1c412c"

ROOT="${HAZEWAVE_9ROUTER_ROOT:-$HOME/.local/share/hazewave/providers/9router}"
RELEASES="$ROOT/releases"
CURRENT="$ROOT/current"
STATE_ROOT="${HAZEWAVE_9ROUTER_STATE_ROOT:-$HOME/.local/state/hazewave/providers/9router}"
RUNTIME_HOME="$STATE_ROOT/home"

for cmd in node npm; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "HAZEWAVE_9ROUTER_INSTALL=FAIL missing_$cmd" >&2
    exit 2
  }
done

node - <<'NODE'
const major = Number(process.versions.node.split('.')[0]);
if (!Number.isInteger(major) || major < 20) {
  console.error("HAZEWAVE_9ROUTER_INSTALL=FAIL node_20_required");
  process.exit(2);
}
NODE

mkdir -p "$RELEASES" "$STATE_ROOT" "$RUNTIME_HOME"
chmod 700 "$STATE_ROOT" "$RUNTIME_HOME"

RELEASE_DIR="$RELEASES/${VERSION}-${UPSTREAM_COMMIT}"
if [ ! -d "$RELEASE_DIR" ]; then
  TMP="$RELEASES/.tmp.${VERSION}.$$"
  rm -rf "$TMP"
  mkdir -p "$TMP"

  HOME="$RUNTIME_HOME" npm install     --prefix "$TMP"     --no-audit     --no-fund     --save-exact     "9router@$VERSION"

  INSTALLED_VERSION="$(
    node -p "require('$TMP/node_modules/9router/package.json').version"
  )"
  test "$INSTALLED_VERSION" = "$VERSION"

  printf '%s\n' "$UPSTREAM_REPO" > "$TMP/UPSTREAM_REPOSITORY"
  printf '%s\n' "$UPSTREAM_COMMIT" > "$TMP/UPSTREAM_COMMIT"
  printf '%s\n' "$VERSION" > "$TMP/UPSTREAM_VERSION"

  mv "$TMP" "$RELEASE_DIR"
fi

test "$(cat "$RELEASE_DIR/UPSTREAM_REPOSITORY")" = "$UPSTREAM_REPO"
test "$(cat "$RELEASE_DIR/UPSTREAM_COMMIT")" = "$UPSTREAM_COMMIT"
test "$(cat "$RELEASE_DIR/UPSTREAM_VERSION")" = "$VERSION"
test -x "$RELEASE_DIR/node_modules/.bin/9router"

NEXT_LINK="$ROOT/.current.${UPSTREAM_COMMIT}"
rm -f "$NEXT_LINK"
ln -s "$RELEASE_DIR" "$NEXT_LINK"
mv -Tf "$NEXT_LINK" "$CURRENT" 2>/dev/null || {
  rm -f "$CURRENT"
  mv "$NEXT_LINK" "$CURRENT"
}

echo "HAZEWAVE_9ROUTER_INSTALL=PASS"
echo "HAZEWAVE_9ROUTER_VERSION=$VERSION"
echo "HAZEWAVE_9ROUTER_UPSTREAM_REPOSITORY=$UPSTREAM_REPO"
echo "HAZEWAVE_9ROUTER_UPSTREAM_COMMIT=$UPSTREAM_COMMIT"
echo "HAZEWAVE_9ROUTER_CURRENT=$CURRENT"
echo "HAZEWAVE_9ROUTER_AUTHORITY=NONE"
echo "HAZEWAVE_9ROUTER_PROJECT_AUTHORITY=HAZEWAVE_HARNESS"
echo "HAZEWAVE_9ROUTER_PAID_FALLBACK=FORBIDDEN"
echo "HAZEWAVE_9ROUTER_EXECUTION_POLICY=DISCOVERY_ONLY_UNTIL_ROUTE_ADMISSION"
