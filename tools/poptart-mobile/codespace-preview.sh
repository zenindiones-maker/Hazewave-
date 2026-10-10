#!/usr/bin/env bash
# Reversible private preview in the ONE authorized Hazewave Codespace.
set -euo pipefail
EXPECTED_CS="hazewave-zero-cost-4jxp45676rq6279xx"
EXPECTED_SHA="1310635d3a306a46544773bfc77720ce123ede75"
ROOT="$HOME/.local/share/hazewave/poptart-mobile-preview-v1"
STATE="$HOME/.local/state/hazewave/poptart-mobile-preview-v1"
PORT=8777
blocked(){ printf 'BLOCKED=%s\n' "$1" >&2; exit 2; }
attest(){
  [[ "${CODESPACES:-}" == "true" ]] || blocked NOT_CODESPACES
  [[ "${CODESPACE_NAME:-}" == "$EXPECTED_CS" ]] || blocked WRONG_CODESPACE
  remote="$(git -C /workspaces/Hazewave- remote get-url origin 2>/dev/null || true)"
  [[ "$remote" == *"zenindiones-maker/Hazewave-"* ]] || blocked WRONG_REPO
  printf '%s\n' "CODESPACE_IDENTITY=PASS" "REPOSITORY_IDENTITY=PASS"
}
running(){
  [[ -f "$STATE/server.pid" ]] || return 1
  read -r pid < "$STATE/server.pid"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  [[ "$cmd" == *"http.server"* && "$cmd" == *"$ROOT"* ]]
}
attest
case "$1" in
  start)
    [[ "$#" -eq 3 ]] || blocked USAGE_START_ARCHIVE_SHA256
    artifact="$(realpath "$2")"
    expected="$3"
    [[ -f "$artifact" && "$expected" =~ ^[a-f0-9]{64}$ ]] || blocked INPUTS_INVALID
    actual="$(sha256sum "$artifact" | awk '{print $1}')"
    [[ "$actual" == "$expected" ]] || blocked ZIP_SHA256_MISMATCH
    mkdir -p "$ROOT" "$STATE"
    if running; then blocked SERVER_ALREADY_RUNNING; fi
    if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then blocked PORT_ALREADY_USED; fi
    stage="$(mktemp -d "$ROOT/.stage.XXXXXXXX")"
    python3 - "$artifact" "$stage" "$EXPECTED_SHA" <<'PY'
import pathlib,sys,zipfile,stat,json
zip_path,dest,source=sys.argv[1:]
with zipfile.ZipFile(zip_path) as z:
    items=z.infolist()
    if len(items)>3000 or sum(i.file_size for i in items)>120_000_000:
        raise SystemExit("BLOCKED=ZIP_RESOURCE_BUDGET")
    for item in items:
        p=pathlib.PurePosixPath(item.filename)
        if p.is_absolute() or ".." in p.parts or "\\" in item.filename:
            raise SystemExit("BLOCKED=ZIP_PATH")
        if stat.S_IFMT(item.external_attr>>16)==stat.S_IFLNK:
            raise SystemExit("BLOCKED=ZIP_SYMLINK")
    z.extractall(dest)
root=pathlib.Path(dest)
required=["index.html","client.js","hz-mobile.js","hz-mobile.css",
          "hz-sw.js","hz-provenance.json","UPSTREAM-LICENSE",
          "THIRD-PARTY-NOTICES.md","SOURCE-AND-LICENSE.txt",
          "web/boot.mjs","web-engine/src/index.mjs","pattern-core/index.mjs"]
for file in required:
    if not (root/file).is_file(): raise SystemExit("BLOCKED=MISSING:"+file)
p=json.loads((root/"hz-provenance.json").read_text())
if p.get("upstream_sha")!=source or p.get("license")!="AGPL-3.0-only":
    raise SystemExit("BLOCKED=PROVENANCE")
if p.get("android_human_acceptance")!="PENDING":
    raise SystemExit("BLOCKED=APPROVAL_NOT_PENDING")
print("ARTIFACT_VERIFIED=PASS")
PY
    release="$ROOT/release-$actual"
    if [[ -d "$release" ]]; then
      rm -rf -- "$stage"
    else
      mv -- "$stage" "$release"
    fi
    nohup python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$release" > "$STATE/server.log" 2>&1 < /dev/null &
    echo "$!" > "$STATE/server.pid"
    ready=0
    for n in 1 2 3 4 5 6 7 8 9 10; do
      if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/hz-provenance.json" >/dev/null 2>&1; then ready=1; break; fi
      sleep 1
    done
    [[ "$ready" == 1 ]] || blocked SERVER_BOOT_FAILED
    printf '%s\n' "PREVIEW_LOCAL_HTTP=PASS" "BIND=127.0.0.1:$PORT" \
      "PRIVATE_HTTPS_PREVIEW=NOT_ATTESTED" "AUDIO_PASS=PENDING_ANDROID"
    ;;
  status)
    if running; then
      curl -fsS --max-time 3 "http://127.0.0.1:$PORT/hz-provenance.json" >/dev/null \
        && echo "PREVIEW_LOCAL_HTTP=PASS"
      echo "PRIVATE_PORT_VISIBILITY=REQUIRES_CHECK_IN_CODESPACES"
    else echo "PREVIEW_PROCESS=STOPPED"; exit 1; fi
    ;;
  stop)
    if ! running; then blocked NOT_RUNNING_OR_UNTRUSTED_PID; fi
    kill "$pid"
    rm "$STATE/server.pid"
    echo "PREVIEW_STOPPED=PASS"
    ;;
  *) blocked USAGE_START_STATUS_STOP ;;
esac
