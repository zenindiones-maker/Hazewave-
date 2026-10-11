"""Fail-closed contracts for the seven external ArtCraft executors.
No owner-private pixels, third-party executable, A15 runtime or fake render in tests.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wave_artcraft_external_tools.py"
LOCK = ROOT / "scripts" / "wave_artcraft-seven-lock.json"
spec = importlib.util.spec_from_file_location("wave_artcraft_external_tools", SCRIPT)
module = importlib.util.module_from_spec(spec)
if SCRIPT.exists():
    assert spec.loader
    spec.loader.exec_module(module)


class ArtCraftSevenContract(unittest.TestCase):
    def test_seven_lock_is_exact_and_keeps_existing_verified_versions(self):
        entries = module.validate_lock(json.loads(LOCK.read_text()))
        self.assertEqual(set(entries), {
            "photocraft", "lightcraft", "designcraft", "pdfcraft",
            "vectorcraft", "effectcraft", "filmcraft",
        })
        self.assertEqual(entries["vectorcraft"]["version"], "0.7.0")
        self.assertEqual(entries["effectcraft"]["version"], "0.6.0")
        self.assertEqual(entries["filmcraft"]["version"], "0.4.0")
        self.assertEqual({x["authority"] for x in entries.values()}, {"NONE"})
        self.assertEqual({x["data_classification"] for x in entries.values()}, {"PUBLIC"})

    def test_blocks_registry_escalation_and_unpinned_payloads(self):
        correct = json.loads(LOCK.read_text())
        for mutate in [
            lambda x: x["tools"]["photocraft"].update(authority="ROOT"),
            lambda x: x["tools"]["pdfcraft"].update(data_classification="PRIVATE_MEDIA"),
            lambda x: x["tools"]["lightcraft"].update(sha256="0" * 64),
            lambda x: x["tools"]["designcraft"].update(url="https://attacker.invalid/run.tar.gz"),
            lambda x: x["tools"]["effectcraft"].update(binary="bash"),
            lambda x: x["tools"]["photocraft"].update({"auto_activate": True}),
        ]:
            altered = json.loads(json.dumps(correct))
            mutate(altered)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                module.validate_lock(altered)

    def test_extract_only_one_exact_named_cli_and_reject_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "test.tar.gz"
            def pack(members):
                with tarfile.open(archive, "w:gz") as writer:
                    for name, data, mode in members:
                        info = tarfile.TarInfo(name)
                        info.size = len(data)
                        info.mode = mode
                        writer.addfile(info, io.BytesIO(data))
            pack([("release/bin/photocraft-cli", b"ELF" * 20_000, 0o755)])
            extracted = module.extract_cli(archive, root / "out", "photocraft")
            self.assertEqual(extracted.name, "photocraft-cli")
            self.assertEqual(extracted.read_bytes(), b"ELF" * 20_000)
            pack([("../x/photocraft-cli", b"A" * 60_000, 0o755)])
            with self.assertRaises(ValueError):
                module.extract_cli(archive, root / "escape", "photocraft")
            pack([("a/photocraft-cli", b"A" * 60_000, 0o755),
                  ("b/photocraft-cli", b"B" * 60_000, 0o755)])
            with self.assertRaises(ValueError):
                module.extract_cli(archive, root / "duplicate", "photocraft")


if __name__ == "__main__":
    unittest.main()
