"""Adversarial host-client tests. Unit tests do NOT prove an owner agent session."""
from __future__ import annotations
from pathlib import Path
import subprocess

import pytest

from hazewave.wave_mcp_client_probe import (
    QualificationError, verify_advertised_tools, verify_observation_result,
)

ROOT=Path(__file__).resolve().parents[1]
SH=ROOT/"scripts/codespaces/wave-research-priority-gates.sh"
SHA="a"*40


def _catalog():
    return {"tools":[
        {"name":"harness_rea_owned_js","inputSchema":{
            "type":"object","properties":{"task_id":{"type":"string"}},
            "required":["task_id"],"additionalProperties":False}},
        {"name":"harness_iris_owned_page","inputSchema":{
            "type":"object","properties":{"task_id":{"type":"string"}},
            "required":["task_id"],"additionalProperties":False}},
    ]}


def test_admits_only_two_fixed_fixture_tools():
    result=verify_advertised_tools(_catalog())
    assert result==["harness_iris_owned_page","harness_rea_owned_js"]


@pytest.mark.parametrize("bad", [
    {"tools":[{"name":"harness_rea_owned_js","inputSchema":{"type":"object","additionalProperties":True}}]},
    {"tools":[{"name":"run_any_url","inputSchema":{"type":"object","additionalProperties":False}}]},
    {"tools":[]},
])
def test_denies_raw_mcp_and_insecure_catalog(bad):
    with pytest.raises(QualificationError):
        verify_advertised_tools(bad)


def _response():
    return {"isError":False,"content":[{"type":"text","text":__import__("json").dumps({
        "schema":"HazewaveHarnessExecutedResearchFixture/v1",
        "reviewed_repo_sha":SHA,
        "state":"OBSERVATION_ONLY",
        "harness_authority":"HAZEWAVE_HARNESS",
        "authorization_scope":"FIRST_PARTY_FIXTURE_BOOTSTRAP_ONLY",
        "host_identity_verified":False,
        "agent_mcp_session_connected":False,
        "capability_plane_measured_ready":False,
        "production_approved":False,
        "owner_signed_external_target":False,
        "provider_tool_sha256":"b"*64,
        "receipt_sha256":"c"*64,
        "kind":"rea_owned_js"
    })}]}


def test_result_is_scoped_observation_not_agent_connection():
    verified=verify_observation_result(_response(),kind="rea_owned_js",expected_sha=SHA)
    assert verified["host_identity_verified"] is False
    assert verified["agent_mcp_session_connected"] is False
    assert verified["production_approved"] is False


@pytest.mark.parametrize("change", [
    {"reviewed_repo_sha":"d"*40}, {"state":"PRODUCTION_READY"},
    {"production_approved":True}, {"agent_mcp_session_connected":True},
    {"host_identity_verified":True}, {"owner_signed_external_target":True},
    {"harness_authority":"SELF"}, {"kind":"iris_owned_page"},
])
def test_denies_forged_or_promoted_receipts(change):
    import json
    r=_response()
    item=json.loads(r["content"][0]["text"])
    item.update(change)
    r["content"][0]["text"]=json.dumps(item)
    with pytest.raises(QualificationError):
        verify_observation_result(r,kind="rea_owned_js",expected_sha=SHA)


def test_existing_codespace_only_gate_has_no_install_or_stock_mutation():
    script=SH.read_text()
    for expected in (
        "hazewave-zero-cost-4jxp45676rq6279xx",
        "work/wave-host-mcp-qualification-v1",
        "HAZEWAVE_RESEARCH_EXPECTED_SHA",
        "--is-inside-work-tree", "--inventory", "--prove", "--client-probe",
        "CODESPACES", "harness_research_execution",
        "wave_mcp_client_probe", "NO_EXTERNAL_TARGETS",
    ):
        assert expected in script
    for banned in (
        "gh codespace create","gh codespace rebuild","git reset --hard",
        "git checkout -f","git clean -fd","git push","git merge",
        "sudo ","npm install","pip install","--no-sandbox",
        "codex mcp add","iris mcp","hazewave-reflex serve-stop",
        "rm -rf","curl | sh",
    ):
        assert banned not in script
    result=subprocess.run(["bash","-n",str(SH)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_offhost_fails_before_side_effects():
    result=subprocess.run(["bash",str(SH),"--prove"],
        env={"HOME":"/tmp","PATH":"/usr/bin:/bin","CODESPACES":"false"},
        capture_output=True,text=True)
    assert result.returncode!=0
    assert "EXISTING_CODESPACE_REQUIRED" in result.stderr
