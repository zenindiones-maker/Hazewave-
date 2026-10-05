#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hazewave.nvidia import DEFAULT_NVIDIA_SECRET_PATH
from hazewave.nvidia_proof import audit_nvidia_secret_boundary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-file", default=str(DEFAULT_NVIDIA_SECRET_PATH))
    args = parser.parse_args()

    result = audit_nvidia_secret_boundary(
        repo_root=ROOT,
        secret_path=args.secret_file,
    )
    for key in (
        "NVIDIA_KEY_IN_GIT",
        "NVIDIA_KEY_IN_WORKTREE",
        "NVIDIA_KEY_IN_STATE",
        "git_leak_count",
        "worktree_leak_count",
        "state_leak_count",
    ):
        print(f"{key}={result[key]}")
    return 0 if (
        result["NVIDIA_KEY_IN_GIT"] == "PASS"
        and result["NVIDIA_KEY_IN_WORKTREE"] == "PASS"
        and result["NVIDIA_KEY_IN_STATE"] == "PASS"
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
