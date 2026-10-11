"""Adversarial WAVE seven-tool delivery contract. No fake real-execution receipts."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/wave_artcraft_seven_handoff.py"


class WAVESevenToolHandoffContract(unittest.TestCase):
    def test_missing_evidence_blocks_seven_tool_handoff_without_output(self):
        spec = importlib.util.spec_from_file_location("wave_artcraft_seven_handoff", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            folders = {name: base / name for name in ("image", "editorial", "vector", "motion")}
            for folder in folders.values():
                folder.mkdir()
            target = base / "result"
            with self.assertRaises((ValueError, FileNotFoundError, PermissionError)):
                module.assemble(
                    image=folders["image"], editorial=folders["editorial"],
                    vector=folders["vector"], motion=folders["motion"],
                    output=target, run_id="1234567890",
                    head_sha="a" * 40,
                )
            self.assertFalse(target.exists())

    def test_manifest_verifier_refuses_absent_media_and_production_claim(self):
        spec = importlib.util.spec_from_file_location("wave_artcraft_seven_handoff", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = {
                "schema": "HazewaveArtCraftSevenLabHandoff/v1",
                "repository": "zenindiones-maker/Hazewave-",
                "run_id": "1234567890", "head_sha": "a" * 40,
                "domain": "WAVE", "authority": "HAZEWAVE_HARNESS",
                "classification": "PUBLIC",
                "owner_private_media_used": False,
                "production_approved": True,
                "publication_attempted": False,
                "all_seven_external_clis_executed": True,
                "artifacts": {"photocraft": {
                    "path": "../escaped.png", "sha256": "1" * 64
                }},
            }
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises((ValueError, PermissionError)):
                module.verify_bundle(root, run_id="1234567890", head_sha="a" * 40)


if __name__ == "__main__":
    unittest.main()
