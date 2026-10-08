"""Synthetic REA/HAZE/WAVE Evidence -> LLaMA-Factory Alpaca format.

This is a schema-compatibility DEMO, not an authorized training dataset.
Raw external/owner media is explicitly excluded. Receipts are locally
revalidated but they are NOT independent owner-signed attestations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any


class LearningBridgeError(RuntimeError):
    pass


def _load_private_receipt(path: Path) -> tuple[dict[str, Any], str]:
    p = Path(path)
    try:
        info = p.lstat()
        if (not stat.S_ISREG(info.st_mode) or p.is_symlink()
                or info.st_mode & 0o077 or info.st_size > 128 * 1024):
            raise LearningBridgeError("RECEIPT_NOT_PRIVATE")
        payload = p.read_bytes()
        record = json.loads(payload)
    except (OSError, ValueError) as exc:
        raise LearningBridgeError("RECEIPT_INVALID") from exc
    if not isinstance(record, dict):
        raise LearningBridgeError("RECEIPT_INVALID")
    return record, hashlib.sha256(payload).hexdigest()


def _write_private(path: Path, data: Any) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def export_synthetic_examples(
    *, native_receipt: Path, av_receipt: Path, output_root: Path,
) -> dict[str, Any]:
    native, native_hash = _load_private_receipt(native_receipt)
    av, av_hash = _load_private_receipt(av_receipt)
    if (
        native.get("schema") != "HazewaveOwnedAutomaticNativeSynthesis/v1"
        or av.get("schema") != "HazewaveSyntheticAudioVideoFidelity/v1"
        or native.get("harness_authority") != "HAZEWAVE_HARNESS"
        or av.get("harness_authority") != "HAZEWAVE_HARNESS"
        or av.get("source") != "OWNED_SYNTHETIC_MEDIA"
        or av.get("owner_media_analyzed") is not False
        or native.get("production_approved") is not False
        or av.get("production_approved") is not False
    ):
        raise LearningBridgeError("SYNTHETIC_ONLY_SOURCE_REQUIRED")
    if (
        native.get("behavioral_status") != "EXHAUSTIVE_WITHIN_EXPLICIT_FINITE_DOMAIN"
        or native.get("domain") != [-1000, 1000]
        or native.get("inputs_checked") != 2001
        or native.get("automatic_candidate_generation") is not True
        or native.get("original_C_used_for_synthesis") is not False
        or native.get("outside_domain_equivalence_proven") is not False
        or av.get("actual_ffmpeg_executed") is not True
        or not isinstance(av.get("audio_attenuation_detected_db"), (int, float))
        or not 10 <= av["audio_attenuation_detected_db"] <= 14
        or not isinstance(av.get("identical_video_ssim"), (int, float))
        or not isinstance(av.get("altered_video_ssim"), (int, float))
        or av["identical_video_ssim"] < 0.999
        or not 0 <= av["altered_video_ssim"] < 0.99
    ):
        raise LearningBridgeError("UNVERIFIED_SYNTHETIC_OBSERVATION")
    samples = [
        {
            "instruction": "Qual limite científico deve acompanhar uma reconstrução obtida por execução de um binário em domínio finito?",
            "input": "A hipótese gerada automaticamente correspondeu às 2001 entradas inteiras de -1000 a 1000.",
            "output": "Equivalência exaustiva apenas nesse domínio finito. Não demonstra equivalência universal, código-fonte original ou reconstrução automática de qualquer aplicação.",
        },
        {
            "instruction": "Como interpretar uma mudança real de nível RMS/volume detectada pelo FFmpeg em um sinal sintético?",
            "input": "O controle de atenuação conhecido foi de aproximadamente 12 dB no volume médio.",
            "output": "O pipeline detectou a atenuação do controle sintético. Isso não prova qualidade de mixagem, fidelidade perceptual ou aprovação de material real.",
        },
        {
            "instruction": "Como diferenciar prova de SSIM de julgamento artístico de vídeo?",
            "input": "SSIM do vídeo sintético idêntico foi próximo de 1 e o vídeo alterado ficou abaixo de 0,99.",
            "output": "A métrica discriminou controles sintéticos positivos e negativos. Não certifica edição, animação, direção de arte ou qualidade profissional.",
        },
    ]
    result = {
        "schema": "HazewaveSyntheticLearningDatasetPreview/v1",
        "harness_authority": "HAZEWAVE_HARNESS",
        "source_type": "SOURCE_OWNED_SYNTHETIC_RECEIPTS_ONLY",
        "source_receipt_sha256": {"native": native_hash, "av": av_hash},
        "dataset_name": "hazewave_synthetic_research_demo",
        "format": "alpaca",
        "example_count": len(samples),
        "training_admitted": False,
        "owner_dataset_grant": "NOT_PROVEN",
        "production_approved": False,
        "synthetic_preview_only": True,
        "limitations": "Examples demonstrate schema compatibility, not suitability for SFT.",
    }
    root = Path(output_root)
    if root.exists() or root.is_symlink() or root.parent.is_symlink():
        raise LearningBridgeError("OUTPUT_DIR_NOT_ADMITTED")
    root.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    _write_private(root / "hazewave_synthetic_research_demo.json", samples)
    _write_private(root / "dataset_info.json", {
        "hazewave_synthetic_research_demo": {
            "file_name": "hazewave_synthetic_research_demo.json",
            "formatting": "alpaca",
        }
    })
    _write_private(root / "preview-receipt.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--native-receipt", required=True, type=Path)
    p.add_argument("--av-receipt", required=True, type=Path)
    p.add_argument("--output-root", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        result = export_synthetic_examples(
            native_receipt=a.native_receipt, av_receipt=a.av_receipt, output_root=a.output_root
        )
    except (LearningBridgeError, OSError) as exc:
        print("HAZEWAVE_LLAMAFABRIC_DATASET=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print("HAZEWAVE_LLAMAFABRIC_DATASET=PASS_SYNTHETIC_FORMAT")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
