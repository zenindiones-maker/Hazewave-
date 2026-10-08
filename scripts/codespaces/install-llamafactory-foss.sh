#!/usr/bin/env bash
# Exact MIT? No: official Apache-2.0 LLaMA-Factory v0.9.5, installed as a
# verified, metadata-only wheel until GPU/rights/resource gates are met.
# Executes ONLY on the preexisting Hazewave Codespace and reviewed clean SHA.
set -euo pipefail

fail() { printf 'HAZEWAVE_LLAMA_FACTORY=BLOCKED:%s\n' "$1" >&2; exit 20; }

[[ $# -eq 1 ]] || fail "EXPLICIT_MODE_REQUIRED"
case "$1" in
  --preflight|--install|--doctor|--training-preflight) mode="$1" ;;
  *) fail "MODE_NOT_ADMITTED" ;;
esac
[[ "${CODESPACE_NAME:-}" == "hazewave-zero-cost-4jxp45676rq6279xx" ]] || fail "WRONG_CODESPACE"
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../.." && pwd -P)"
EXPECTED="${HAZEWAVE_LLAMA_EXPECTED_SHA:-}"
[[ "$EXPECTED" =~ ^[a-f0-9]{40}$ ]] || fail "EXACT_REVIEWED_SHA_REQUIRED"
[[ "$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)" == "$EXPECTED" ]] || fail "HEAD_DRIFT"
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || fail "DIRTY_WORKTREE"
remote="$(git -C "$ROOT" remote get-url origin 2>/dev/null)" || fail "REMOTE_MISSING"
case "$remote" in
  https://github.com/zenindiones-maker/Hazewave-|https://github.com/zenindiones-maker/Hazewave-.git|git@github.com:zenindiones-maker/Hazewave-|git@github.com:zenindiones-maker/Hazewave-.git) ;;
  *) fail "REPO_IDENTITY_DRIFT" ;;
esac
[[ -f "$ROOT/config/llamafactory-training-policy-v1.json" ]] || fail "TRAINING_POLICY_MISSING"
[[ -f "$ROOT/src/hazewave/llamafactory_install.py" ]] || fail "PINNED_INSTALLER_MISSING"

PY=""
for name in python3.12 python3.13 python3.11 python3; do
  if command -v "$name" >/dev/null 2>&1; then
    version="$("$name" -c 'import sys;print(int((3,11) <= sys.version_info[:2] <= (3,13)))' 2>/dev/null || true)"
    if [[ "$version" == 1 ]]; then PY="$(command -v "$name")"; break; fi
  fi
done
[[ -n "$PY" ]] || fail "SUPPORTED_PYTHON_3_11_TO_3_13_REQUIRED"
FREE_KIB="$(df -Pk "$HOME" | awk 'NR==2{print $4}')"
RAM_KIB="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ "$FREE_KIB" =~ ^[0-9]+$ && "$RAM_KIB" =~ ^[0-9]+$ ]] || fail "RESOURCE_BUDGET_UNKNOWN"
(( FREE_KIB >= 1024*1024 )) || fail "DISK_BELOW_1GIB"
(( RAM_KIB >= 512*1024 )) || fail "RAM_BELOW_512MIB"
export PYTHONPATH="$ROOT/src"

ENV_ROOT="$HOME/.local/share/hazewave/llamafactory/0.9.5"
ENV_PY="$ENV_ROOT/venv/bin/python"
WHEEL="llamafactory-0.9.5-py3-none-any.whl"
SHA256="10776e9b259798bf65f6c5343f6298f0302e92e9cd47472abe29eef69e286c6a"

if [[ "$mode" == "--preflight" ]]; then
  printf 'HAZEWAVE_LLAMA_PYTHON=%s\n' "$PY"
  printf 'HAZEWAVE_LLAMA_DISK_FREE_KIB=%s\n' "$FREE_KIB"
  printf 'HAZEWAVE_LLAMA_MEM_AVAILABLE_KIB=%s\n' "$RAM_KIB"
  echo "HAZEWAVE_LLAMA_PREFLIGHT=PASS"
  echo "HAZEWAVE_LLAMA_INSTALL=NOT_ATTEMPTED"
  echo "LLAMA_FACTORY_TRAINING=NOT_PROVEN"
  exit 0
fi

if [[ "$mode" == "--install" ]]; then
  command -v sha256sum >/dev/null 2>&1 || fail "SHA256SUM_MISSING"
  [[ ! -L "$ENV_ROOT" && ! -L "$ENV_ROOT/venv" ]] || fail "INSTALL_DIR_SYMLINK"
  if [[ -f "$ENV_PY" ]]; then
    "$PY" -m hazewave.llamafactory_install doctor --python "$ENV_PY" || fail "EXISTING_PINNED_INSTALL_INVALID"
    echo "HAZEWAVE_LLAMA_INSTALL=PASS:EXISTING_VERIFIED_PACKAGE"
    echo "LLAMA_FACTORY_TRAINING=NOT_PROVEN"
    exit 0
  fi
  stage="$(mktemp -d)"
  trap 'rm -rf -- "$stage"' EXIT
  # Exact PyPI wheel file, no dependencies, no index substitution without SHA.
  "$PY" -m pip download --disable-pip-version-check --no-cache-dir --no-deps \
    --only-binary=:all: --dest "$stage" "llamafactory==0.9.5" \
    || fail "PINNED_WHEEL_DOWNLOAD_FAILED"
  [[ -f "$stage/$WHEEL" ]] || fail "PINNED_WHEEL_ABSENT"
  printf '%s  %s\n' "$SHA256" "$stage/$WHEEL" | sha256sum -c - >/dev/null \
    || fail "PINNED_WHEEL_CHECKSUM_MISMATCH"
  "$PY" -m hazewave.llamafactory_install verify-wheel --wheel "$stage/$WHEEL" \
    || fail "WHEEL_UPSTREAM_MISMATCH"
  mkdir -p "$ENV_ROOT"
  chmod 0700 "$ENV_ROOT"
  "$PY" -m venv "$ENV_ROOT/venv" || fail "VENV_CREATION_FAILED"
  "$ENV_PY" -m pip install --disable-pip-version-check --no-index --no-deps \
    "$stage/$WHEEL" || fail "PINNED_DISTRIBUTION_INSTALL_FAILED"
  "$PY" -m hazewave.llamafactory_install doctor --python "$ENV_PY" \
    || fail "PINNED_DISTRIBUTION_DOCTOR_FAILED"
  echo "HAZEWAVE_LLAMA_INSTALL=VERSION_INSTALLED_METADATA_ONLY"
  echo "LLAMA_FACTORY_TRAINING=NOT_PROVEN"
  echo "LLAMA_FACTORY_CLI_RUNTIME=NOT_PROVEN"
  exit 0
fi

[[ -f "$ENV_PY" ]] || fail "ISOLATED_PACKAGE_NOT_INSTALLED"
"$PY" -m hazewave.llamafactory_install doctor --python "$ENV_PY" \
  || fail "INSTALLED_METADATA_DRIFT"
if [[ "$mode" == "--doctor" ]]; then
  echo "HAZEWAVE_LLAMA_DOCTOR=PASS:DISTRIBUTION_METADATA"
  echo "LLAMA_FACTORY_TRAINING=NOT_PROVEN"
  echo "LLAMA_FACTORY_CLI_RUNTIME=NOT_PROVEN"
  exit 0
fi

# Training preflight is deliberately read-only. NO model, weights, datasets or
# heavyweight torch dependencies are fetched or executed on this Codespace.
if ! command -v nvidia-smi >/dev/null 2>&1; then
  fail "GPU_UNAVAILABLE_NO_TRAINING"
fi
if ! nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits >/dev/null 2>&1; then
  fail "GPU_NOT_ACCESSIBLE"
fi
(( RAM_KIB >= 16*1024*1024 )) || fail "TRAINING_RAM_BELOW_16GIB"
(( FREE_KIB >= 20*1024*1024 )) || fail "TRAINING_DISK_BELOW_20GIB"
echo "LLAMA_FACTORY_GPU_DISCOVERED=YES"
echo "LLAMA_FACTORY_TRAINING=BLOCKED:MODEL_DATASET_SIGNED_GRANT_AND_DEPENDENCIES_PENDING"
exit 20
