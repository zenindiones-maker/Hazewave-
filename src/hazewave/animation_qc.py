from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re
import struct
from typing import Final


PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
_FRAME_RE = re.compile(r"^frame-(\d+)\.png$")


class AnimationQCError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnimationFrameQC:
    frame_number: int
    path: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    bit_depth: int
    color_type: int
    alpha_channel_present: bool
    schema: str = "AnimationFrameQC/v1"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AnimationQCReport:
    frame_start: int
    frame_end: int
    frame_count: int
    width: int
    height: int
    bit_depth: int
    alpha_channel_present: bool
    frames: tuple[AnimationFrameQC, ...]
    missing_frames: tuple[int, ...]
    empty_frames: tuple[int, ...]
    sequence_sha256: str
    technical_status: str = "PASS"
    creative_verdict: str = "HUMAN_REVIEW_REQUIRED"
    schema: str = "AnimationQCReport/v1"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["frames"] = [item.to_dict() for item in self.frames]
        value["missing_frames"] = list(self.missing_frames)
        value["empty_frames"] = list(self.empty_frames)
        return value


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_png_header(path: Path) -> tuple[int, int, int, int, bool]:
    try:
        with path.open("rb") as handle:
            header = handle.read(33)
    except OSError as exc:
        raise AnimationQCError("ANIMATION_QC_FRAME_READ_FAILED") from exc

    if len(header) < 33 or header[:8] != PNG_SIGNATURE:
        raise AnimationQCError("ANIMATION_QC_PNG_INVALID")
    try:
        chunk_length = struct.unpack(">I", header[8:12])[0]
        chunk_type = header[12:16]
        width, height, bit_depth, color_type, compression, filtering, interlace = (
            struct.unpack(">IIBBBBB", header[16:29])
        )
    except struct.error as exc:
        raise AnimationQCError("ANIMATION_QC_PNG_INVALID") from exc

    if chunk_type != b"IHDR" or chunk_length != 13:
        raise AnimationQCError("ANIMATION_QC_PNG_INVALID")
    if width <= 0 or height <= 0 or bit_depth <= 0:
        raise AnimationQCError("ANIMATION_QC_PNG_INVALID")
    if compression != 0 or filtering != 0 or interlace not in {0, 1}:
        raise AnimationQCError("ANIMATION_QC_PNG_INVALID")
    if color_type not in {0, 2, 3, 4, 6}:
        raise AnimationQCError("ANIMATION_QC_PNG_INVALID")

    alpha = color_type in {4, 6}
    return width, height, bit_depth, color_type, alpha


def analyze_animation_sequence(
    root: Path | str,
    *,
    expected_frame_start: int,
    expected_frame_end: int,
) -> AnimationQCReport:
    directory = Path(root).expanduser().resolve()
    if not directory.is_dir():
        raise AnimationQCError("ANIMATION_QC_FRAME_ROOT_NOT_FOUND")
    if (
        not isinstance(expected_frame_start, int)
        or not isinstance(expected_frame_end, int)
        or expected_frame_start < 0
        or expected_frame_end < expected_frame_start
    ):
        raise AnimationQCError("ANIMATION_QC_EXPECTED_RANGE_INVALID")

    discovered: dict[int, Path] = {}
    unexpected_names: list[str] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = _FRAME_RE.fullmatch(path.name)
        if match is None:
            if path.suffix.lower() == ".png":
                unexpected_names.append(path.name)
            continue
        number = int(match.group(1))
        if number in discovered:
            raise AnimationQCError("ANIMATION_QC_DUPLICATE_FRAME_NUMBER")
        discovered[number] = path

    if unexpected_names:
        raise AnimationQCError("ANIMATION_QC_FRAME_NAME_INVALID")

    expected = tuple(range(expected_frame_start, expected_frame_end + 1))
    missing = tuple(number for number in expected if number not in discovered)
    if missing:
        raise AnimationQCError("ANIMATION_QC_FRAME_SEQUENCE_GAP")

    extras = tuple(sorted(number for number in discovered if number not in expected))
    if extras:
        raise AnimationQCError("ANIMATION_QC_UNEXPECTED_FRAMES")

    frames: list[AnimationFrameQC] = []
    empty: list[int] = []
    reference_dimensions: tuple[int, int] | None = None
    reference_bit_depth: int | None = None
    reference_alpha: bool | None = None

    for number in expected:
        path = discovered[number]
        size = path.stat().st_size
        if size <= 0:
            empty.append(number)
            continue

        width, height, bit_depth, color_type, alpha = _parse_png_header(path)
        dimensions = (width, height)
        if reference_dimensions is None:
            reference_dimensions = dimensions
        elif dimensions != reference_dimensions:
            raise AnimationQCError("ANIMATION_QC_RESOLUTION_DRIFT")

        if reference_bit_depth is None:
            reference_bit_depth = bit_depth
        elif bit_depth != reference_bit_depth:
            raise AnimationQCError("ANIMATION_QC_BIT_DEPTH_DRIFT")

        if reference_alpha is None:
            reference_alpha = alpha
        elif alpha != reference_alpha:
            raise AnimationQCError("ANIMATION_QC_ALPHA_MODE_DRIFT")

        frames.append(
            AnimationFrameQC(
                frame_number=number,
                path=str(path.resolve()),
                sha256=_sha256_file(path),
                size_bytes=size,
                width=width,
                height=height,
                bit_depth=bit_depth,
                color_type=color_type,
                alpha_channel_present=alpha,
            )
        )

    if empty:
        raise AnimationQCError("ANIMATION_QC_EMPTY_FRAME")
    if not frames or reference_dimensions is None or reference_bit_depth is None:
        raise AnimationQCError("ANIMATION_QC_FRAME_SEQUENCE_EMPTY")

    sequence_material = "\n".join(
        f"{item.frame_number}:{item.sha256}" for item in frames
    ).encode("utf-8")
    sequence_digest = sha256(sequence_material).hexdigest()

    return AnimationQCReport(
        frame_start=expected_frame_start,
        frame_end=expected_frame_end,
        frame_count=len(frames),
        width=reference_dimensions[0],
        height=reference_dimensions[1],
        bit_depth=reference_bit_depth,
        alpha_channel_present=bool(reference_alpha),
        frames=tuple(frames),
        missing_frames=(),
        empty_frames=(),
        sequence_sha256=sequence_digest,
    )
