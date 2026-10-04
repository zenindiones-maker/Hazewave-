from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_INSTANCE_PAIRS = (
    ("schemas/project-profile-v2.schema.json", "config/project-profile-v2.json"),
    ("schemas/documentation-registry-v2.schema.json", "docs/DOCUMENTATION_REGISTRY_V2.json"),
    ("schemas/haze-state-v1.schema.json", "examples/contracts/haze-state-v1.example.json"),
    ("schemas/wave-state-v1.schema.json", "examples/contracts/wave-state-v1.example.json"),
    (
        "schemas/hazewave-asset-manifest-v1.schema.json",
        "examples/contracts/hazewave-asset-manifest-v1.example.json",
    ),
)

ALLOWED_DOCUMENT_TYPES = {
    "AGENT_CONTRACT",
    "PROJECT_PROFILE",
    "CANON",
    "ARCHITECTURE_DECISION",
    "EXPLANATION",
    "REFERENCE",
    "RUNBOOK",
    "PUBLISHING_STANDARD",
    "PROJECT_SPEC",
}
ALLOWED_AUTHORITIES = {"NORMATIVE", "CANONICAL", "OPERATIONAL", "EXPLANATORY"}
ALLOWED_STATUSES = {"ACTIVE", "DEVELOPMENT", "SUPERSEDED"}

REQUIRED_AGENT_HEADINGS = (
    "## Authority",
    "## Source-of-truth precedence",
    "## Setup",
    "## Test and validation commands",
    "## Domain routing",
    "## Data classification",
    "## Write rules",
    "## Stop conditions",
    "## Handoff contract",
)

ISOLATION_SCAN_ROOTS = (
    "AGENTS.md",
    "config",
    "canon",
    "schemas",
    "docs",
    "scripts",
    "src",
    "examples",
)
FORBIDDEN_EXTERNAL_MARKERS = (
    "BR-no-GTA",
    "~/GTA/BR",
    ".local/state/br-no-gta",
)


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def validate_schema_instances() -> None:
    for schema_path, instance_path in SCHEMA_INSTANCE_PAIRS:
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(load_json(instance_path))


def validate_registry() -> None:
    registry = load_json("docs/DOCUMENTATION_REGISTRY_V2.json")
    ids: set[str] = set()
    for entry in registry["documents"]:
        if entry["id"] in ids:
            raise ValueError(f"DUPLICATE_DOCUMENT_ID:{entry['id']}")
        ids.add(entry["id"])
        if entry["type"] not in ALLOWED_DOCUMENT_TYPES:
            raise ValueError(f"UNKNOWN_DOCUMENT_TYPE:{entry['type']}")
        if entry["authority"] not in ALLOWED_AUTHORITIES:
            raise ValueError(f"UNKNOWN_DOCUMENT_AUTHORITY:{entry['authority']}")
        if entry["status"] not in ALLOWED_STATUSES:
            raise ValueError(f"UNKNOWN_DOCUMENT_STATUS:{entry['status']}")
        path = ROOT / entry["path"]
        if not path.is_file():
            raise FileNotFoundError(f"REGISTERED_DOCUMENT_MISSING:{entry['path']}")


def validate_agent_contract() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for heading in REQUIRED_AGENT_HEADINGS:
        if heading not in text:
            raise ValueError(f"AGENT_CONTRACT_HEADING_MISSING:{heading}")


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for item in ISOLATION_SCAN_ROOTS:
        path = ROOT / item
        if path.is_file():
            files.append(path)
            continue
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in {
                    ".md",
                    ".json",
                    ".py",
                    ".sh",
                    ".toml",
                    ".yml",
                    ".yaml",
                }:
                    files.append(candidate)
    return files


def validate_project_isolation() -> None:
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in FORBIDDEN_EXTERNAL_MARKERS:
            if marker in text:
                relative = path.relative_to(ROOT)
                raise ValueError(f"NAMED_CROSS_PROJECT_COUPLING:{relative}:{marker}")


def validate_profile_migration() -> None:
    old = load_json("config/project-profile-v1.json")
    if old.get("status") != "SUPERSEDED":
        raise ValueError("PROJECT_PROFILE_V1_NOT_SUPERSEDED")
    if old.get("superseded_by") != "config/project-profile-v2.json":
        raise ValueError("PROJECT_PROFILE_V1_REPLACEMENT_INVALID")


def main() -> int:
    validate_schema_instances()
    validate_registry()
    validate_agent_contract()
    validate_project_isolation()
    validate_profile_migration()
    print("HAZEWAVE_SCHEMA_VALIDATION=PASS")
    print("HAZEWAVE_DOCUMENTATION_REGISTRY=PASS")
    print("HAZEWAVE_AGENT_CONTRACT=PASS")
    print("HAZEWAVE_PROJECT_ISOLATION=PASS")
    print("HAZEWAVE_PROJECT_PROFILE_MIGRATION=PASS")
    print("HAZEWAVE_REPOSITORY_CONTRACTS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
