from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

PORTABLE_UNSUPPORTED_SCHEMA_KEYWORDS = {
    "$dynamicRef",
    "$recursiveRef",
    "$vocabulary",
}

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


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _walk_schema_keywords(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PORTABLE_UNSUPPORTED_SCHEMA_KEYWORDS:
                found.add(key)
            found.update(_walk_schema_keywords(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_walk_schema_keywords(child))
    return found


def validate_portable_schema_subset() -> None:
    for schema_path, _ in SCHEMA_INSTANCE_PAIRS:
        schema = load_json(schema_path)
        unsupported = _walk_schema_keywords(schema)
        if unsupported:
            values = ",".join(sorted(unsupported))
            raise ValueError(f"TERMUX_SCHEMA_FEATURE_REQUIRES_REVIEW:{schema_path}:{values}")


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


def validate_project_isolation() -> None:
    profile = load_json("config/project-profile-v2.json")
    if profile.get("portfolio_authority") != "NONE":
        raise ValueError("PORTFOLIO_AUTHORITY_MUST_BE_NONE")

    runtime = profile.get("runtime_model") or {}
    for key in ("state_namespace", "config_namespace", "deploy_namespace"):
        if runtime.get(key) != "hazewave":
            raise ValueError(f"NON_HAZEWAVE_RUNTIME_NAMESPACE:{key}")

    installer = (ROOT / "scripts" / "install_hazewave_termux_runtime.sh").read_text(
        encoding="utf-8"
    )
    control = (ROOT / "scripts" / "hazewave_termux_control.sh").read_text(
        encoding="utf-8"
    )
    combined = installer + "\n" + control
    for required in (
        ".local/share/hazewave/deploy",
        ".local/state/hazewave",
        ".config/hazewave",
    ):
        if required not in combined:
            raise ValueError(f"HAZEWAVE_RUNTIME_NAMESPACE_MISSING:{required}")


def validate_telegram_runtime_contract() -> None:
    required_files = (
        "src/hazewave/telegram_gateway.py",
        "scripts/configure_hazewave_telegram.sh",
        "scripts/hazewave_telegram_control.sh",
        "scripts/install_hazewave_telegram_persistence.sh",
        "docs/architecture/decisions/ADR-0004-hazewave-telegram-runtime-isolation.md",
        "docs/runbooks/TELEGRAM_RUNTIME_V1.md",
    )
    for relative in required_files:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(f"HAZEWAVE_TELEGRAM_RUNTIME_MISSING:{relative}")

    combined = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "scripts/configure_hazewave_telegram.sh",
            "scripts/hazewave_telegram_control.sh",
            "scripts/install_hazewave_telegram_persistence.sh",
        )
    )
    for required in (
        ".config/hazewave/telegram",
        ".local/state/hazewave/telegram",
        ".local/share/hazewave/deploy/current",
        "HazewaveAgentBot",
    ):
        if required not in combined:
            raise ValueError(f"HAZEWAVE_TELEGRAM_ISOLATION_MISSING:{required}")
    if "Hazewave-dev" in combined:
        raise ValueError("HAZEWAVE_TELEGRAM_DEPENDS_ON_DEVELOPMENT_CHECKOUT")
    control = (ROOT / "scripts" / "hazewave_telegram_control.sh").read_text(
        encoding="utf-8"
    )
    for forbidden in ("git merge", "git pull", "git checkout"):
        if forbidden in control:
            raise ValueError(f"HAZEWAVE_TELEGRAM_RUNTIME_MUTATES_GIT:{forbidden}")


def validate_profile_migration() -> None:
    old = load_json("config/project-profile-v1.json")
    if old.get("status") != "SUPERSEDED":
        raise ValueError("PROJECT_PROFILE_V1_NOT_SUPERSEDED")
    if old.get("superseded_by") != "config/project-profile-v2.json":
        raise ValueError("PROJECT_PROFILE_V1_REPLACEMENT_INVALID")


def main() -> int:
    validate_portable_schema_subset()
    validate_schema_instances()
    validate_registry()
    validate_agent_contract()
    validate_project_isolation()
    validate_telegram_runtime_contract()
    validate_profile_migration()
    print(f"HAZEWAVE_JSON_SCHEMA_ENGINE=jsonschema/{version('jsonschema')}")
    print("HAZEWAVE_SCHEMA_PORTABLE_SUBSET=PASS")
    print("HAZEWAVE_SCHEMA_VALIDATION=PASS")
    print("HAZEWAVE_DOCUMENTATION_REGISTRY=PASS")
    print("HAZEWAVE_AGENT_CONTRACT=PASS")
    print("HAZEWAVE_PROJECT_ISOLATION=PASS")
    print("HAZEWAVE_TELEGRAM_RUNTIME_ISOLATION=PASS")
    print("HAZEWAVE_PROJECT_PROFILE_MIGRATION=PASS")
    print("HAZEWAVE_REPOSITORY_CONTRACTS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
