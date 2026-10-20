#!/usr/bin/env bash
set -euo pipefail

BLENDER_VERSION="5.2.2"
BLENDER_SERIES="5.2"
ARCHIVE="blender-5.2.2-linux-x64.tar.xz"
CHECKSUM_FILE="blender-5.2.2.sha256"
SOURCE_BASE="https://download.blender.org/release/Blender5.2"
INSTALL_ROOT="${HOME}/.local/opt/blender"
TARGET="${HOME}/.local/opt/blender/5.2.2"
TARGET_BIN="${TARGET}/blender"
BLENDER_LINK="${HOME}/.local/bin/blender"
STATE_ROOT="${HOME}/.local/state/hazewave-codespace"
RECEIPT="${STATE_ROOT}/blender-5.2.2.receipt"

die() {
  echo "$1" >&2
  exit "${2:-20}"
}

verify_runtime() {
  [[ -x "$TARGET_BIN" ]] || return 1
  [[ -L "$BLENDER_LINK" ]] || return 1
  [[ "$(readlink -f "$BLENDER_LINK")" == "$TARGET_BIN" ]] || return 1
  local version_line
  version_line="$("$BLENDER_LINK" --background --factory-startup --disable-autoexec --version 2>&1 | sed -n '1p')"
  [[ "$version_line" == "Blender 5.2.2 LTS" ]] || return 1
  [[ -s "$RECEIPT" ]] || return 1
  grep -Fxq "BLENDER_VERSION_PIN=5.2.2" "$RECEIPT" || return 1
  grep -Fxq "BLENDER_SOURCE=OFFICIAL_BLENDER_FOUNDATION" "$RECEIPT" || return 1
  return 0
}

mkdir -p "$INSTALL_ROOT" "${HOME}/.local/bin" "$STATE_ROOT"

if verify_runtime; then
  echo "BLENDER_INSTALL=PASS_ALREADY_PINNED"
  echo "BLENDER_VERSION_PIN=5.2.2"
  echo "BLENDER_SOURCE=OFFICIAL_BLENDER_FOUNDATION"
  echo "PAID_FALLBACK=FALSE"
  echo "UNKNOWN_COST_FALLBACK=FALSE"
  exit 0
fi

if [[ -e "$TARGET" ]]; then
  die "BLENDER_INSTALL=BLOCKED_EXISTING_UNVERIFIED_TARGET" 21
fi

for cmd in curl tar sha256sum grep sed; do
  command -v "$cmd" >/dev/null 2>&1 || die "BLENDER_INSTALL=MISSING_COMMAND:$cmd" 22
done

TMPDIR_INSTALL="$(mktemp -d)"
cleanup() {
  rm -rf "$TMPDIR_INSTALL"
}
trap cleanup EXIT

curl -fL --retry 3 --retry-delay 2 \
  -o "$TMPDIR_INSTALL/$ARCHIVE" \
  "$SOURCE_BASE/$ARCHIVE"
curl -fL --retry 3 --retry-delay 2 \
  -o "$TMPDIR_INSTALL/$CHECKSUM_FILE" \
  "$SOURCE_BASE/$CHECKSUM_FILE"

grep -F "$ARCHIVE" "$TMPDIR_INSTALL/$CHECKSUM_FILE" \
  > "$TMPDIR_INSTALL/blender-linux.sha256" || \
  die "BLENDER_INSTALL=FAIL_OFFICIAL_CHECKSUM_ENTRY_MISSING" 23

(
  cd "$TMPDIR_INSTALL"
  sha256sum -c blender-linux.sha256
) || die "BLENDER_INSTALL=FAIL_OFFICIAL_SHA256" 24

ARCHIVE_SHA256="$(sha256sum "$TMPDIR_INSTALL/$ARCHIVE" | awk '{print $1}')"

tar -xJf "$TMPDIR_INSTALL/$ARCHIVE" -C "$TMPDIR_INSTALL"
EXTRACTED="$TMPDIR_INSTALL/blender-5.2.2-linux-x64"
[[ -x "$EXTRACTED/blender" ]] || die "BLENDER_INSTALL=FAIL_EXTRACTED_BINARY_MISSING" 25

mv "$EXTRACTED" "$TARGET"
ln -sfn "$TARGET_BIN" "$BLENDER_LINK"

VERSION_LINE="$("$BLENDER_LINK" --background --factory-startup --disable-autoexec --version 2>&1 | sed -n '1p')"
[[ "$VERSION_LINE" == "Blender 5.2.2 LTS" ]] || {
  rm -f "$BLENDER_LINK"
  die "BLENDER_INSTALL=FAIL_VERSION:$VERSION_LINE" 26
}

cat >"$RECEIPT" <<EOF
BLENDER_VERSION_PIN=5.2.2
BLENDER_SOURCE=OFFICIAL_BLENDER_FOUNDATION
SOURCE_BASE=$SOURCE_BASE
ARCHIVE=$ARCHIVE
ARCHIVE_SHA256=$ARCHIVE_SHA256
CHECKSUM_SOURCE=$SOURCE_BASE/$CHECKSUM_FILE
INSTALL_PATH=$TARGET
AUTOEXEC_DEFAULT=DISABLED_FOR_HAZEWAVE_HEADLESS
PAID_FALLBACK=FALSE
UNKNOWN_COST_FALLBACK=FALSE
EOF
chmod 600 "$RECEIPT"

verify_runtime || die "BLENDER_INSTALL=FAIL_POSTINSTALL_VERIFY" 27

echo "BLENDER_INSTALL=PASS"
echo "BLENDER_VERSION_PIN=5.2.2"
echo "BLENDER_SOURCE=OFFICIAL_BLENDER_FOUNDATION"
echo "BLENDER_BINARY=$TARGET_BIN"
echo "BLENDER_ARCHIVE_SHA256=$ARCHIVE_SHA256"
echo "PAID_FALLBACK=FALSE"
echo "UNKNOWN_COST_FALLBACK=FALSE"
