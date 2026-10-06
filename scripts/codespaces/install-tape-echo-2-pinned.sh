#!/usr/bin/env bash
set -euo pipefail

TAPE_ECHO_2_VERSION="1.0.8"
TAPE_ECHO_2_TAG="tape-echo-2-v${TAPE_ECHO_2_VERSION}"
ARCHIVE_NAME="tape-echo-2-linux.zip"
ARCHIVE_SHA256="698c8825cac19547b40cd7a893d1b9bfac25587ec79cb30518f64084123b29f3"
DOWNLOAD_URL="https://github.com/dusk-audio/dusk-audio-plugins/releases/download/${TAPE_ECHO_2_TAG}/${ARCHIVE_NAME}"

VST3_ROOT="${HOME}/.vst3"
INSTALL_DIR="${VST3_ROOT}/tape-echo-2.vst3"
STATE_ROOT="${HOME}/.local/state/hazewave-codespace"
RECEIPT="${STATE_ROOT}/tape-echo-2-${TAPE_ECHO_2_VERSION}.receipt"

if [[ "${CODESPACES:-}" != "true" ]]; then
  echo "TAPE_ECHO_2_INSTALL=BLOCKED_NOT_CODESPACES"
  exit 20
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "TAPE_ECHO_2_INSTALL=BLOCKED_UNSUPPORTED_ARCH"
  echo "ARCH=$(uname -m)"
  exit 21
fi

mkdir -p "$VST3_ROOT" "$STATE_ROOT"

if [[ -d "$INSTALL_DIR" && -s "$RECEIPT" ]]   && grep -Fxq "TAPE_ECHO_2_VERSION=$TAPE_ECHO_2_VERSION" "$RECEIPT"   && grep -Fxq "ARCHIVE_SHA256=$ARCHIVE_SHA256" "$RECEIPT"; then
  echo "TAPE_ECHO_2_INSTALL=PASS_ALREADY_PRESENT"
  echo "TAPE_ECHO_2_VERSION=$TAPE_ECHO_2_VERSION"
  echo "VST3_PATH=$INSTALL_DIR"
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ARCHIVE="$TMP/$ARCHIVE_NAME"
EXTRACT_ROOT="$TMP/extract"

curl   --proto '=https'   --tlsv1.2   --fail   --location   --retry 3   --retry-delay 2   --connect-timeout 20   --output "$ARCHIVE"   "$DOWNLOAD_URL"

SIZE_BYTES="$(stat -c '%s' "$ARCHIVE")"
if (( SIZE_BYTES < 3000000 || SIZE_BYTES > 8000000 )); then
  echo "TAPE_ECHO_2_ARCHIVE=BLOCKED_UNEXPECTED_SIZE"
  echo "SIZE_BYTES=$SIZE_BYTES"
  exit 22
fi

ACTUAL_SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$ARCHIVE_SHA256" ]]; then
  echo "TAPE_ECHO_2_ARCHIVE=BLOCKED_SHA256_MISMATCH"
  echo "EXPECTED_SHA256=$ARCHIVE_SHA256"
  echo "ACTUAL_SHA256=$ACTUAL_SHA256"
  exit 23
fi

mkdir -p "$EXTRACT_ROOT"
python3 - "$ARCHIVE" "$EXTRACT_ROOT" <<'PY'
import pathlib
import sys
import zipfile

archive = pathlib.Path(sys.argv[1])
dest = pathlib.Path(sys.argv[2]).resolve()

with zipfile.ZipFile(archive) as zf:
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if dest != target and dest not in target.parents:
            raise SystemExit("TAPE_ECHO_2_ARCHIVE=BLOCKED_PATH_TRAVERSAL")
    zf.extractall(dest)
PY

SOURCE_DIR="$EXTRACT_ROOT/VST3/tape-echo-2.vst3"
if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "TAPE_ECHO_2_ARCHIVE=BLOCKED_UNEXPECTED_LAYOUT"
  exit 24
fi

if ! find "$SOURCE_DIR" -type f -print -quit | grep -q .; then
  echo "TAPE_ECHO_2_ARCHIVE=BLOCKED_EMPTY_PLUGIN"
  exit 25
fi

STAGED_DIR="${INSTALL_DIR}.new"
rm -rf "$STAGED_DIR"
cp -a "$SOURCE_DIR" "$STAGED_DIR"
rm -rf "$INSTALL_DIR"
mv "$STAGED_DIR" "$INSTALL_DIR"
chmod -R u+rwX,go-rwx "$INSTALL_DIR"

cat >"$RECEIPT" <<EOF
TAPE_ECHO_2_VERSION=$TAPE_ECHO_2_VERSION
TAPE_ECHO_2_TAG=$TAPE_ECHO_2_TAG
DOWNLOAD_URL=$DOWNLOAD_URL
ARCHIVE_SHA256=$ARCHIVE_SHA256
ARCHIVE_SIZE_BYTES=$SIZE_BYTES
VST3_PATH=$INSTALL_DIR
EOF
chmod 600 "$RECEIPT"

echo "TAPE_ECHO_2_INSTALL=PASS"
echo "TAPE_ECHO_2_VERSION=$TAPE_ECHO_2_VERSION"
echo "ARCHIVE_SHA256=$ARCHIVE_SHA256"
echo "VST3_PATH=$INSTALL_DIR"
echo "REAPER_RESCAN_REQUIRED=TRUE"
