#!/usr/bin/env bash
set -euo pipefail

REAPER_VERSION="7.82"
REAPER_BUILD="782"
REAPER_ARCH="linux_x86_64"
REAPER_ARCHIVE="reaper${REAPER_BUILD}_${REAPER_ARCH}.tar.xz"
REAPER_URL="https://www.reaper.fm/files/7.x/${REAPER_ARCHIVE}"
INSTALL_ROOT="${HOME}/.local/opt/reaper/${REAPER_VERSION}"
BINARY="${INSTALL_ROOT}/REAPER/reaper"
BIN_DIR="${HOME}/.local/bin"
LINK="${BIN_DIR}/reaper"
STATE_ROOT="${HOME}/.local/state/hazewave-codespace"
RECEIPT="${STATE_ROOT}/reaper-${REAPER_VERSION}.receipt"

if [[ "${CODESPACES:-}" != "true" ]]; then
  echo "REAPER_INSTALL=BLOCKED_NOT_CODESPACES"
  exit 20
fi

[[ "$(uname -m)" == "x86_64" ]] || {
  echo "REAPER_INSTALL=BLOCKED_UNSUPPORTED_ARCH"
  echo "ARCH=$(uname -m)"
  exit 21
}

mkdir -p "$(dirname "$INSTALL_ROOT")" "$BIN_DIR" "$STATE_ROOT"

if [[ -x "$BINARY" ]]; then
  ln -sfn "$BINARY" "$LINK"
  echo "REAPER_INSTALL=PASS_ALREADY_PRESENT"
  echo "REAPER_VERSION=$REAPER_VERSION"
  echo "REAPER_BINARY=$BINARY"
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl \
  --proto '=https' \
  --tlsv1.2 \
  --fail \
  --location \
  --retry 3 \
  --retry-delay 2 \
  --connect-timeout 20 \
  --output "$TMP/$REAPER_ARCHIVE" \
  "$REAPER_URL"

SIZE_BYTES="$(stat -c '%s' "$TMP/$REAPER_ARCHIVE")"
(( SIZE_BYTES >= 8000000 && SIZE_BYTES <= 30000000 )) || {
  echo "REAPER_ARCHIVE=BLOCKED_UNEXPECTED_SIZE"
  echo "SIZE_BYTES=$SIZE_BYTES"
  exit 22
}

tar -tf "$TMP/$REAPER_ARCHIVE" |
  grep -qx 'reaper_linux_x86_64/REAPER/reaper' || {
    echo "REAPER_ARCHIVE=BLOCKED_UNEXPECTED_LAYOUT"
    exit 23
  }

STAGE="$TMP/stage"
mkdir -p "$STAGE"
tar -xf "$TMP/$REAPER_ARCHIVE" -C "$STAGE"

[[ -x "$STAGE/reaper_linux_x86_64/REAPER/reaper" ]] || {
  echo "REAPER_BINARY=BLOCKED_NOT_EXECUTABLE"
  exit 24
}

mkdir -p "$(dirname "$INSTALL_ROOT")"
mv "$STAGE/reaper_linux_x86_64" "$INSTALL_ROOT"
ln -sfn "$BINARY" "$LINK"

ARCHIVE_SHA256="$(sha256sum "$TMP/$REAPER_ARCHIVE" | awk '{print $1}')"

cat >"$RECEIPT" <<EOF
REAPER_VERSION=$REAPER_VERSION
REAPER_BUILD=$REAPER_BUILD
REAPER_URL=$REAPER_URL
REAPER_ARCHIVE_SHA256=$ARCHIVE_SHA256
REAPER_BINARY=$BINARY
EOF
chmod 600 "$RECEIPT"

echo "REAPER_INSTALL=PASS"
echo "REAPER_VERSION=$REAPER_VERSION"
echo "REAPER_BUILD=$REAPER_BUILD"
echo "REAPER_ARCHIVE_SHA256=$ARCHIVE_SHA256"
echo "REAPER_BINARY=$BINARY"
