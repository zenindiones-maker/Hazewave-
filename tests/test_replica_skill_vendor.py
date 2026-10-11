from hashlib import sha1
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "replica-skill-vendor-v1.json"

def test_vendor_is_exactly_pinned_and_has_no_duplicate_git():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["authority"] == "NONE"
    assert manifest["project_authority"] == "HAZEWAVE_HARNESS"
    assert manifest["license"] == "MIT"
    assert manifest["enabled_side_effects"] == []
    assert manifest["requires_explicit_harness_admission"] is True
    assert len(manifest["files"]) == 28
    for item in manifest["files"]:
        file_path = ROOT / item["path"]
        assert file_path.is_file(), item["path"]
        data = file_path.read_bytes()
        blob = b"blob " + str(len(data)).encode() + b"\x00" + data
        assert sha1(blob).hexdigest() == item["git_blob_sha"], item["path"]
        assert not (file_path.parent / ".git").exists()
    skills = sorted((ROOT / ".claude" / "skills").glob("replica-*/SKILL.md"))
    assert len(skills) == 11

def test_replica_skill_preserves_owner_authority():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    forbidden = {"deploy", "publish", "payment", "execute", "write_secrets"}
    assert not forbidden.intersection(manifest["enabled_side_effects"])
    assert "deployment" in manifest["human_approval_required_for"]
    assert "publication" in manifest["human_approval_required_for"]
