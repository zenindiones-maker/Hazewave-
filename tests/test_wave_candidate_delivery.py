"""Adversarial CI/CD source-only gates; no private art, deployment or live host."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ci/wave_candidate_delivery.py"
spec = spec_from_file_location("wave_candidate_delivery", SCRIPT)
assert spec and spec.loader
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True,
        check=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "working"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "ci@example.invalid")
    _git(root, "config", "user.name", "CI Fixture")
    for name in mod.FILES:
        path = root / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text("HAZEWAVE_SOURCE_FIXTURE_ONLY\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture commit")
    return root, _git(root, "rev-parse", "HEAD")


def test_source_package_delivers_exact_head_bytes_without_owner_media(repo, tmp_path):
    root, sha = repo
    result = tmp_path / "source-only.zip"
    receipt = mod.create_package(root, result, expected_sha=sha)
    verified = mod.verify_package(result, expected_sha=sha)
    assert verified == receipt
    assert receipt["production_approved"] is False
    assert receipt["deployment_attempted"] is False
    with ZipFile(result) as zipfile:
        names = zipfile.namelist()
        assert len(names) == len(mod.FILES) + 1
        assert names[0] == "manifest.json"
        assert all(name.endswith((".html", ".css", ".js", ".py", ".md", ".json"))
                   for name in names)
        meta = json.loads(zipfile.read("manifest.json"))
        assert meta["media_bytes_embedded"] == 0
        assert meta["private_assets_present"] is False
        assert meta["source_only"] is True
        assert meta["production_approved"] is False
        assert meta["reviewed_sha"] == sha


def test_package_rebuild_is_deterministic_and_existing_outputs_refused(repo, tmp_path):
    root, sha = repo
    a = tmp_path / "candidate-a.zip"
    b = tmp_path / "candidate-b.zip"
    ra = mod.create_package(root, a, expected_sha=sha)
    rb = mod.create_package(root, b, expected_sha=sha)
    assert ra["archive_sha256"] == rb["archive_sha256"]
    with pytest.raises(mod.DeliveryDenied, match="EXISTS"):
        mod.create_package(root, a, expected_sha=sha)


def test_worktree_dirty_source_is_denied_before_delivery(repo, tmp_path):
    root, sha = repo
    (root / mod.FILES[0]).write_text("Modified private unauthorized WIP")
    out = tmp_path / "no-archive.zip"
    with pytest.raises(mod.DeliveryDenied, match="WORKTREE_SOURCE_DIFFERS_FROM_HEAD"):
        mod.create_package(root, out, expected_sha=sha)
    assert not out.exists()


def test_wrong_sha_and_repo_output_denied(repo, tmp_path):
    root, sha = repo
    with pytest.raises(mod.DeliveryDenied, match="EXACT_HEAD_BINDING_FAILED"):
        mod.create_package(root, tmp_path / "invalid.zip",
                           expected_sha="a" * 40)
    with pytest.raises(mod.DeliveryDenied, match="DELIVERY_OUTPUT_NOT_PRIVATE"):
        mod.create_package(root, root / "staged.zip", expected_sha=sha)


def test_refuse_mutated_archive_and_receipt(repo, tmp_path):
    root, sha = repo
    out = tmp_path / "candidate.zip"
    mod.create_package(root, out, expected_sha=sha)
    receipt_path = out.with_name(out.name + ".receipt.json")
    receipt = json.loads(receipt_path.read_text())
    receipt["archive_sha256"] = "b" * 64
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(mod.DeliveryDenied, match="DELIVERY_RECEIPT_UNTRUSTED"):
        mod.verify_package(out, expected_sha=sha)
    receipt_path.unlink()
    with pytest.raises(mod.DeliveryDenied, match="DELIVERY_RECEIPT_NOT_FOUND"):
        mod.verify_package(out, expected_sha=sha)


def test_untracked_private_media_never_gets_into_package(repo, tmp_path):
    root, sha = repo
    art = root / "apps/hazewave-site/experiments/travessia-v4/assets/secret-owner.png"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_bytes(b"PRIVATE_OWNER_IMAGE")
    out = tmp_path / "source.zip"
    mod.create_package(root, out, expected_sha=sha)
    with ZipFile(out) as archive:
        assert all("secret-owner" not in path for path in archive.namelist())
        assert all(not path.endswith(".png") for path in archive.namelist())
    assert art.read_bytes() == b"PRIVATE_OWNER_IMAGE"


def test_source_script_cannot_execute_deployment_or_import_network():
    code = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("git push", "gh codespace create", "curl |", "requests.get(",
                      "aws s3", "kubectl", "deploy_prod", "gh release create",
                      "npm publish", "gh pages"):
        assert forbidden not in code
    assert len(mod.FILES) == 9
