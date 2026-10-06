#!/usr/bin/env bash
set -euo pipefail

SESSION=":100"
PORT="14500"
SCRATCH="/tmp/hazewave-scratch"
CACHE="/tmp/hazewave-cache"

if [[ "${CODESPACES:-}" != "true" ]]; then
  echo "HAZEWAVE_PRO=BLOCKED_NOT_CODESPACES"
  exit 20
fi

command -v xpra >/dev/null || {
  echo "HAZEWAVE_PRO=BLOCKED_XPRA_MISSING"
  exit 21
}

mkdir -p "$SCRATCH" "$CACHE"

ARDOUR_BIN=""
for candidate in ardour9 ardour8 ardour7 ardour6 ardour; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ARDOUR_BIN="$(command -v "$candidate")"
    break
  fi
done

[[ -n "$ARDOUR_BIN" ]] || {
  echo "ARDOUR=BLOCKED_NOT_INSTALLED"
  exit 22
}

if ! xpra list 2>/dev/null | grep -Eq "LIVE.*${SESSION}|\${SESSION}.*LIVE"; then
  xpra start-desktop "$SESSION" \
    --bind-tcp="127.0.0.1:${PORT},auth=none" \
    --html=on \
    --pulseaudio=yes \
    --speaker=on \
    --microphone=disabled \
    --webcam=no \
    --file-transfer=off \
    --open-files=off \
    --mdns=no \
    --sharing=no \
    --start-new-commands=no \
    --resize-display=1600x900 \
    --session-name="Hazewave Professional" \
    --env="TMPDIR=${SCRATCH}" \
    --env="XDG_CACHE_HOME=${CACHE}" \
    --start-child="xfce4-session" \
    --start="$ARDOUR_BIN" \
    --exit-with-children=no \
    --daemon=yes
fi

for _ in $(seq 1 40); do
  curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 && break
  sleep 1
done

curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null

LISTEN_LINE="$(ss -ltn 2>/dev/null | awk -v p=":${PORT}" '$4 ~ p"$" {print $4; exit}')"
case "$LISTEN_LINE" in
  127.0.0.1:${PORT}) ;;
  *)
    echo "XPRA_BIND=FAIL"
    echo "LISTEN=${LISTEN_LINE:-NONE}"
    exit 23
    ;;
esac

echo "HAZEWAVE_PRO_DESKTOP=PASS"
echo "REMOTE_TRANSPORT=XPRA_HTML5"
echo "XPRA_PORT=$PORT"
echo "XPRA_BIND=LOOPBACK_ONLY"
echo "SPEAKER_FORWARDING=ENABLED"
echo "MICROPHONE_FORWARDING=DISABLED"
echo "NOVNC_FALLBACK_PORT=6080"
echo "SCRATCH_ROOT=$SCRATCH"
echo "REFERENCE_QC=LOCAL_A15"
