from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = (
    ROOT / "scripts" / "install_hazewave_termux_runtime.sh",
    ROOT / "scripts" / "hazewave_termux_control.sh",
    ROOT / "scripts" / "hazewave_reflex_termux_control.sh",
    ROOT / "scripts" / "install_hazewave_always_ready_termux.sh",
    ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh",
    ROOT / "scripts" / "codespaces" / "start-always-ready.sh",
)


def test_termux_shell_scripts_have_valid_bash_syntax() -> None:
    for script in SCRIPTS:
        completed = subprocess.run(
            ["bash", "-n", str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"{script.name} failed bash -n\n"
            + completed.stdout
            + completed.stderr
        )


def test_termux_shell_scripts_do_not_embed_literal_newline_escape_between_commands() -> None:
    for script in SCRIPTS:
        text = script.read_text(encoding="utf-8")
        assert "\\ntest -f" not in text


def test_reflex_candidate_ref_propagates_from_termux_to_codespace_runtime() -> None:
    termux = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    assert 'DEFAULT_REF="work/hazewave-always-ready-v1"' in termux
    assert 'resolve_ref()' in termux
    assert 'REF="$(resolve_ref)"' in termux
    assert 'REF="${HAZEWAVE_REFLEX_REF:-work/hazewave-always-ready-v1}"' in remote
    assert "HAZEWAVE_REFLEX_REF='$REF'" in termux


def test_reflex_codespace_lifecycle_waits_through_shutdown_transition_before_restart() -> None:
    text = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")

    assert "codespace_metadata_row() {" in text
    assert "codespace_state_action() {" in text
    assert "ShuttingDown|Stopping" in text
    assert 'printf \'%s\\n\' "WAIT"' in text
    assert 'printf \'%s\\n\' "START"' in text
    assert 'printf \'%s\\n\' "READY"' in text
    assert 'action="$(codespace_state_action "$current_state")"' in text
    assert 'if [[ "$action" == "START" && "$start_requested" == "0" ]]; then' in text
    assert 'gh codespace view -c "$CS" --json state' not in text


def test_reflex_codespace_metadata_avoids_full_details_view_endpoint() -> None:
    text = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")

    assert 'gh codespace list --limit 100 --json name,state,repository' in text
    assert 'gh codespace view -c "$CS" --json name' not in text
    assert 'gh codespace view -c "$CS" --json repository' not in text


def test_reflex_termux_forwards_latency_scale_probe_to_remote_controller() -> None:
    text = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")

    assert "latency-scale-probe" in text
    remote_case = text.split('case "$action" in', 1)[1].split('esac', 1)[0]
    assert "latency-scale-probe" in remote_case


def test_reflex_engine_tuner_uses_semantic_stability_not_production_latency_eligibility() -> None:
    text = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")
    start = text.index("latency_engine_tune() {")
    end = text.index("latency_scale_probe() {", start)
    block = text[start:end]

    assert 'row.get("all_semantically_stable") is not True' in block
    assert 'row.get("all_robust_eligible") is not True' not in block


def test_reflex_termux_forwards_stale_latency_selection_retirement() -> None:
    termux = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    assert "latency-retire-stale-selection" in termux
    assert "latency-retire-stale-selection" in remote
    assert "retire-stale-selection" in remote


def test_reflex_engine_report_wakes_existing_codespace_before_reading_evidence() -> None:
    text = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")
    start = text.index("    latency-engine-report)")
    end = text.index("        ;;", start)
    block = text[start:end]

    assert "ensure_codespace_available" in block
    assert 'run_remote "$action"' in block


def test_reflex_laya_phase_profiler_is_diagnostic_only_and_exposed_through_termux() -> None:
    termux = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    assert "latency-engine-profile" in termux
    assert "latency-engine-profile" in remote
    assert "REFLEX_LAYA_PHASES" in remote
    assert '"diagnostic_only": True' in remote
    assert '"activatable": False' in remote
    assert "AGGREGATE_PROBABILITY_DRIFT" in remote
    assert '--engine-bin "$engine"' in remote
    assert 'run_profile_case instrumented "$profiler"' in remote


def test_reflex_termux_supports_persistent_ref_pin_without_weakening_env_override() -> None:
    text = (ROOT / "scripts" / "hazewave_reflex_termux_control.sh").read_text(encoding="utf-8")

    assert 'REF_PIN_FILE=' in text
    assert 'resolve_ref()' in text
    assert 'HAZEWAVE_REFLEX_REF' in text
    assert 'if [[ "$action" == "ref-pin" ]]; then' in text
    assert 'if [[ "$action" == "ref-clear" ]]; then' in text
    assert 'REFLEX_REF_SOURCE=PINNED_CONFIG' in text
    assert 'REFLEX_REF_SOURCE=ENVIRONMENT' in text
    assert 'chmod 600 "$REF_PIN_FILE"' in text


def test_reflex_laya_phase_profiler_breaks_encoder_hotspots_into_lossless_subphases() -> None:
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    assert 'local variant="phase_profile_v4"' in remote
    assert "REFLEX_LAYA_SUBPHASES" in remote
    for field in (
        "encoder_qkv_gemm_ms",
        "encoder_rope_ms",
        "encoder_attention_core_ms",
        "encoder_out_gemm_ms",
        "encoder_mlp_norm_ms",
        "encoder_wi_gemm_ms",
        "encoder_geglu_ms",
        "encoder_wo_gemm_ms",
        "encoder_residual_ms",
    ):
        assert field in remote
    assert "subphase_medians_ms" in remote
    assert "subphase_shares" in remote


def test_reflex_engine_tune_includes_exact_output_weight_panel_reuse_variant() -> None:
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    assert 'reuse_packed_w_v1' in remote
    assert 'build_pack_reuse_engine_variant' in remote
    assert 'qi_pack_w(panel, W, n0, nr, k0, kc);' in remote
    assert 'for (int nb = 0; nb < nblocks; nb++)' in remote
    assert 'for (int k0 = 0; k0 < K; k0 += QI_KC)' in remote
    assert 'for (int mb = 0; mb < mblocks; mb++)' in remote
    assert '"reuse_packed_w_v1"' in remote
    assert '"exact_aggregate_probability_match"' in remote


def test_reflex_laya_profiler_v3_separates_qi_gemm_pack_kernel_and_bias_costs() -> None:
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    assert 'local variant="phase_profile_v4"' in remote
    assert "REFLEX_QI_GEMM" in remote
    for field in (
        "pack_ms",
        "kernel_ms",
        "bias_ms",
        "total_ms",
        "gemm_internal_totals_ms",
        "gemm_internal_shares",
        "gemm_shapes",
        "dominant_gemm_shape",
    ):
        assert field in remote
    assert "AGGREGATE_PROBABILITY_DRIFT" in remote
    assert '"diagnostic_only": True' in remote
    assert '"activatable": False' in remote


def test_reflex_engine_ab_uses_explicit_engine_bin_contract_not_ambient_env() -> None:
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    assert '--engine-bin "$engine"' in remote
    assert 'COLI_ENGINE="$engine"' not in remote
    assert 'REFLEX_LATENCY_ENGINE_SHA256=' in (
        ROOT / "src" / "hazewave" / "reflex_latency.py"
    ).read_text(encoding="utf-8")


def test_reflex_qi_profiler_patch_is_scoped_to_phase_profile_builder_and_binary_verified() -> None:
    remote = (ROOT / "scripts" / "codespaces" / "reflex-shadow-control.sh").read_text(encoding="utf-8")

    pack_start = remote.index("build_pack_reuse_engine_variant() {")
    phase_start = remote.index("build_phase_profile_engine_variant() {")
    profile_start = remote.index("latency_engine_profile() {", phase_start)
    pack_block = remote[pack_start:phase_start]
    phase_block = remote[phase_start:profile_start]

    assert "REFLEX_QI_GEMM" not in pack_block
    assert 'local variant="phase_profile_v4"' in phase_block
    assert "REFLEX_QI_GEMM" in phase_block
    assert 'qi_path.write_text(qi_text, encoding="utf-8")' in phase_block
    assert 'grep -Fq "REFLEX_QI_GEMM" "$stage/c/qi_gemm.h"' in phase_block
    assert 'grep -aFq "REFLEX_QI_GEMM" "$stage/c/laya"' in phase_block
    assert 'strings "$stage/c/laya" | grep -Fq "REFLEX_QI_GEMM"' not in phase_block
