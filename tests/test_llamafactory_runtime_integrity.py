"""LLaMA-Factory on-host package/runtime integrity, not fake training PASS."""
from __future__ import annotations
import base64
import hashlib
from pathlib import Path
import json
import subprocess
import sys
import pytest

from hazewave.llamafactory_runtime_probe import (
    LlamaRuntimeError, validate_probe, check_record_hashes, diagnose_runtime,
)

ROOT=Path(__file__).resolve().parents[1]
INSTALLER=ROOT/"scripts/codespaces/install-llamafactory-foss.sh"
WORKFLOW=ROOT/".github/workflows/llamafactory-harness-release.yml"


def test_installer_requires_executable_import_and_record_doctor():
    script=INSTALLER.read_text()
    assert "--runtime-doctor" in script
    assert "hazewave.llamafactory_runtime_probe" in script
    assert 'LLAMA_FACTORY_CLI_RUNTIME=NOT_PROVEN' in script
    assert 'LLAMA_FACTORY_TRAINING=NOT_PROVEN' in script
    assert "hazewave-zero-cost-4jxp45676rq6279xx" in script
    for forbidden in ("--model_name_or_path","gh codespace create","sudo ","codex mcp add","torchrun","hazewave-reflex serve-stop"):
        assert forbidden not in script
    assert subprocess.run(["bash","-n",str(INSTALLER)],capture_output=True).returncode == 0


def _row(path: str, content: bytes):
    digest=base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
    return (path,"sha256="+digest,str(len(content)))


def test_record_hash_audit_detects_post_install_tampering_and_unsafe_paths(tmp_path):
    root=tmp_path/"venv"
    file=root/"lib"/"python3.12"/"site-packages"/"llamafactory"/"cli.py"
    file.parent.mkdir(parents=True)
    file.write_bytes(b"print('known good')")
    row=_row("llamafactory/cli.py",file.read_bytes())
    assert check_record_hashes(root,[(file,row[1],row[2])]) == 1
    file.write_bytes(b"print('known evil')")
    with pytest.raises(LlamaRuntimeError,match="RECORD_HASH_MISMATCH"):
        check_record_hashes(root,[(file,row[1],row[2])])


def test_record_audit_blocks_symlink_and_out_of_environment(tmp_path):
    root=tmp_path/"venv"
    root.mkdir()
    external=tmp_path/"outside.py"
    external.write_text("pass")
    with pytest.raises(LlamaRuntimeError,match="INSTALLED_FILE_OUTSIDE_VENV"):
        check_record_hashes(root,[(external,_row("outside.py",external.read_bytes())[1],"4")])
    shortcut=root/"pkg.py"
    shortcut.symlink_to(external)
    with pytest.raises(LlamaRuntimeError,match="INSTALLED_FILE_SYMLINK"):
        check_record_hashes(root,[(shortcut,_row("pkg.py",external.read_bytes())[1],"4")])


def test_metadata_and_import_but_missing_deps_is_not_cli_or_training_ready():
    report=validate_probe({
        "distribution":"llamafactory","version":"0.9.5",
        "imported_version":"0.9.5", "hash_files_verified":81,\n        "release_files_verified":75, "release_wheel_sha256":"10776e9b259798bf65f6c5343f6298f0302e92e9cd47472abe29eef69e286c6a",
        "environment_isolated":True, "dependency_check_ok":False,
        "missing_dependencies_count":17,"cli_status":"NOT_ATTEMPTED_MISSING_DEPS",
        "python_version":"3.12.1",
    })
    assert report["package_imported"] is True
    assert report["installed_files_hash_verified"] is True\n    assert report["source_release_payload_verified"] is True
    assert report["dependencies_satisfied"] is False
    assert report["cli_runnable"] is False
    assert report["model_training_ready"] is False
    assert report["harness_connected"] is False
    assert report["production_approved"] is False


@pytest.mark.parametrize("value",[
    {"distribution":"llamafactory","version":"0.9.6","imported_version":"0.9.6","hash_files_verified":99,
     "environment_isolated":True,"dependency_check_ok":True,"missing_dependencies_count":0,"cli_status":"EXECUTED","python_version":"3.12.1"},
    {"distribution":"llamafactory","version":"0.9.5","imported_version":"0.9.5","hash_files_verified":0,
     "environment_isolated":True,"dependency_check_ok":False,"missing_dependencies_count":20,"cli_status":"NOT_ATTEMPTED_MISSING_DEPS","python_version":"3.12.1"},
    {"distribution":"llamafactory","version":"0.9.5","imported_version":"0.9.5","hash_files_verified":90,
     "environment_isolated":False,"dependency_check_ok":False,"missing_dependencies_count":20,"cli_status":"NOT_ATTEMPTED_MISSING_DEPS","python_version":"3.12.1"},
])
def test_invalid_package_version_records_or_isolation_refused(value):
    with pytest.raises(LlamaRuntimeError):
        validate_probe(value)


def test_live_import_has_no_unrestricted_python_eval_or_network_payload():
    import inspect
    import hazewave.llamafactory_runtime_probe as mod
    s=inspect.getsource(mod)
    assert "model_name_or_path" not in s
    assert "pip install" not in s
    assert "https://" not in s
    assert "HF_HUB_OFFLINE" in s
    assert "TRANSFORMERS_OFFLINE" in s
    assert "PYTHONNOUSERSITE" in s
    assert "subprocess.run" in s


def test_workflow_really_runs_package_probe_and_tamper_negative_control():
    source=WORKFLOW.read_text()
    assert "LLAMA_FACTORY_IMPORT_AND_RECORD_INTEGRITY=PASS" in source
    assert "LLAMA_FACTORY_TAMPERED_PACKAGE=REJECTED" in source
    assert "llamafactory_runtime_probe doctor" in source
    assert "LLAMA_FACTORY_CLI_RUNTIMEREADY=FALSE" in source


def test_mutable_record_cannot_attest_upstream_release_without_immutable_wheel():
    with pytest.raises(LlamaRuntimeError, match="OFFICIAL_WHEEL_REFERENCE_MISSING"):
        validate_probe({
            "distribution":"llamafactory","version":"0.9.5","imported_version":"0.9.5",
            "hash_files_verified":120, "environment_isolated":True,
            "dependency_check_ok":False, "missing_dependencies_count":30,
            "cli_status":"NOT_ATTEMPTED_MISSING_DEPS","python_version":"3.12.1"
        })


def test_official_wheel_zip_payload_validation_is_executed_on_host():
    from pathlib import Path
    s=(ROOT/"src/hazewave/llamafactory_runtime_probe.py").read_text()
    assert "zipfile.ZipFile" in s
    assert "release_files_verified" in s
    assert "OFFICIAL_WHEEL_SHA256" in s
    assert "dist.locate_file" in s
    assert "INSTALLED_FILE_TAMPERED" in s


def test_runtime_doctor_reuses_pinned_cached_official_wheel():
    script=INSTALLER.read_text()
    assert 'WHEEL_CACHE="$ENV_ROOT/release/$WHEEL"' in script
    assert 'sha256sum -c -' in script
    assert 'chmod 0400 "$WHEEL_CACHE"' in script
    assert '--wheel "$WHEEL_CACHE"' in script
