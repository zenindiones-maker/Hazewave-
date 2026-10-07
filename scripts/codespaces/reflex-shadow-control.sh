#!/usr/bin/env bash
set -euo pipefail
umask 077

# Run from existing Hazewave Codespace; never switch the active branch.
MAIN_REPO="/workspaces/Hazewave-"
REF="work/reflex-latency-v1"
EXPECTED_CODESPACE="${HAZEWAVE_REFLEX_EXPECTED_CODESPACE:-redesigned-space-bassoon-gxp67g5g7r739w59}"
RUN_ROOT="${HOME}/.local/share/hazewave/reflex-shadow-runtime"
SOURCE_ROOT="${HOME}/.local/share/hazewave/providers/colibri/source"
MODEL_ROOT="${HOME}/.local/share/hazewave/models/colibri/laya"
STATE_ROOT="${HOME}/.local/state/hazewave/reflex"
WORKTREE="${RUN_ROOT}/checkout"
SECRET_FILE="${STATE_ROOT}/colibri-api-key"
PORT=28080
PYTHON_BIN=""
HF_REPO="convaiinnovations/laya"
HF_REVISION="7b928d828b7b0e022f929d9bd2e44165aa270148"
MODEL_WEIGHT_SHA256="891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c"

die() { printf '%s\n' "REFLEX_SHADOW_FAIL_CLOSED=$*" >&2; exit 18; }

resolve_python() {
  local candidate=""

  for candidate in     "$MAIN_REPO/.venv/bin/python"     "$(command -v python3 2>/dev/null || true)"     "$(command -v python 2>/dev/null || true)"
  do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      export PYTHON_BIN
      echo "REFLEX_PYTHON_BIN=$PYTHON_BIN"
      "$PYTHON_BIN" --version
      return 0
    fi
  done

  die "PYTHON_3_10_PLUS_MISSING"
}

check_codespace() {
  local actual="${CODESPACE_NAME:-}"
  local shared="/workspaces/.codespaces/shared/environment-variables.json"

  [[ -d "$MAIN_REPO/.git" ]] || die "EXISTING_HAZEWAVE_REPO_MISSING"
  [[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]] || die "LINUX_X86_64_REQUIRED"
  command -v git >/dev/null || die "GIT_MISSING"

  resolve_python

  if [[ "$actual" != "$EXPECTED_CODESPACE" && -f "$shared" ]]; then
    actual="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("CODESPACE_NAME",""))' "$shared" 2>/dev/null || true)"
  fi

  [[ "$actual" == "$EXPECTED_CODESPACE" ]] || die "EXISTING_CODESPACE_IDENTITY_NOT_VERIFIED"
  export CODESPACE_NAME="$actual"
}

ensure_checkout() {
  check_codespace
  mkdir -p "$RUN_ROOT" "$STATE_ROOT"
  chmod 700 "$RUN_ROOT" "$STATE_ROOT"
  # Fetches refs but never checks out, resets or overwrites the active worktree.
  git -C "$MAIN_REPO" fetch --no-tags origin "refs/heads/$REF:refs/remotes/origin/$REF" || die "REF_FETCH_FAILED"
  local remote_sha
  remote_sha="$(git -C "$MAIN_REPO" rev-parse "refs/remotes/origin/$REF" 2>/dev/null || true)"
  [[ "$remote_sha" =~ ^[a-f0-9]{40}$ ]] || die "REF_NOT_PRESENT_AFTER_FETCH"
  if [[ ! -e "$WORKTREE/.git" ]]; then
    [[ ! -e "$WORKTREE" ]] || die "WORKTREE_PATH_OCCUPIED"
    git -C "$MAIN_REPO" worktree add --detach "$WORKTREE" "$remote_sha" || die "WORKTREE_ADD_FAILED"
  fi
  [[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$remote_sha" ]] || die "CHECKOUT_HEAD_DIFFERS_FROM_CURRENT_REMOTE"
  [[ -z "$(git -C "$WORKTREE" status --porcelain)" ]] || die "ISOLATED_CHECKOUT_DIRTY"
  export PYTHONPATH="$WORKTREE/src${PYTHONPATH:+:$PYTHONPATH}"
}

plan_resources() {
  "$PYTHON_BIN" - <<'PY'
from hazewave.colibri import detect_colibri_hardware,plan_colibri_model
from pathlib import Path
h=detect_colibri_hardware(Path.home()/".local/share/hazewave/models/colibri/laya")
p=plan_colibri_model(model_id="laya",hardware=h)
print("REFLEX_RESOURCE_PLAN="+str(p))
if not p["fits_before_download"]:
    raise SystemExit("REFLEX_HARDWARE_ADMISSION=BLOCKED")
if h.ram_available_bytes < int(2.7*1e9):
    raise SystemExit("REFLEX_AVAILABLE_RAM_HEADROOM=BLOCKED")
PY
}

doctor() {
  ensure_checkout
  "$PYTHON_BIN" -m hazewave.reflex_shadow_runtime doctor --repository-root "$WORKTREE"
}

model_material_ready() {
  [[ -s "$MODEL_ROOT/model.safetensors" ]] || return 1
  [[ -s "$MODEL_ROOT/rl_agent_config.json" ]] || return 1
  [[ -s "$MODEL_ROOT/encoder/config.json" ]] || return 1
  [[ -s "$MODEL_ROOT/tokenizer/tokenizer.json" ]] || return 1
  [[ -s "$MODEL_ROOT/tokenizer/tokenizer_config.json" ]] || return 1

  printf '%s  %s\n' "$MODEL_WEIGHT_SHA256" "$MODEL_ROOT/model.safetensors" \
    | sha256sum -c - >/dev/null 2>&1 || return 1

  "$PYTHON_BIN" - "$MODEL_ROOT" <<'PY' >/dev/null
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for relative in (
    "rl_agent_config.json",
    "encoder/config.json",
    "tokenizer/tokenizer.json",
    "tokenizer/tokenizer_config.json",
):
    with (root / relative).open("r", encoding="utf-8") as handle:
        json.load(handle)
PY
}

download_model_material() {
  if model_material_ready; then
    echo "REFLEX_MODEL_MATERIAL=VERIFIED_EXISTING"
    return 0
  fi

  if [[ -e "$MODEL_ROOT" ]]; then
    die "MODEL_ROOT_PRESENT_BUT_UNVERIFIED"
  fi

  command -v curl >/dev/null || die "CURL_MISSING"

  mkdir -p "$(dirname "$MODEL_ROOT")"
  local stage
  stage="$(mktemp -d "${MODEL_ROOT}.stage.XXXXXX")"
  trap 'rm -rf -- "$stage"' EXIT
  mkdir -p "$stage/encoder" "$stage/tokenizer"

  download_one() {
    local remote_path="$1"
    local local_path="$2"
    local target="$stage/$local_path"
    local partial="${target}.part"

    mkdir -p "$(dirname "$target")"

    curl \
      --fail \
      --location \
      --silent \
      --show-error \
      --retry 4 \
      --retry-delay 2 \
      --connect-timeout 20 \
      --max-time 7200 \
      "https://huggingface.co/$HF_REPO/resolve/$HF_REVISION/$remote_path" \
      --output "$partial" \
      || die "MODEL_DOWNLOAD_FAILED:$remote_path"

    [[ -s "$partial" ]] || die "MODEL_DOWNLOAD_EMPTY:$remote_path"
    mv "$partial" "$target"
  }

  download_one "model.safetensors" "model.safetensors"
  download_one "rl_agent_config.json" "rl_agent_config.json"
  download_one "encoder/config.json" "encoder/config.json"
  download_one "tokenizer/tokenizer.json" "tokenizer/tokenizer.json"
  download_one "tokenizer/tokenizer_config.json" "tokenizer/tokenizer_config.json"

  printf '%s  %s\n' "$MODEL_WEIGHT_SHA256" "$stage/model.safetensors" \
    | sha256sum -c - || die "MODEL_WEIGHT_HASH_MISMATCH"

  "$PYTHON_BIN" - "$stage" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for relative in (
    "rl_agent_config.json",
    "encoder/config.json",
    "tokenizer/tokenizer.json",
    "tokenizer/tokenizer_config.json",
):
    path = root / relative
    with path.open("r", encoding="utf-8") as handle:
        json.load(handle)
print("REFLEX_MODEL_JSON_VALIDATION=PASS")
PY

  [[ ! -e "$MODEL_ROOT" ]] || die "MODEL_ROOT_RACE_DETECTED"
  mv "$stage" "$MODEL_ROOT"
  trap - EXIT

  model_material_ready || die "MODEL_MATERIAL_POST_INSTALL_VERIFY_FAILED"
  echo "REFLEX_MODEL_MATERIAL=DOWNLOADED_PINNED_VERIFIED"
  echo "REFLEX_MODEL_REVISION=$HF_REVISION"
}

prepare() {
  ensure_checkout
  plan_resources
  command -v gcc >/dev/null || die "C_COMPILER_MISSING"
  command -v make >/dev/null || die "MAKE_MISSING"
  command -v curl >/dev/null || die "CURL_MISSING"
  local expected_sha="bf2442915d6e3dd4cdfd2eb9c2a3d2aa44a25850"
  if [[ ! -e "$SOURCE_ROOT/.git" ]]; then
    [[ ! -e "$SOURCE_ROOT" ]] || die "SOURCE_PATH_OCCUPIED"
    mkdir -p "$(dirname "$SOURCE_ROOT")"
    git clone --depth 1 --branch v2.0.0 https://github.com/JustVugg/colibri.git "$SOURCE_ROOT" || die "UPSTREAM_CLONE_FAILED"
  fi
  [[ "$(git -C "$SOURCE_ROOT" rev-parse HEAD)" == "$expected_sha" ]] || die "COLIBRI_SOURCE_SHA_MISMATCH"
  [[ -z "$(git -C "$SOURCE_ROOT" status --porcelain)" ]] || die "COLIBRI_SOURCE_DIRTY"
  make -C "$SOURCE_ROOT/c" laya || die "Laya_BUILD_FAILED"

  download_model_material

  if [[ ! -f "$SECRET_FILE" ]]; then
    "$PYTHON_BIN" - "$SECRET_FILE" <<'PY'
import os,secrets,sys
from pathlib import Path
p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True)
fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,"w") as out:
    out.write(secrets.token_urlsafe(48)+"\n")
PY
  fi
  chmod 600 "$SECRET_FILE"
  doctor
  echo "REFLEX_PREPARE=PASS"
  echo "REFLEX_INFERENCE_PROVEN=FALSE"
}

port_is_free() {
  "$PYTHON_BIN" - "$PORT" <<'PY'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
}

wait_health() {
  local attempts="${1:-120}"
  "$PYTHON_BIN" - "$PORT" "$SECRET_FILE" "$attempts" <<'PY'
import json
import sys
import time
from pathlib import Path
import httpx

port = int(sys.argv[1])
secret = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
attempts = int(sys.argv[3])
url = f"http://127.0.0.1:{port}/health"
headers = {"Authorization": f"Bearer {secret}"}
for _ in range(attempts):
    try:
        reply = httpx.get(url, headers=headers, timeout=1.0, trust_env=False)
        if reply.status_code == 200:
            body = reply.json()
            if isinstance(body, dict) and body.get("status") == "ok":
                print("REFLEX_LATENCY_SERVER_HEALTH=PASS")
                raise SystemExit(0)
    except (httpx.HTTPError, ValueError):
        pass
    time.sleep(1.0)
raise SystemExit("REFLEX_LATENCY_SERVER_HEALTH_TIMEOUT")
PY
}

serve() {
  ensure_checkout
  "$PYTHON_BIN" -m hazewave.reflex_shadow_runtime doctor --repository-root "$WORKTREE" >/dev/null || die "RUNTIME_DOCTOR_BLOCKED"
  [[ -f "$SECRET_FILE" && ! -L "$SECRET_FILE" ]] || die "COLIBRI_SECRET_MISSING"
  [[ "$(stat -c %a "$SECRET_FILE")" == "600" ]] || die "COLIBRI_SECRET_PERMISSIONS_INVALID"
  port_is_free || die "REFLEX_PORT_ALREADY_BOUND"
  echo "REFLEX_COLIBRI_SERVE=FOREGROUND"
  echo "REFLEX_MODEL=laya"
  echo "REFLEX_BIND=127.0.0.1:$PORT"
  exec "$PYTHON_BIN" -m hazewave.reflex_latency server \
    --source-root "$SOURCE_ROOT" \
    --model-root "$MODEL_ROOT" \
    --secret-file "$SECRET_FILE" \
    --state-root "$STATE_ROOT" \
    --port "$PORT"
}

latency_profiles() {
  ensure_checkout
  "$PYTHON_BIN" -m hazewave.reflex_latency profiles
}

latency_selected() {
  ensure_checkout
  "$PYTHON_BIN" -m hazewave.reflex_latency selected --state-root "$STATE_ROOT"
}

serve_stop() {
  ensure_checkout
  if port_is_free; then
    echo "REFLEX_SERVE_STOP=ALREADY_STOPPED"
    echo "REFLEX_BIND=127.0.0.1:$PORT"
    return 0
  fi

  [[ -x "$SOURCE_ROOT/c/coli" ]] || die "COLIBRI_LAUNCHER_MISSING"
  "$SOURCE_ROOT/c/coli" stop --port "$PORT" || die "REFLEX_SERVE_STOP_FAILED"

  for _ in $(seq 1 40); do
    port_is_free && break
    sleep 0.25
  done

  port_is_free || die "REFLEX_SERVE_PORT_STILL_BUSY"
  echo "REFLEX_SERVE_STOP=PASS"
  echo "REFLEX_BIND=127.0.0.1:$PORT"
}

latency_tune() {
  ensure_checkout
  "$PYTHON_BIN" -m hazewave.reflex_shadow_runtime doctor --repository-root "$WORKTREE" >/dev/null || die "RUNTIME_DOCTOR_BLOCKED"
  [[ -f "$SECRET_FILE" && ! -L "$SECRET_FILE" ]] || die "COLIBRI_SECRET_MISSING"
  [[ "$(stat -c %a "$SECRET_FILE")" == "600" ]] || die "COLIBRI_SECRET_PERMISSIONS_INVALID"
  port_is_free || die "LATENCY_TUNE_PORT_BUSY_STOP_SERVE_FIRST"

  local stamp run_dir profile pid rc
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  run_dir="$STATE_ROOT/latency/runs/$stamp"
  mkdir -p "$run_dir"
  chmod 700 "$STATE_ROOT/latency" "$STATE_ROOT/latency/runs" "$run_dir" 2>/dev/null || true

  echo "REFLEX_LATENCY_RUN_DIR=$run_dir"
  echo "REFLEX_LATENCY_MODE=SEQUENTIAL_PROFILE_SWEEP"
  echo "REFLEX_LATENCY_NOTE=one_laya_server_at_a_time"

  mapfile -t profiles < <("$PYTHON_BIN" -m hazewave.reflex_latency profiles)
  [[ "${#profiles[@]}" -ge 2 ]] || die "LATENCY_PROFILE_LIST_INVALID"

  stop_profile_server() {
    local owned_pid="$1"
    if kill -0 "$owned_pid" 2>/dev/null; then
      "$SOURCE_ROOT/c/coli" stop --port "$PORT" >/dev/null 2>&1 || true
      for _ in $(seq 1 20); do
        kill -0 "$owned_pid" 2>/dev/null || break
        sleep 0.25
      done
    fi
    if kill -0 "$owned_pid" 2>/dev/null; then
      kill -TERM "$owned_pid" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$owned_pid" 2>/dev/null || break
        sleep 0.25
      done
    fi
    if kill -0 "$owned_pid" 2>/dev/null; then
      kill -KILL "$owned_pid" 2>/dev/null || true
    fi
    wait "$owned_pid" 2>/dev/null || true
    port_is_free || die "LATENCY_PROFILE_SERVER_DID_NOT_RELEASE_PORT"
  }

  for profile in "${profiles[@]}"; do
    echo "=== REFLEX LATENCY PROFILE: $profile ==="
    port_is_free || die "LATENCY_PROFILE_PORT_NOT_FREE:$profile"

    "$PYTHON_BIN" -m hazewave.reflex_latency server \
      --source-root "$SOURCE_ROOT" \
      --model-root "$MODEL_ROOT" \
      --secret-file "$SECRET_FILE" \
      --state-root "$STATE_ROOT" \
      --port "$PORT" \
      --profile "$profile" \
      >"$run_dir/$profile.server.log" 2>&1 &
    pid=$!

    if ! wait_health 180; then
      tail -n 40 "$run_dir/$profile.server.log" >&2 || true
      stop_profile_server "$pid"
      die "LATENCY_PROFILE_SERVER_START_FAILED:$profile"
    fi

    set +e
    "$PYTHON_BIN" -m hazewave.reflex_latency measure \
      --profile "$profile" \
      --secret-file "$SECRET_FILE" \
      >"$run_dir/$profile.json"
    rc=$?
    set -e

    stop_profile_server "$pid"

    if [[ "$rc" -ne 0 ]]; then
      echo "REFLEX_LATENCY_PROFILE_MEASURE=FAIL:$profile:$rc" >&2
      cat "$run_dir/$profile.json" >&2 || true
      die "LATENCY_PROFILE_MEASURE_FAILED:$profile"
    fi

    "$PYTHON_BIN" - "$run_dir/$profile.json" <<'PY'
import json, sys
row = json.load(open(sys.argv[1], encoding="utf-8"))
lat = row["latency"]
print(
    "REFLEX_LATENCY_PROFILE_RESULT="
    f"{row['profile']}:"
    f"p50={lat['wall']['p50_ms']:.3f}:"
    f"p95={lat['wall']['p95_ms']:.3f}:"
    f"engine_p50={lat['engine']['p50_ms']}:"
    f"failures={row['failed_requests']}:"
    f"robust={row['all_robust_eligible']}"
)
PY
  done

  "$PYTHON_BIN" -m hazewave.reflex_latency select \
    --run-dir "$run_dir" \
    --state-root "$STATE_ROOT"
  echo "REFLEX_LATENCY_TUNE=PASS"
  echo "REFLEX_LATENCY_RESTART_REQUIRED=TRUE"
}

latency_report() {
  ensure_checkout
  local active latest
  active="$("$PYTHON_BIN" -m hazewave.reflex_latency selected --state-root "$STATE_ROOT")"
  latest="$(find "$STATE_ROOT/latency/runs" -mindepth 2 -maxdepth 2 -name selection.json -type f 2>/dev/null | sort | tail -n 1 || true)"
  echo "REFLEX_LATENCY_SELECTED_PROFILE=$active"
  if [[ -n "$latest" ]]; then
    echo "REFLEX_LATENCY_LATEST_SELECTION=$latest"
    cat "$latest"
  else
    echo "REFLEX_LATENCY_LATEST_SELECTION=NONE"
  fi
}

smoke() {
  ensure_checkout
  "$PYTHON_BIN" -m hazewave.reflex_shadow_runtime smoke \
    --repository-root "$WORKTREE" --secret-file "$SECRET_FILE"
}

observe() {
  ensure_checkout
  [[ -n "${1:-}" && -f "$1" ]] || die "OBSERVE_EVENT_FILE_REQUIRED"
  "$PYTHON_BIN" -m hazewave.reflex_shadow_runtime observe \
    --repository-root "$WORKTREE" --secret-file "$SECRET_FILE" --event-file "$1"
}

report() {
  ensure_checkout
  "$PYTHON_BIN" -m hazewave.reflex_shadow_runtime report
}

case "${1:-}" in
  doctor) doctor ;;
  prepare) prepare ;;
  serve) serve ;;
  smoke) smoke ;;
  observe) shift; observe "${1:-}" ;;
  report) report ;;
  latency-profiles) latency_profiles ;;
  latency-selected) latency_selected ;;
  serve-stop) serve_stop ;;
  latency-tune) latency_tune ;;
  latency-report) latency_report ;;
  *) echo "usage: $0 {doctor|prepare|serve|serve-stop|smoke|observe EVENT.json|report|latency-profiles|latency-selected|latency-tune|latency-report}" >&2; exit 2 ;;
esac
