from __future__ import annotations

import argparse
from pathlib import Path

from hazewave.acestep import (
    ACESTEP_DEFAULT_MODEL_REPO,
    DEFAULT_API_URL,
    DEFAULT_RUNTIME_DIR,
    AceStepClient,
    AceStepError,
    install_runtime,
    serve_runtime,
)
from hazewave.separation import DEFAULT_MODEL, SeparationError, separate_track
from hazewave.wan2gp import (
    DEFAULT_RUNTIME_DIR as WAN2GP_RUNTIME_DIR,
    DEFAULT_SERVER_PORT,
    Wan2GPError,
    install_runtime as install_wan2gp,
    process_queue,
    runtime_status,
    serve_runtime as serve_wan2gp,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hazewave",
        description="Hazewave generative music, neural audio, and local Wan2GP video.",
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

    wan = subcommands.add_parser(
        "wan2gp",
        help="Install and run the pinned deepbeepmeep/Wan2GP video studio.",
    )
    wan_commands = wan.add_subparsers(dest="wan_command", required=True)

    wan_install = wan_commands.add_parser(
        "install",
        help="Clone the pinned Wan2GP repository and install its dependencies.",
    )
    wan_install.add_argument(
        "--runtime-dir",
        default=str(WAN2GP_RUNTIME_DIR),
        help=f"Managed runtime directory. Default: {WAN2GP_RUNTIME_DIR}",
    )
    wan_install.add_argument(
        "--gpu",
        choices=("rtx", "gtx10"),
        default="rtx",
        help="Upstream torch install. rtx = RTX 20xx-50xx (cu130). gtx10 = GTX 10xx (cu128).",
    )
    wan_install.add_argument(
        "--skip-deps",
        action="store_true",
        help="Clone and pin the repository without installing torch or requirements.txt.",
    )

    wan_serve = wan_commands.add_parser(
        "serve",
        help="Start the official Wan2GP web UI (python wgp.py).",
    )
    wan_serve.add_argument("--runtime-dir", default=str(WAN2GP_RUNTIME_DIR))
    wan_serve.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT)
    wan_serve.add_argument(
        "--listen",
        action="store_true",
        help="Bind on the local network (wgp.py --listen).",
    )
    wan_serve.add_argument("--share", action="store_true", help="Create a Gradio share URL.")
    wan_serve.add_argument("--open-browser", action="store_true")
    wan_serve.add_argument(
        "--memory-profile",
        default=None,
        help="Wan2GP VRAM profile number passed as wgp.py --profile.",
    )
    wan_serve.add_argument(
        "--attention",
        default=None,
        help="Attention mode passed as wgp.py --attention, for example sdpa.",
    )

    wan_process = wan_commands.add_parser(
        "process",
        help="Run a saved queue (.zip) or settings (.json) overnight, without the web UI.",
    )
    wan_process.add_argument("queue", help="Path to a Wan2GP queue.zip or settings.json.")
    wan_process.add_argument("--runtime-dir", default=str(WAN2GP_RUNTIME_DIR))
    wan_process.add_argument(
        "--output-dir",
        default="output/wan2gp",
        help="Directory for rendered videos. Default: output/wan2gp",
    )
    wan_process.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the queue and exit without generating.",
    )

    wan_status = wan_commands.add_parser(
        "status",
        help="Show whether the pinned Wan2GP checkout is installed.",
    )
    wan_status.add_argument("--runtime-dir", default=str(WAN2GP_RUNTIME_DIR))
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

        if args.command == "wan2gp" and args.wan_command == "install":
            result = install_wan2gp(
                args.runtime_dir,
                gpu_profile=args.gpu,
                install_deps=not args.skip_deps,
            )
            print(f"runtime={result.runtime_dir}")
            print(f"upstream_ref={result.upstream_ref}")
            print(f"gpu_profile={result.gpu_profile}")
            print(f"dependencies_installed={str(result.dependencies_installed).lower()}")
            return 0

        if args.command == "wan2gp" and args.wan_command == "serve":
            return serve_wan2gp(
                args.runtime_dir,
                port=args.port,
                listen=args.listen,
                share=args.share,
                open_browser=args.open_browser,
                memory_profile=args.memory_profile,
                attention=args.attention,
            )

        if args.command == "wan2gp" and args.wan_command == "process":
            return process_queue(
                args.queue,
                args.runtime_dir,
                output_dir=args.output_dir,
                dry_run=args.dry_run,
            )

        if args.command == "wan2gp" and args.wan_command == "status":
            status = runtime_status(args.runtime_dir)
            print(f"runtime={status.runtime_dir}")
            print(f"installed={str(status.installed).lower()}")
            print(f"upstream_ref={status.upstream_ref or ''}")
            print(f"expected_ref={status.expected_ref}")
            print(f"dependencies_installed={str(status.dependencies_installed).lower()}")
            pinned = status.installed and status.upstream_ref == status.expected_ref
            return 0 if pinned else 3

    except (SeparationError, AceStepError, Wan2GPError) as exc:
        print(f"error={exc}")
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
