#!/usr/bin/env bash
# Stage FyahReaper Remote only in the already existing Hazewave Codespace.
# Never switch the owner's checkout, run a second REAPER, or touch user media.
set -Eeuo pipefail
REPO=/workspaces/Hazewave-
APPROVED=hazewave-zero-cost-4jxp45676rq6279xx
PIN=ce69288070b65e8b1f0c761a0ae1bbbfd0d89221
ROOT="$HOME/.local/share/hazewave/fyahreaper-remote"
RELEASE="$ROOT/source-$PIN"
if [[ -n "${CODESPACE_NAME:-}" && "$CODESPACE_NAME" != "$APPROVED" ]]; then
  echo BLOCKED:WRONG_CODESPACE; exit 3
fi
[[ -d "$REPO/.git" || -f "$REPO/.git" ]] || { echo BLOCKED:REPO_NOT_FOUND; exit 3; }
[[ -x /home/vscode/.local/opt/reaper/7.82/REAPER/reaper ]] || {
  echo BLOCKED:EXISTING_REAPER_7_82_MISSING; exit 3;
}
[[ ! -L "$ROOT" && ! -L "$RELEASE" ]] || { echo BLOCKED:SYMLINK; exit 3; }
head_before="$(git -C "$REPO" rev-parse HEAD)"
status_before="$(git -C "$REPO" status --porcelain=v1)"
git -C "$REPO" fetch --no-tags origin refs/heads/work/fyahreaper-remote-mvp-v1
git -C "$REPO" merge-base --is-ancestor "$PIN" FETCH_HEAD || {
  echo BLOCKED:CANDIDATE_DOES_NOT_CONTAIN_PIN; exit 3;
}
git -C "$REPO" cat-file -e "${PIN}^{commit}"
mkdir -p "$ROOT"
temporary="$(mktemp -d "$ROOT/.verify-XXXXXXXX")"
trap 'rm -rf "$temporary"' EXIT
git -C "$REPO" archive "$PIN" apps/fyahreaper_remote | tar -xf - -C "$temporary"
if [[ -e "$RELEASE" ]]; then
  [[ -d "$RELEASE" ]] && diff -qr "$temporary" "$RELEASE" >/dev/null || {
    echo BLOCKED:RELEASE_CONFLICT_PRESERVED; exit 4;
  }
else
  mv "$temporary" "$RELEASE"
  temporary=""
fi
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$head_before" ]] || {
  echo BLOCKED:CHECKOUT_CHANGED; exit 6;
}
[[ "$(git -C "$REPO" status --porcelain=v1)" == "$status_before" ]] || {
  echo BLOCKED:USER_WIP_CHANGED; exit 6;
}
echo FYAHREAPER_STAGE=PASS
echo FYAHREAPER_PIN="$PIN"
echo FYAHREAPER_SOURCE="$RELEASE/apps/fyahreaper_remote"
echo FYAHREAPER_ORIGINAL_HEAD_UNCHANGED=PASS
echo FYAHREAPER_ORIGINAL_WIP_UNCHANGED=PASS
echo FYAHREAPER_REAPER_SESSION_UNTOUCHED=PASS
echo FYAHREAPER_REAPY_CONFIGURED=NOT_CHECKED
echo FYAHREAPER_MOBILE_E2E=NOT_RUN
