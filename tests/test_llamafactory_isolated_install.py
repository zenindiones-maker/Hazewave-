"""Test first: isolated, SHA-pinned LLaMA-Factory install with no fake training readiness."""
from pathlib import Path
import json
import subprocess
import sys
import pytest

from hazewave.llamafactory_install import (
    LlamaFactoryError, RELEASE_SHA256, RELEASE_VERSION,
    validate_installed_metadata, admitted_wheel_name, training_readiness,
)

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/codespaces/install-llamafactory-foss.sh"
MANIFEST = ROOT / "config/llamafactory-training-policy-v1.json"


def test_original_project_and_exact_hash_are_not_mirrors_or_latest():
    p=json.loads(MANIFEST.read_text())
    assert p["upstream"]["repository"]=="hiyouga/LlamaFactory"
    assert p["upstream"]["version"]=="0.9.5"
    assert p["upstream"]["tag_sha"]=="7af909522a951e3ad9f022ea6f88b6755257eaa5"
    assert p["upstream"]["wheel_sha256"]==RELEASE_SHA256
    assert p["upstream"]["license"]=="Apache-2.0"
    assert p["harness_authority"]=="HAZEWAVE_HARNESS"
    assert p["auto_training"] is False
    assert p["owner_media_allowed"] is False
    assert p["production_approved"] is False


def test_installer_is_guarded_existing_codespace_only():
    s=INSTALLER.read_text()
    assert 'hazewave-zero-cost-4jxp45676rq6279xx' in s
    assert '--preflight|--install|--doctor|--runtime-doctor|--training-preflight' in s
    assert 'HAZEWAVE_LLAMA_EXPECTED_SHA' in s
    assert 'git -C "$ROOT" status --porcelain' in s
    assert "VERSION_INSTALLED_METADATA_ONLY" in s
    assert "LLAMA_FACTORY_TRAINING=NOT_PROVEN" in s
    assert subprocess.run(["bash","-n",str(INSTALLER)],capture_output=True).returncode==0
    for forbidden in ("gh codespace create","sudo ","apt-get","git reset","git merge",
                      "git push","codex mcp add","hazewave-reflex serve-stop",
                      "--no-sandbox","curl | bash","torchrun","--model_name_or_path"):
        assert forbidden not in s


def test_installer_denies_wrong_host_before_writing_anything():
    p=subprocess.run(["bash",str(INSTALLER),"--preflight"],capture_output=True,text=True,
                     env={"CODESPACE_NAME":"wrong-host","HOME":"/tmp","PATH":"/usr/bin:/bin"})
    assert p.returncode != 0
    assert "WRONG_CODESPACE" in p.stderr


def test_wheel_name_must_match_official_pinned_distribution():
    assert admitted_wheel_name("llamafactory-0.9.5-py3-none-any.whl")
    for bad in ("llamafactory-0.9.6-py3-none-any.whl",
                "evil-0.9.5-py3-none-any.whl", "llamafactory-0.9.5.tar.gz"):
        assert not admitted_wheel_name(bad)


def test_metadata_doctor_requires_installed_package_and_proves_no_train():
    m={"name":"llamafactory","version":"0.9.5",
       "entry_points":["llamafactory-cli","lmf"], "license":"Apache-2.0"}
    proof=validate_installed_metadata(m)
    assert proof["package_installed"] is True
    assert proof["full_dependency_stack_verified"] is False
    assert proof["cli_runnable"] is False
    assert proof["training_runnable"] is False
    assert proof["models_downloaded"] is False
    assert proof["harness_agent_connected"] is False
    with pytest.raises(LlamaFactoryError):
        validate_installed_metadata({**m, "version":"0.9.6"})


def test_training_cpu_machine_fails_closed_and_no_automatic_gpu_install():
    state=training_readiness(cuda_available=False, vram_gib=0, ram_gib=8,
                             free_disk_gib=40, dependencies_ok=True)
    assert state["training_admitted"] is False
    assert state["reason"] == "GPU_UNAVAILABLE"
    state2=training_readiness(cuda_available=True,vram_gib=12,ram_gib=8,
                              free_disk_gib=40,dependencies_ok=True)
    assert state2["training_admitted"] is False
    assert state2["reason"]=="HOST_RAM_BELOW_16GIB"
    state3=training_readiness(cuda_available=True,vram_gib=24,ram_gib=32,
                              free_disk_gib=45,dependencies_ok=True)
    assert state3["training_admitted"] is False
    assert state3["reason"]=="OWNER_MODEL_AND_DATASET_GRANT_MISSING"


def test_harness_inventory_surfaces_learning_tool_without_claiming_ready():
    from hazewave.harness_connection_inventory import inventory_all_capabilities
    x=inventory_all_capabilities()
    item=x["learning_candidates"]["llamafactory"]
    assert item["framework_version"]=="0.9.5"
    assert item["installation_status"]=="NOT_VERIFIED_ON_CODESPACE"
    assert item["training_status"]=="NOT_PROVEN"
    assert item["harness_selected_provider"] is False
    assert item["agent_mcp_connected"] is False
    assert item["owner_signed_model_dataset_grant"] is False
    assert x["summary"]["provider_mapped"]==10
    assert x["summary"]["ready_on_existing_codespace"]==0
