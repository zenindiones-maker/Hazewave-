from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import json

from hazewave.acestep import (
    ACESTEP_DEFAULT_MODEL_REPO,
    DEFAULT_API_URL,
    DEFAULT_RUNTIME_DIR,
    AceStepClient,
    AceStepError,
    install_runtime,
    serve_runtime,
)
from hazewave.freellmapi import (
    DEFAULT_BASE_URL,
    FreeLLMAPIClient,
    FreeLLMAPIError,
    FreeLLMAPILocalCatalog,
    build_free_fabric_eligibility_report,
    build_free_fabric_inventory,
    run_live_probe,
)
from hazewave.harness import HazewaveTask, issue_authorization, route_task
from hazewave.ninerouter import (
    NineRouterExecutionError,
    build_9router_efficiency_status,
    execute_9router_messages,
    execute_9router_text,
)
from hazewave.provider_policy import (
    DEFAULT_ACCOUNT_ATTESTATION_PATH,
    load_account_attestations,
    load_provider_registry,
    write_account_attestation,
)
from hazewave.separation import DEFAULT_MODEL, SeparationError, separate_track
from hazewave.reverse_engineering import (
    ReverseEngineeringError,
    load_default_foundation,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hazewave",
        description="Hazewave generative music and neural audio tools.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    separate = subcommands.add_parser(
        "separate",
        help="Separate an audio track into vocals and instrumental stems.",
    )
    separate.add_argument("input", help="Path to an audio file.")
    separate.add_argument(
        "--output-dir",
        default="output",
        help="Destination directory. Default: output",
    )
    separate.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Demucs model name. Default: {DEFAULT_MODEL}",
    )
    separate.add_argument(
        "--instrumental-only",
        action="store_true",
        help="Export only the no-vocals instrumental stem.",
    )
    separate.add_argument(
        "--format",
        choices=("wav", "mp3"),
        default="wav",
        dest="output_format",
        help="Output format. WAV is lossless; MP3 is encoded at 320 kbps.",
    )

    free = subcommands.add_parser(
        "freellmapi",
        help="Use the Hazewave-scoped FreeLLMAPI provider gateway.",
    )
    free_commands = free.add_subparsers(dest="freellmapi_command", required=True)

    default_key_file = str(
        Path.home()
        / ".config"
        / "hazewave"
        / "providers"
        / "freellmapi"
        / "unified-api-key"
    )

    inventory = free_commands.add_parser(
        "inventory",
        help="Report the local FreeLLMAPI surface without exposing credentials.",
    )

    eligible = free_commands.add_parser(
        "eligible",
        help="Show the currently eligible zero-cost Hazewave provider surface.",
    )
    eligible.add_argument(
        "--data-classification",
        choices=("PUBLIC", "INTERNAL_NON_SECRET", "PRIVATE_MEDIA", "CREDENTIAL"),
        default="PUBLIC",
    )

    health = free_commands.add_parser(
        "health",
        help="Check the local FreeLLMAPI HTTP health boundary.",
    )
    health.add_argument("--key-file", default=default_key_file)

    quota = free_commands.add_parser(
        "quota",
        help="Read FreeLLMAPI usage/quota observability through read-only MCP.",
    )
    quota.add_argument("--key-file", default=default_key_file)
    quota.add_argument("--range", choices=("24h", "7d", "30d"), default="24h")

    probe = free_commands.add_parser(
        "probe",
        help="Run one bounded Harness-authorized live provider proof.",
    )
    probe.add_argument("--key-file", default=default_key_file)
    probe.add_argument(
        "--task-id",
        default="hazewave-freellmapi-live-proof",
    )

    probe_all = free_commands.add_parser(
        "probe-all",
        help=(
            "Run one live zero-cost text proof and report the remaining eligible "
            "surfaces without spending their quotas."
        ),
    )
    probe_all.add_argument("--key-file", default=default_key_file)
    probe_all.add_argument(
        "--task-id",
        default="hazewave-freellmapi-bounded-surface-proof",
    )

    attest = free_commands.add_parser(
        "attest",
        help="Inspect or create account-bound zero-cost attestations.",
    )
    attest_commands = attest.add_subparsers(dest="attest_command", required=True)

    attest_status = attest_commands.add_parser(
        "status",
        help="Show secret-free provider key and attestation status.",
    )
    attest_status.add_argument(
        "--file",
        default=str(DEFAULT_ACCOUNT_ATTESTATION_PATH),
        help="Local attestation store. Default: project-scoped config path.",
    )

    attest_write = attest_commands.add_parser(
        "write",
        help=(
            "Persist a human-verified Free-tier attestation for one FreeLLMAPI "
            "provider key id."
        ),
    )
    attest_write.add_argument("--provider", required=True)
    attest_write.add_argument("--credential-id", type=int, required=True)
    attest_write.add_argument("--expires-at", required=True)
    attest_write.add_argument(
        "--source-evidence",
        action="append",
        required=True,
        help="Evidence URL or reference; repeat for multiple sources.",
    )
    attest_write.add_argument(
        "--confirm-free-tier",
        action="store_true",
        help="Confirm that this exact provider account/key is on the Free tier.",
    )
    attest_write.add_argument(
        "--confirm-no-paid-billing",
        action="store_true",
        help=(
            "Confirm that this exact account/key cannot overflow into paid "
            "billing without an explicit account upgrade."
        ),
    )
    attest_write.add_argument(
        "--file",
        default=str(DEFAULT_ACCOUNT_ATTESTATION_PATH),
        help="Local attestation store. Default: project-scoped config path.",
    )

    ninerouter = subcommands.add_parser(
        "9router",
        help="Execute receipt-bound zero-cost text tasks through the local 9Router sidecar.",
    )
    ninerouter_commands = ninerouter.add_subparsers(
        dest="ninerouter_command",
        required=True,
    )

    ninerouter_status = ninerouter_commands.add_parser(
        "status",
        help="Report the current receipt-ranked 9Router efficiency posture.",
    )

    ninerouter_execute = ninerouter_commands.add_parser(
        "execute",
        help="Execute one Harness-authorized PUBLIC text task on an admitted 9Router model.",
    )
    ninerouter_input = ninerouter_execute.add_mutually_exclusive_group(
        required=True
    )
    ninerouter_input.add_argument("--prompt")
    ninerouter_input.add_argument(
        "--messages-file",
        help=(
            "JSON array of PUBLIC text-only chat/tool-history messages. "
            "Tool results remain subject to the governed RTK boundary."
        ),
    )
    ninerouter_execute.add_argument(
        "--model",
        default="auto",
        help="Exact admitted model or auto for optimized receipt-ranked selection.",
    )
    ninerouter_execute.add_argument(
        "--capability",
        choices=("reason.general", "reason.deep", "code.generate", "code.review"),
        default="reason.general",
    )
    ninerouter_execute.add_argument(
        "--domain",
        choices=("HAZE", "WAVE", "BRIDGE"),
        default="HAZE",
    )
    ninerouter_execute.add_argument(
        "--data-classification",
        choices=("PUBLIC",),
        default="PUBLIC",
    )
    ninerouter_execute.add_argument(
        "--task-id",
        default="hazewave-9router-cli",
    )
    ninerouter_execute.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
    )
    ninerouter_execute.add_argument(
        "--max-fallbacks",
        type=int,
        default=3,
        help="Maximum admitted Free models attempted by auto selection.",
    )

    reverse_engineering = subcommands.add_parser(
        "reverse-engineering",
        help="Plan governed reverse-engineering research for HAZE, WAVE, or BRIDGE.",
    )
    re_commands = reverse_engineering.add_subparsers(
        dest="reverse_engineering_command",
        required=True,
    )
    re_plan = re_commands.add_parser(
        "plan",
        help="Create an evidence-first investigation plan for an authorized target.",
    )
    re_plan.add_argument("--domain", choices=("HAZE", "WAVE", "BRIDGE"), required=True)
    re_plan.add_argument(
        "--target-kind",
        choices=(
            "audio_plugin",
            "audio_codec",
            "audio_application",
            "visual_shader",
            "visual_application",
            "web_visual",
            "av_pipeline",
        ),
        required=True,
    )
    re_plan.add_argument(
        "--purpose",
        choices=(
            "AUTHORIZED_FEATURE_STUDY",
            "COMPATIBILITY_RESEARCH",
            "INTEROPERABILITY",
            "PERFORMANCE_STUDY",
            "FORMAT_ANALYSIS",
            "QUALITY_BENCHMARK",
        ),
        required=True,
    )
    re_plan.add_argument(
        "--authorized",
        action="store_true",
        help="Confirm that the target is owned, open-source, or otherwise authorized for analysis.",
    )
    re_commands.add_parser(
        "registry",
        help="Show the pinned reverse-engineering capability registry.",
    )

    ace = subcommands.add_parser(
        "acestep",
        help="Manage and use the local ACE-Step 1.5 music engine.",
    )
    ace_commands = ace.add_subparsers(dest="ace_command", required=True)

    install = ace_commands.add_parser(
        "install",
        help="Download the pinned ACE-Step runtime and resolve dependencies.",
    )
    install.add_argument(
        "--runtime-dir",
        default=str(DEFAULT_RUNTIME_DIR),
        help=f"Managed runtime directory. Default: {DEFAULT_RUNTIME_DIR}",
    )
    install.add_argument(
        "--prefetch-models",
        action="store_true",
        help="Also download the official ACE-Step 1.5 model snapshot into the HF cache.",
    )
    install.add_argument(
        "--model-repo",
        default=ACESTEP_DEFAULT_MODEL_REPO,
        help=f"Hugging Face model repository. Default: {ACESTEP_DEFAULT_MODEL_REPO}",
    )

    serve = ace_commands.add_parser(
        "serve",
        help="Start the official ACE-Step REST API in the foreground.",
    )
    serve.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME_DIR))
    serve.add_argument("--model", default=None, help="Optional ACE-Step DiT model.")
    serve.add_argument("--api-key", default=None, help="Optional local API key.")

    status = ace_commands.add_parser(
        "status",
        help="Check whether the local ACE-Step API is healthy.",
    )
    status.add_argument("--server", default=DEFAULT_API_URL)
    status.add_argument("--api-key", default=None)

    generate = ace_commands.add_parser(
        "generate",
        help="Generate an instrumental from prompt plus optional reference/source audio.",
    )
    generate.add_argument(
        "audio",
        nargs="?",
        help="Reference/source audio. Required for reference and cover modes.",
    )
    generate.add_argument("--prompt", required=True, help="Desired instrumental description.")
    generate.add_argument(
        "--mode",
        choices=("text", "reference", "cover"),
        default="reference",
        help="text=new composition; reference=style-guided; cover=retain source structure.",
    )
    generate.add_argument(
        "--cover-strength",
        type=float,
        default=0.8,
        help="Source influence for cover mode, from 0.0 to 1.0.",
    )
    generate.add_argument("--duration", type=float, default=None)
    generate.add_argument("--bpm", type=int, default=None)
    generate.add_argument("--key-scale", default=None)
    generate.add_argument("--time-signature", default=None)
    generate.add_argument(
        "--format",
        choices=("wav", "wav32", "flac", "mp3", "opus", "aac"),
        default="wav",
        dest="audio_format",
    )
    generate.add_argument("--model", default=None)
    generate.add_argument("--server", default=DEFAULT_API_URL)
    generate.add_argument("--api-key", default=None)
    generate.add_argument(
        "--no-thinking",
        action="store_true",
        help="Disable the 5Hz LM for text/reference generation.",
    )
    generate.add_argument(
        "--timeout",
        type=float,
        default=1800.0,
        help="Maximum task wait in seconds. Default: 1800.",
    )
    generate.add_argument(
        "--output",
        default=None,
        help="Output audio path. Defaults to output/acestep/<source-or-generated>.<format>.",
    )
    return parser


def _default_acestep_output(audio: str | None, audio_format: str, mode: str) -> Path:
    stem = Path(audio).stem if audio else "generated"
    suffix = "wav" if audio_format == "wav32" else audio_format
    return Path("output") / "acestep" / f"{stem}_{mode}.{suffix}"


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.command == "reverse-engineering":
            policy_path = (
                Path(__file__).resolve().parents[2]
                / "config"
                / "reverse-engineering-foundation-v1.json"
            )
            foundation = load_default_foundation(policy_path)
            if args.reverse_engineering_command == "registry":
                print(
                    json.dumps(
                        foundation.snapshot(),
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                )
                return 0
            if args.reverse_engineering_command == "plan":
                plan = foundation.plan(
                    domain=args.domain,
                    target_kind=args.target_kind,
                    authorized=args.authorized,
                    purpose=args.purpose,
                )
                print(json.dumps(plan, sort_keys=True, ensure_ascii=False))
                return 0

        if args.command == "separate":
            result = separate_track(
                args.input,
                output_dir=args.output_dir,
                model=args.model,
                instrumental_only=args.instrumental_only,
                output_format=args.output_format,
            )
            print(f"model={result.model}")
            print(f"instrumental={result.instrumental}")
            if result.vocals is not None:
                print(f"vocals={result.vocals}")
            return 0

        if args.command == "9router" and args.ninerouter_command == "status":
            print(
                json.dumps(
                    build_9router_efficiency_status(),
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command == "9router" and args.ninerouter_command == "execute":
            messages = None
            if args.messages_file:
                messages_path = Path(args.messages_file).expanduser()
                if not messages_path.is_file():
                    raise ValueError("NINEROUTER_MESSAGES_FILE_MISSING")
                try:
                    messages = json.loads(
                        messages_path.read_text(encoding="utf-8")
                    )
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "NINEROUTER_MESSAGES_FILE_INVALID_JSON"
                    ) from exc
                if not isinstance(messages, list):
                    raise ValueError(
                        "NINEROUTER_MESSAGES_FILE_MUST_BE_ARRAY"
                    )

            goal = (
                args.prompt
                if args.prompt is not None
                else "Execute governed PUBLIC tool-history through 9Router"
            )
            task = HazewaveTask(
                task_id=args.task_id,
                goal=goal,
                required_capability=args.capability,
                requested_domain=args.domain,
            )
            authorization = issue_authorization(route_task(task))

            if messages is not None:
                result = execute_9router_messages(
                    authorization=authorization,
                    model_id=args.model,
                    messages=messages,
                    data_classification=args.data_classification,
                    max_tokens=args.max_tokens,
                    max_fallbacks=args.max_fallbacks,
                )
            else:
                result = execute_9router_text(
                    authorization=authorization,
                    model_id=args.model,
                    prompt=args.prompt,
                    data_classification=args.data_classification,
                    max_tokens=args.max_tokens,
                    max_fallbacks=args.max_fallbacks,
                )

            print("HAZEWAVE_9ROUTER_EXECUTION=PASS")
            print(
                json.dumps(
                    asdict(result),
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command == "acestep" and args.ace_command == "install":
            result = install_runtime(
                args.runtime_dir,
                prefetch_models=args.prefetch_models,
                model_repo=args.model_repo,
            )
            print(f"runtime={result.runtime_dir}")
            print(f"upstream_ref={result.upstream_ref}")
            print(f"models_prefetched={str(result.models_prefetched).lower()}")
            return 0

        if args.command == "acestep" and args.ace_command == "serve":
            return serve_runtime(
                args.runtime_dir,
                model=args.model,
                api_key=args.api_key,
            )

        if args.command == "acestep" and args.ace_command == "status":
            with AceStepClient(args.server, api_key=args.api_key) as client:
                healthy = client.health()
            print(f"acestep_api={'healthy' if healthy else 'unhealthy'}")
            return 0 if healthy else 3

        if args.command == "acestep" and args.ace_command == "generate":
            output = (
                Path(args.output)
                if args.output
                else _default_acestep_output(args.audio, args.audio_format, args.mode)
            )
            with AceStepClient(args.server, api_key=args.api_key) as client:
                result = client.generate_instrumental(
                    args.prompt,
                    destination=output,
                    audio_path=args.audio,
                    mode=args.mode,
                    cover_strength=args.cover_strength,
                    duration=args.duration,
                    bpm=args.bpm,
                    key_scale=args.key_scale,
                    time_signature=args.time_signature,
                    audio_format=args.audio_format,
                    model=args.model,
                    thinking=not args.no_thinking,
                    timeout_seconds=args.timeout,
                )
            print(f"task_id={result.task_id}")
            print(f"mode={result.mode}")
            print(f"output={result.output_path}")
            return 0

        if args.command == "freellmapi" and args.freellmapi_command == "attest":
            store_path = Path(args.file).expanduser()
            if args.attest_command == "status":
                store = load_account_attestations(store_path)
                registry = load_provider_registry()
                account_bound = {
                    str(row.get("provider") or "").casefold()
                    for row in (registry.get("providers") or [])
                    if row.get("enabled") is True
                    and row.get("monetary_policy")
                    == "ZERO_COST_REQUIRES_ACCOUNT_HARD_CAP"
                    and row.get("billing_overflow_policy")
                    == "ACCOUNT_ATTESTATION_REQUIRED"
                }
                attestations = {
                    (
                        str(row.get("provider") or "").casefold(),
                        int(row.get("credential_id") or 0),
                    ): dict(row)
                    for row in (store.get("attestations") or [])
                    if isinstance(row, dict)
                }
                keys = [
                    row
                    for row in FreeLLMAPILocalCatalog().provider_keys()
                    if str(row.get("provider") or "").casefold() in account_bound
                ]
                status_rows = []
                for key in keys:
                    identity = (
                        str(key["provider"]).casefold(),
                        int(key["credential_id"]),
                    )
                    attestation = attestations.get(identity)
                    status_rows.append(
                        {
                            **key,
                            "attested": attestation is not None,
                            "attestation_id": (
                                attestation.get("attestation_id")
                                if attestation is not None
                                else None
                            ),
                            "expires_at": (
                                attestation.get("expires_at")
                                if attestation is not None
                                else None
                            ),
                        }
                    )
                print(
                    json.dumps(
                        {
                            "schema": "HazewaveProviderAccountAttestationStatus/v1",
                            "project_id": "HAZEWAVE",
                            "authority": "HAZEWAVE_HARNESS",
                            "store": str(store_path),
                            "keys": status_rows,
                        },
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                )
                return 0

            if args.attest_command == "write":
                if not args.confirm_free_tier or not args.confirm_no_paid_billing:
                    raise FreeLLMAPIError(
                        "FREELLMAPI_ACCOUNT_ATTESTATION_CONFIRMATIONS_REQUIRED"
                    )
                provider = str(args.provider).strip().casefold()
                credential_id = int(args.credential_id)
                keys = FreeLLMAPILocalCatalog().provider_keys()
                if not any(
                    str(row.get("provider") or "").casefold() == provider
                    and int(row.get("credential_id") or 0) == credential_id
                    for row in keys
                ):
                    raise FreeLLMAPIError(
                        "FREELLMAPI_ACCOUNT_ATTESTATION_KEY_NOT_FOUND"
                    )
                record = write_account_attestation(
                    provider=provider,
                    credential_id=credential_id,
                    expires_at=args.expires_at,
                    source_evidence=list(args.source_evidence),
                    path=store_path,
                )
                print("HAZEWAVE_FREELLMAPI_ACCOUNT_ATTESTATION=WRITTEN")
                print(json.dumps(record, sort_keys=True, ensure_ascii=False))
                return 0

        if args.command == "freellmapi" and args.freellmapi_command == "inventory":
            print(
                json.dumps(
                    build_free_fabric_inventory(),
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command == "freellmapi" and args.freellmapi_command == "eligible":
            print(
                json.dumps(
                    build_free_fabric_eligibility_report(
                        data_classification=args.data_classification
                    ),
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command == "freellmapi" and args.freellmapi_command == "health":
            key_path = Path(args.key_file).expanduser()
            if not key_path.is_file():
                raise FreeLLMAPIError("FREELLMAPI_UNIFIED_API_KEY_FILE_MISSING")
            with FreeLLMAPIClient(
                DEFAULT_BASE_URL,
                api_key=key_path.read_text(encoding="utf-8").strip(),
            ) as client:
                healthy = client.health()
            print(f"HAZEWAVE_FREELLMAPI_HEALTH={'PASS' if healthy else 'FAIL'}")
            return 0 if healthy else 3

        if args.command == "freellmapi" and args.freellmapi_command == "quota":
            key_path = Path(args.key_file).expanduser()
            if not key_path.is_file():
                raise FreeLLMAPIError("FREELLMAPI_UNIFIED_API_KEY_FILE_MISSING")
            with FreeLLMAPIClient(
                DEFAULT_BASE_URL,
                api_key=key_path.read_text(encoding="utf-8").strip(),
            ) as client:
                result = client.mcp_readonly(
                    "usage_summary",
                    {"range": args.range},
                )
            print(json.dumps(result, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "freellmapi" and args.freellmapi_command == "probe-all":
            key_path = Path(args.key_file).expanduser()
            if not key_path.is_file():
                raise FreeLLMAPIError("FREELLMAPI_UNIFIED_API_KEY_FILE_MISSING")
            receipt = run_live_probe(
                api_key=key_path.read_text(encoding="utf-8").strip(),
                task_id=args.task_id,
            )
            report = {
                "schema": "HazewaveBoundedSurfaceProbe/v1",
                "status": "PASS",
                "live_text_probe": receipt,
                "eligible_surface": build_free_fabric_eligibility_report(
                    data_classification="PUBLIC"
                ),
                "quota_policy": (
                    "Only the text route is exercised live; other eligible surfaces "
                    "are reported without consuming finite free quotas."
                ),
            }
            print("HAZEWAVE_FREELLMAPI_BOUNDED_PROBE_ALL=PASS")
            print(json.dumps(report, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "freellmapi" and args.freellmapi_command == "probe":
            key_path = Path(args.key_file).expanduser()
            if not key_path.is_file():
                raise FreeLLMAPIError("FREELLMAPI_UNIFIED_API_KEY_FILE_MISSING")
            receipt = run_live_probe(
                api_key=key_path.read_text(encoding="utf-8").strip(),
                task_id=args.task_id,
            )
            print("HAZEWAVE_FREELLMAPI_LIVE_PROBE=PASS")
            print(json.dumps(receipt, sort_keys=True, ensure_ascii=False))
            return 0

    except (
        SeparationError,
        AceStepError,
        FreeLLMAPIError,
        NineRouterExecutionError,
        ReverseEngineeringError,
        PermissionError,
        ValueError,
    ) as exc:
        print(f"error={exc}")
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
