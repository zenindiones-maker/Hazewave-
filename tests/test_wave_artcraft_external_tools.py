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

    def test_harness_is_real_routing_authority_for_all_seven(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from hazewave.harness import classify_capability_domain, WAVE
        from hazewave.wave_artcraft import admit_artcraft
        approved = {}
        for app in sorted(module.NAMES):
            receipt = admit_artcraft(task_id="ci-wave-artcraft-001", tool=app,
                                     data_classification="PUBLIC",
                                     requested_domain="WAVE")
            self.assertEqual(receipt.schema, "HazewaveArtCraftHarnessAdmission/v1")
            self.assertEqual(receipt.tool, app)
            self.assertEqual(receipt.project_id, "HAZEWAVE")
            self.assertEqual(receipt.domain, WAVE)
            self.assertEqual(receipt.authority, "HAZEWAVE_HARNESS")
            self.assertEqual(receipt.execution_boundary, "PUBLIC_SYNTHETIC_OFFLINE")
            self.assertEqual(classify_capability_domain(receipt.capability_id), WAVE)
            self.assertEqual(len(receipt.authorization_id), 64)
            approved[app] = receipt.capability_id
        self.assertEqual(set(approved), set(module.NAMES))

    def test_harness_never_admits_private_media_wrong_domain_or_unknown_provider(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from hazewave.wave_artcraft import admit_artcraft
        for invalid in [
            {"tool": "photoshop"},
            {"tool": "photocraft", "requested_domain": "HAZE"},
            {"tool": "photocraft", "requested_domain": "BRIDGE"},
            {"tool": "photocraft", "data_classification": "PRIVATE_MEDIA"},
            {"tool": "photocraft", "data_classification": "CREDENTIAL"},
            {"tool": "photocraft", "task_id": "../escape"},
            {"tool": "photocraft", "task_id": " "},
        ]:
            options = {"task_id": "ci-wave-artcraft-001",
                       "tool": "photocraft", "data_classification": "PUBLIC",
                       "requested_domain": "WAVE"} | invalid
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, PermissionError)):
                admit_artcraft(**options)

    def test_smoke_uses_existing_harness_capability_and_rejects_self_authority(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from hazewave.wave_artcraft import admit_artcraft, verify_admission
        admission = admit_artcraft(task_id="ci-wave-artcraft-001", tool="designcraft",
                                   data_classification="PUBLIC", requested_domain="WAVE")
        verify_admission(admission, expected_tool="designcraft", expected_task_id="ci-wave-artcraft-001")
        with self.assertRaises(PermissionError):
            verify_admission(admission, expected_tool="photocraft", expected_task_id="ci-wave-artcraft-001")
        with self.assertRaises(PermissionError):
            verify_admission(admission, expected_tool="designcraft", expected_task_id="other-task")
        self.assertNotIn("artcraft", admission.authority.lower())

    def test_lightcraft_must_consume_harness_verified_photocraft_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises((ValueError, FileNotFoundError)):
                module.select_image_input("lightcraft", root, upstream_task_id="artcraft-ci-photocraft")
            module.small_png(root / "hazewave-synthetic-signal.png")
            module.small_png(root / "photocraft-render.png")
            # Even a genuine PNG cannot bypass upstream receipt / exact task boundary.
            (root / "photocraft-receipt.json").write_text(json.dumps({
                "schema": "HazewaveArtCraftExternalRealSmoke/v1",
                "tool": "photocraft",
                "output": "photocraft-render.png",
                "output_sha256": "0" * 64,
                "admission": {"authority": "NONE"},
            }))
            with self.assertRaises((ValueError, PermissionError)):
                module.select_image_input("lightcraft", root,
                                          upstream_task_id="artcraft-ci-photocraft")

    def test_unrelated_tool_cannot_claim_a_cross_stage_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                module.select_image_input("pdfcraft", root, upstream_task_id=None)
            with self.assertRaises(ValueError):
                module.select_image_input("photocraft", root,
                                          upstream_task_id="artcraft-ci-photocraft")


if __name__ == "__main__":
    unittest.main()
