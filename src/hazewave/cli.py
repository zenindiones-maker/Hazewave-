from __future__ import annotations

import argparse
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
from hazewave.freellmapi import FreeLLMAPIError, run_live_probe
from hazewave.separation import DEFAULT_MODEL, SeparationError, separate_track


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

    probe = free_commands.add_parser(
        "probe",
        help="Run one bounded Harness-authorized live provider proof.",
    )
    probe.add_argument(
        "--key-file",
        default=str(
            Path.home()
            / ".config"
            / "hazewave"
            / "providers"
            / "freellmapi"
            / "unified-api-key"
        ),
    )
    probe.add_argument(
        "--task-id",
        default="hazewave-freellmapi-live-proof",
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

    except (SeparationError, AceStepError, FreeLLMAPIError) as exc:
        print(f"error={exc}")
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
