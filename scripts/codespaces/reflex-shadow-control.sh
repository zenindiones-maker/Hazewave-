#!/usr/bin/env bash
set -euo pipefail
umask 077

# Run from existing Hazewave Codespace; never switch the active branch.
MAIN_REPO="/workspaces/Hazewave-"
REF="work/hazewave-always-ready-v1"
EXPECTED_CODESPACE="${HAZEWAVE_REFLEX_EXPECTED_CODESPACE:-hazewave-zero-cost-4jxp45676rq6279xx}"
RUN_ROOT="${HOME}/.local/share/hazewave/reflex-shadow-runtime"
SOURCE_ROOT="${HOME}/.local/share/hazewave/providers/colibri/source"
MODEL_ROOT="${HOME}/.local/share/hazewave/models/colibri/laya"
STATE_ROOT="${HOME}/.local/state/hazewave/reflex"
WORKTREE="${RUN_ROOT}/checkout"
SECRET_FILE="${STATE_ROOT}/colibri-api-key"
PORT=28080
SERVICE_ROOT="${STATE_ROOT}/service"
SERVICE_PID_FILE="${SERVICE_ROOT}/reflex.pid"
SERVICE_META_FILE="${SERVICE_ROOT}/service.json"
SERVICE_LOG_FILE="${SERVICE_ROOT}/reflex.log"
SERVICE_LOCK_FILE="${SERVICE_ROOT}/reconcile.lock"
SERVICE_FAILURE_FILE="${SERVICE_ROOT}/restart-failures.json"
SERVICE_RECEIPT_ROOT="${SERVICE_ROOT}/receipts"
RESTART_WINDOW_SECONDS=900
RESTART_BUDGET=3
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
  else
    [[ -z "$(git -C "$WORKTREE" status --porcelain)" ]] || die "ISOLATED_CHECKOUT_DIRTY"
    if [[ "$(git -C "$WORKTREE" rev-parse HEAD)" != "$remote_sha" ]]; then
      git -C "$WORKTREE" checkout --detach "$remote_sha" || die "WORKTREE_FAST_RECONCILE_FAILED"
    fi
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


build_scheduler_engine_variant() {
  local variant="$1"
  local root="$HOME/.local/share/hazewave/providers/colibri/derived/$variant"
  local binary="$root/c/laya"
  local meta="$root/build.json"
  local expected_sha="bf2442915d6e3dd4cdfd2eb9c2a3d2aa44a25850"

  [[ "$(git -C "$SOURCE_ROOT" rev-parse HEAD)" == "$expected_sha" ]] || die "ENGINE_TUNE_UPSTREAM_SHA_MISMATCH"
  [[ -z "$(git -C "$SOURCE_ROOT" status --porcelain)" ]] || die "ENGINE_TUNE_UPSTREAM_SOURCE_DIRTY"

  if [[ -x "$binary" && -f "$meta" ]]; then
    local recorded current
    recorded="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["binary_sha256"])' "$meta" 2>/dev/null || true)"
    current="$(sha256sum "$binary" | awk '{print $1}')"
    [[ -n "$recorded" && "$recorded" == "$current" ]] || die "ENGINE_TUNE_DERIVED_BINARY_METADATA_MISMATCH:$variant"
    printf '%s\n' "$binary"
    return 0
  fi

  [[ ! -e "$root" ]] || die "ENGINE_TUNE_DERIVED_ROOT_OCCUPIED:$variant"
  mkdir -p "$(dirname "$root")"
  local stage
  stage="$(mktemp -d "$root.stage.XXXXXX")"
  mkdir -p "$stage"
  git -C "$SOURCE_ROOT" archive HEAD c | tar -x -C "$stage" || die "ENGINE_TUNE_SOURCE_ARCHIVE_FAILED:$variant"

  if ! "$PYTHON_BIN" - "$stage/c" "$variant" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
variant = sys.argv[2]

if variant in {"static_attention_v2", "static_all_f32_v2"}:
    p = root / "laya.c"
    text = p.read_text(encoding="utf-8")
    old = "#pragma omp for schedule(dynamic, 8)"
    if text.count(old) != 1:
        raise SystemExit("ENGINE_TUNE_ATTENTION_PATCH_ANCHOR_INVALID")
    p.write_text(text.replace(old, "#pragma omp for schedule(static)", 1), encoding="utf-8")

if variant in {"static_gemm_f32_v2", "static_all_f32_v2"}:
    p = root / "qi_gemm.h"
    text = p.read_text(encoding="utf-8")
    old = "#pragma omp for schedule(dynamic, 1) collapse(2)"
    # There are two occurrences upstream: the first is the f32 GEMM used by
    # Laya here; the second belongs to the opt-in int8 activation path. Patch
    # only the first and require the pinned source shape to remain recognizable.
    if text.count(old) != 2:
        raise SystemExit("ENGINE_TUNE_GEMM_F32_PATCH_ANCHOR_INVALID")
    p.write_text(text.replace(old, "#pragma omp for schedule(static) collapse(2)", 1), encoding="utf-8")
PY
  then
    rm -rf "$stage"
    die "ENGINE_TUNE_SOURCE_PATCH_FAILED:$variant"
  fi

  make -C "$stage/c" laya >/dev/null || { rm -rf "$stage"; die "ENGINE_TUNE_BUILD_FAILED:$variant"; }
  [[ -x "$stage/c/laya" ]] || { rm -rf "$stage"; die "ENGINE_TUNE_BINARY_MISSING:$variant"; }

  local patch_sha binary_sha
  patch_sha="$(
    {
      git -C "$SOURCE_ROOT" show HEAD:c/laya.c
      git -C "$SOURCE_ROOT" show HEAD:c/qi_gemm.h
      cat "$stage/c/laya.c" "$stage/c/qi_gemm.h"
      printf '%s\n' "$variant"
    } | sha256sum | awk '{print $1}'
  )"
  binary_sha="$(sha256sum "$stage/c/laya" | awk '{print $1}')"

  mkdir -p "$(dirname "$root")"
  mv "$stage" "$root"

  "$PYTHON_BIN" - "$meta" "$variant" "$expected_sha" "$patch_sha" "$binary_sha" <<'PY'
import json, os, sys
from pathlib import Path
p = Path(sys.argv[1])
row = {
    "schema": "HazewaveReflexDerivedEngineBuild/v1",
    "variant": sys.argv[2],
    "upstream_commit": sys.argv[3],
    "patch_sha256": sys.argv[4],
    "binary_sha256": sys.argv[5],
    "changes_model_or_precision": False,
    "scheduling_only": True,
    "provider_authority": "NONE",
}
fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as out:
    json.dump(row, out, sort_keys=True, separators=(",", ":"))
    out.write("\n")
PY
  printf '%s\n' "$binary"
}

latency_engine_tune() {
  ensure_checkout
  "$PYTHON_BIN" -m hazewave.reflex_shadow_runtime doctor --repository-root "$WORKTREE" >/dev/null || die "RUNTIME_DOCTOR_BLOCKED"
  [[ -f "$SECRET_FILE" && ! -L "$SECRET_FILE" ]] || die "COLIBRI_SECRET_MISSING"
  [[ "$(stat -c %a "$SECRET_FILE")" == "600" ]] || die "COLIBRI_SECRET_PERMISSIONS_INVALID"
  port_is_free || die "ENGINE_TUNE_PORT_BUSY_STOP_SERVE_FIRST"

  local stamp run_dir
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  run_dir="$STATE_ROOT/latency/engine-runs/$stamp"
  mkdir -p "$run_dir"
  chmod 700 "$STATE_ROOT/latency" "$STATE_ROOT/latency/engine-runs" "$run_dir" 2>/dev/null || true
  echo "REFLEX_ENGINE_TUNE_RUN_DIR=$run_dir"
  echo "REFLEX_ENGINE_TUNE_MODE=STOCK_VS_SCHEDULER_DERIVATIVES"
  echo "REFLEX_ENGINE_TUNE_PATCH_POLICY=F32_GEMM_ONLY_FAIL_CLOSED"

  local attn gemm all
  attn="$(build_scheduler_engine_variant static_attention_v2)"
  gemm="$(build_scheduler_engine_variant static_gemm_f32_v2)"
  all="$(build_scheduler_engine_variant static_all_f32_v2)"

  stop_engine_case() {
    local owned_pid="$1"
    "$SOURCE_ROOT/c/coli" stop --port "$PORT" >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      kill -0 "$owned_pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -0 "$owned_pid" 2>/dev/null && kill -TERM "$owned_pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$owned_pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -0 "$owned_pid" 2>/dev/null && kill -KILL "$owned_pid" 2>/dev/null || true
    wait "$owned_pid" 2>/dev/null || true
    port_is_free || die "ENGINE_TUNE_SERVER_DID_NOT_RELEASE_PORT"
  }

  run_case() {
    local label="$1"
    local engine="$2"
    local pid rc
    echo "=== REFLEX ENGINE CASE: $label ==="
    port_is_free || die "ENGINE_TUNE_PORT_NOT_FREE:$label"

    COLI_ENGINE="$engine" "$PYTHON_BIN" -m hazewave.reflex_latency server \
      --source-root "$SOURCE_ROOT" --model-root "$MODEL_ROOT" \
      --secret-file "$SECRET_FILE" --state-root "$STATE_ROOT" \
      --port "$PORT" --profile baseline_2t \
      >"$run_dir/$label.server.log" 2>&1 &
    pid=$!

    if ! wait_health 180; then
      tail -n 60 "$run_dir/$label.server.log" >&2 || true
      stop_engine_case "$pid"
      die "ENGINE_TUNE_SERVER_START_FAILED:$label"
    fi

    set +e
    "$PYTHON_BIN" -m hazewave.reflex_latency measure \
      --profile baseline_2t --secret-file "$SECRET_FILE" >"$run_dir/$label.json"
    rc=$?
    set -e
    stop_engine_case "$pid"
    [[ "$rc" -eq 0 ]] || die "ENGINE_TUNE_MEASURE_FAILED:$label:$rc"

    "$PYTHON_BIN" - "$run_dir/$label.json" "$label" <<'PY'
import json, sys
row = json.load(open(sys.argv[1], encoding="utf-8"))
lat = row["latency"]
print(
    "REFLEX_ENGINE_CASE_RESULT="
    f"{sys.argv[2]}:"
    f"p50={lat['wall']['p50_ms']:.3f}:"
    f"p95={lat['wall']['p95_ms']:.3f}:"
    f"engine_p50={lat['engine']['p50_ms']}:"
    f"failures={row['failed_requests']}:"
    f"robust={row['all_robust_eligible']}"
)
PY
  }

  run_case stock "$SOURCE_ROOT/c/laya"
  run_case static_attention_v2 "$attn"
  run_case static_gemm_f32_v2 "$gemm"
  run_case static_all_f32_v2 "$all"

  "$PYTHON_BIN" - "$run_dir" <<'PY'
import hashlib, json, os, sys
from pathlib import Path
root = Path(sys.argv[1])
names = ["stock", "static_attention_v2", "static_gemm_f32_v2", "static_all_f32_v2"]
rows = {n: json.load(open(root / f"{n}.json", encoding="utf-8")) for n in names}
base = rows["stock"]
bs = [x for x in base["samples"] if x.get("status") == "PASS"]
bp50 = float(base["latency"]["wall"]["p50_ms"])
bp95 = float(base["latency"]["wall"]["p95_ms"])
base_req = [x["request_sha256"] for x in bs]
base_probs = [x["aggregate_probabilities"] for x in bs]
evaluated, accepted = [], []
for name in names[1:]:
    row = rows[name]
    ss = [x for x in row["samples"] if x.get("status") == "PASS"]
    p50 = float(row["latency"]["wall"]["p50_ms"])
    p95 = float(row["latency"]["wall"]["p95_ms"])
    reasons = []
    if len(ss) != row["measured_requests"] or row.get("failed_requests") != 0:
        reasons.append("FAILURES_OR_INCOMPLETE")
    if row.get("all_robust_eligible") is not True:
        reasons.append("ROBUST_ELIGIBILITY_FAILED")
    if [x["request_sha256"] for x in ss] != base_req:
        reasons.append("REQUEST_SEQUENCE_DRIFT")
    exact_probs = [x["aggregate_probabilities"] for x in ss] == base_probs
    if not exact_probs:
        reasons.append("AGGREGATE_PROBABILITY_DRIFT")
    improvement = (bp50 - p50) / bp50
    p95_ratio = p95 / bp95
    if improvement < 0.05:
        reasons.append("P50_IMPROVEMENT_BELOW_5_PERCENT")
    if p95_ratio > 1.03:
        reasons.append("P95_REGRESSION")
    item = {
        "variant": name,
        "p50_ms": p50,
        "p95_ms": p95,
        "p50_improvement_fraction": improvement,
        "p95_ratio": p95_ratio,
        "exact_aggregate_probability_match": exact_probs,
        "reasons": reasons,
    }
    evaluated.append(item)
    if not reasons:
        accepted.append(item)
accepted.sort(key=lambda x: (x["p50_ms"], x["p95_ms"], x["variant"]))
winner = accepted[0]["variant"] if accepted else "stock"
report = {
    "schema": "HazewaveReflexEngineTuneReport/v1",
    "status": "ENGINE_CANDIDATE_MEETS_GATE" if accepted else "STOCK_ENGINE_RETAINED",
    "winner": winner,
    "baseline_p50_ms": bp50,
    "baseline_p95_ms": bp95,
    "evaluated": evaluated,
    "requires_manual_activation": True,
    "changes_model_or_precision": False,
    "provider_authority": "NONE",
    "production_calibrated": False,
}
raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
report["report_sha256"] = hashlib.sha256(raw).hexdigest()
target = root / "engine-selection.json"
fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as out:
    json.dump(report, out, sort_keys=True, separators=(",", ":"))
    out.write("\n")
print(json.dumps(report, sort_keys=True))
PY
  echo "REFLEX_ENGINE_TUNE=PASS"
  echo "REFLEX_ENGINE_TUNE_ACTIVATION=NOT_AUTOMATIC"
}

latency_engine_report() {
  ensure_checkout
  local latest
  latest="$(find "$STATE_ROOT/latency/engine-runs" -mindepth 2 -maxdepth 2 -name engine-selection.json -type f 2>/dev/null | sort | tail -n 1 || true)"
  if [[ -z "$latest" ]]; then
    echo "REFLEX_ENGINE_TUNE_LATEST=NONE"
  else
    echo "REFLEX_ENGINE_TUNE_LATEST=$latest"
    cat "$latest"
  fi
}


runtime_health_once() {
  [[ -f "$SECRET_FILE" && ! -L "$SECRET_FILE" ]] || return 1
  "$PYTHON_BIN" - "$PORT" "$SECRET_FILE" <<'PY' >/dev/null 2>&1
import sys
from pathlib import Path
import httpx

port = int(sys.argv[1])
secret = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
try:
    response = httpx.get(
        f"http://127.0.0.1:{port}/health",
        headers={"Authorization": f"Bearer {secret}"},
        timeout=1.5,
        trust_env=False,
    )
    body = response.json()
except (httpx.HTTPError, ValueError, OSError):
    raise SystemExit(1)
raise SystemExit(0 if response.status_code == 200 and isinstance(body, dict) and body.get("status") == "ok" else 1)
PY
}

restart_budget_check() {
  mkdir -p "$SERVICE_ROOT"
  chmod 700 "$SERVICE_ROOT"
  "$PYTHON_BIN" - "$SERVICE_FAILURE_FILE" "$RESTART_WINDOW_SECONDS" "$RESTART_BUDGET" <<'PY'
import json, sys, time
from pathlib import Path

path = Path(sys.argv[1])
window = int(sys.argv[2])
budget = int(sys.argv[3])
now = int(time.time())
rows = []
if path.exists():
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = [int(x) for x in payload.get("failures", [])]
    except (OSError, ValueError, TypeError):
        raise SystemExit("REFLEX_RESTART_LEDGER_INVALID")
rows = [x for x in rows if now - x <= window]
if len(rows) >= budget:
    print(f"REFLEX_RESTART_BUDGET=EXHAUSTED:{len(rows)}/{budget}")
    raise SystemExit(42)
print(f"REFLEX_RESTART_BUDGET=PASS:{len(rows)}/{budget}")
PY
}

restart_budget_record_failure() {
  mkdir -p "$SERVICE_ROOT"
  chmod 700 "$SERVICE_ROOT"
  "$PYTHON_BIN" - "$SERVICE_FAILURE_FILE" "$RESTART_WINDOW_SECONDS" <<'PY'
import json, os, sys, time
from pathlib import Path

path = Path(sys.argv[1])
window = int(sys.argv[2])
now = int(time.time())
rows = []
if path.exists():
    try:
        rows = [int(x) for x in json.loads(path.read_text(encoding="utf-8")).get("failures", [])]
    except (OSError, ValueError, TypeError):
        rows = []
rows = [x for x in rows if now - x <= window]
rows.append(now)
tmp = path.with_name(path.name + ".tmp")
fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as out:
    json.dump({"schema": "HazewaveReflexRestartFailures/v1", "failures": rows}, out, sort_keys=True, separators=(",", ":"))
    out.write("\n")
os.replace(tmp, path)
PY
}

restart_budget_clear() {
  rm -f "$SERVICE_FAILURE_FILE"
}

write_service_metadata() {
  local action="$1"
  local pid="$2"
  local profile="$3"
  local head source_sha model_sha stamp receipt
  head="$(git -C "$WORKTREE" rev-parse HEAD)"
  source_sha="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
  model_sha="$(sha256sum "$MODEL_ROOT/model.safetensors" | awk '{print $1}')"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$SERVICE_ROOT" "$SERVICE_RECEIPT_ROOT"
  chmod 700 "$SERVICE_ROOT" "$SERVICE_RECEIPT_ROOT"
  receipt="$SERVICE_RECEIPT_ROOT/${stamp}-${pid}-${head:0:12}.json"

  "$PYTHON_BIN" - "$SERVICE_META_FILE" "$receipt" "$action" "$pid" "$profile" "$head" "$source_sha" "$model_sha" "$PORT" <<'PY'
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

meta_path = Path(sys.argv[1])
receipt_path = Path(sys.argv[2])
row = {
    "schema": "HazewaveReflexServiceReadyReceipt/v1",
    "status": "READY",
    "startup_action": sys.argv[3],
    "pid": int(sys.argv[4]),
    "profile": sys.argv[5],
    "worktree_head": sys.argv[6],
    "source_commit": sys.argv[7],
    "model_sha256": sys.argv[8],
    "bind": f"127.0.0.1:{int(sys.argv[9])}",
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "provider_authority": "NONE",
    "grants_execution_authority": False,
    "production_calibrated": False,
}
tmp = meta_path.with_name(meta_path.name + ".tmp")
fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as out:
    json.dump(row, out, sort_keys=True, separators=(",", ":"))
    out.write("\n")
os.replace(tmp, meta_path)
fd = os.open(receipt_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as out:
    json.dump(row, out, sort_keys=True, separators=(",", ":"))
    out.write("\n")
PY
  printf '%s\n' "$pid" >"$SERVICE_PID_FILE.tmp"
  chmod 600 "$SERVICE_PID_FILE.tmp"
  mv "$SERVICE_PID_FILE.tmp" "$SERVICE_PID_FILE"
  echo "REFLEX_RUNTIME_RECEIPT=$receipt"
}

runtime_status() {
  ensure_checkout
  mkdir -p "$SERVICE_ROOT"
  chmod 700 "$SERVICE_ROOT"
  if port_is_free; then
    echo "REFLEX_RUNTIME=STOPPED"
    echo "REFLEX_BIND=127.0.0.1:$PORT"
    return 0
  fi
  if runtime_health_once; then
    echo "REFLEX_RUNTIME=READY"
    echo "REFLEX_BIND=127.0.0.1:$PORT"
    if [[ -f "$SERVICE_META_FILE" ]]; then
      cat "$SERVICE_META_FILE"
    else
      echo "REFLEX_RUNTIME_METADATA=MISSING"
    fi
    return 0
  fi
  echo "REFLEX_RUNTIME=DEGRADED"
  echo "REFLEX_RUNTIME_REASON=PORT_BOUND_HEALTH_FAILED"
  return 18
}


tracked_runtime_pid_matches() {
  local pid="$1"
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
  local cmdline
  cmdline="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$SOURCE_ROOT/c/coli"* ]] || return 1
  [[ "$cmdline" == *" serve "* || "$cmdline" == *" serve" ]] || return 1
  [[ "$cmdline" == *"--port $PORT"* ]] || return 1
}

reconcile() {
  ensure_checkout
  command -v flock >/dev/null || die "FLOCK_MISSING"
  mkdir -p "$SERVICE_ROOT" "$SERVICE_RECEIPT_ROOT"
  chmod 700 "$SERVICE_ROOT" "$SERVICE_RECEIPT_ROOT"

  exec 9>"$SERVICE_LOCK_FILE"
  flock -w 30 9 || die "REFLEX_RECONCILE_LOCK_TIMEOUT"

  "$PYTHON_BIN" -m hazewave.reflex_shadow_runtime doctor --repository-root "$WORKTREE" \
    || die "RUNTIME_DOCTOR_BLOCKED"
  [[ -f "$SECRET_FILE" && ! -L "$SECRET_FILE" ]] || die "COLIBRI_SECRET_MISSING"
  [[ "$(stat -c %a "$SECRET_FILE")" == "600" ]] || die "COLIBRI_SECRET_PERMISSIONS_INVALID"
  model_material_ready || die "MODEL_MATERIAL_NOT_PREPARED"
  [[ -x "$SOURCE_ROOT/c/coli" && -x "$SOURCE_ROOT/c/laya" ]] || die "COLIBRI_RUNTIME_NOT_PREPARED"

  local profile profile_reply current_head meta_head meta_profile pid
  if ! profile_reply="$("$PYTHON_BIN" -m hazewave.reflex_latency resolved --state-root "$STATE_ROOT")"; then
    echo "REFLEX_SELECTED_PROFILE_DETAIL=$profile_reply" >&2
    die "REFLEX_SELECTED_PROFILE_INVALID"
  fi
  profile="$profile_reply"
  current_head="$(git -C "$WORKTREE" rev-parse HEAD)"

  if ! port_is_free; then
    if ! runtime_health_once; then
      die "REFLEX_PORT_BOUND_UNHEALTHY"
    fi

    meta_head=""
    meta_profile=""
    pid=""
    if [[ -f "$SERVICE_META_FILE" ]]; then
      meta_head="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("worktree_head",""))' "$SERVICE_META_FILE" 2>/dev/null || true)"
      meta_profile="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("profile",""))' "$SERVICE_META_FILE" 2>/dev/null || true)"
      pid="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("pid",""))' "$SERVICE_META_FILE" 2>/dev/null || true)"
    fi

    if [[ "$meta_head" == "$current_head" && "$meta_profile" == "$profile" ]] && tracked_runtime_pid_matches "$pid"; then
      echo "REFLEX_RECONCILE_ACTION=REUSE_HEALTHY"
      echo "REFLEX_RUNTIME_PID=$pid"
      echo "REFLEX_RUNTIME_PROFILE=$profile"
      echo "REFLEX_RUNTIME=READY"
      echo "HAZEWAVE_WORKSTATION_READY=PASS"
      return 0
    fi

    [[ -n "$meta_head" ]] || die "REFLEX_HEALTHY_RUNTIME_UNTRACKED"
    "$SOURCE_ROOT/c/coli" stop --port "$PORT" >/dev/null 2>&1 || die "REFLEX_STALE_RUNTIME_STOP_FAILED"
    for _ in $(seq 1 40); do
      port_is_free && break
      sleep 0.25
    done
    port_is_free || die "REFLEX_STALE_RUNTIME_DID_NOT_RELEASE_PORT"
    echo "REFLEX_RECONCILE_ACTION=RESTART_FOR_TRACKED_DRIFT"
  else
    echo "REFLEX_RECONCILE_ACTION=START_MISSING"
  fi

  if ! restart_budget_check; then
    echo "REFLEX_RUNTIME=DEGRADED"
    echo "RESTART_BUDGET_EXHAUSTED=TRUE"
    die "REFLEX_RESTART_BUDGET_EXHAUSTED"
  fi

  nohup "$PYTHON_BIN" -m hazewave.reflex_latency server \
    --source-root "$SOURCE_ROOT" \
    --model-root "$MODEL_ROOT" \
    --secret-file "$SECRET_FILE" \
    --state-root "$STATE_ROOT" \
    --port "$PORT" \
    9>&- >"$SERVICE_LOG_FILE" 2>&1 < /dev/null &
  pid=$!
  printf '%s\n' "$pid" >"$SERVICE_PID_FILE.tmp"
  chmod 600 "$SERVICE_PID_FILE.tmp"
  mv "$SERVICE_PID_FILE.tmp" "$SERVICE_PID_FILE"

  if ! wait_health 180; then
    restart_budget_record_failure
    tail -n 80 "$SERVICE_LOG_FILE" >&2 || true
    "$SOURCE_ROOT/c/coli" stop --port "$PORT" >/dev/null 2>&1 || true
    for _ in $(seq 1 40); do
      port_is_free && break
      sleep 0.25
    done
    echo "REFLEX_RUNTIME=DEGRADED"
    port_is_free || die "REFLEX_FAILED_START_PORT_STILL_BOUND"
    die "REFLEX_BACKGROUND_START_FAILED"
  fi

  restart_budget_clear
  write_service_metadata "STARTED_OR_RECONCILED" "$pid" "$profile"
  echo "REFLEX_RUNTIME_PID=$pid"
  echo "REFLEX_RUNTIME_PROFILE=$profile"
  echo "REFLEX_RUNTIME=READY"
  echo "REFLEX_BIND=127.0.0.1:$PORT"
  echo "REFLEX_BACKGROUND=DETACHED"
  echo "HAZEWAVE_WORKSTATION_READY=PASS"
}

smoke() {
  # A Codespace may have just resumed from Shutdown. Its filesystem persists,
  # but the detached Colibri/Laya processes do not. Reconcile first so an
  # explicit live smoke is self-contained and never races a missing endpoint.
  reconcile
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
  reconcile) reconcile ;;
  runtime-status) runtime_status ;;
  smoke) smoke ;;
  observe) shift; observe "${1:-}" ;;
  report) report ;;
  latency-profiles) latency_profiles ;;
  latency-selected) latency_selected ;;
  serve-stop) serve_stop ;;
  latency-tune) latency_tune ;;
  latency-report) latency_report ;;
  latency-engine-tune) latency_engine_tune ;;
  latency-engine-report) latency_engine_report ;;
  *) echo "usage: $0 {doctor|prepare|serve|serve-stop|reconcile|runtime-status|smoke|observe EVENT.json|report|latency-profiles|latency-selected|latency-tune|latency-report|latency-engine-tune|latency-engine-report}" >&2; exit 2 ;;
esac
