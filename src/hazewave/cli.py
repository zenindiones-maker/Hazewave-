from __future__ import annotations

import argparse

from hazewave.separation import DEFAULT_MODEL, SeparationError, separate_track


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hazewave",
        description="Hazewave neural audio processing tools.",
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
    return parser


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
    except SeparationError as exc:
        print(f"error={exc}")
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
