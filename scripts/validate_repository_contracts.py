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
    (
        "schemas/freellmapi-provider-eligibility-v1.schema.json",
        "config/freellmapi-provider-eligibility-v1.json",
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



def validate_freellmapi_provider_contract() -> None:
    required_files = (
        "src/hazewave/freellmapi.py",
        "scripts/install_hazewave_freellmapi_termux.sh",
        "scripts/hazewave_freellmapi_control.sh",
        "scripts/install_hazewave_freellmapi_persistence.sh",
        "docs/architecture/decisions/ADR-0005-freellmapi-provider-gateway.md",
        "docs/architecture/decisions/ADR-0006-governed-zero-cost-provider-fabric.md",
        "schemas/freellmapi-provider-eligibility-v1.schema.json",
        "config/freellmapi-provider-eligibility-v1.json",
        "docs/runbooks/FREELLMAPI_PROVIDER_V1.md",
    )
    for relative in required_files:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(f"HAZEWAVE_FREELLMAPI_MISSING:{relative}")

    provider = (ROOT / "src" / "hazewave" / "freellmapi.py").read_text(
        encoding="utf-8"
    )
    installer = (
        ROOT / "scripts" / "install_hazewave_freellmapi_termux.sh"
    ).read_text(encoding="utf-8")
    control = (
        ROOT / "scripts" / "hazewave_freellmapi_control.sh"
    ).read_text(encoding="utf-8")
    persistence = (
        ROOT / "scripts" / "install_hazewave_freellmapi_persistence.sh"
    ).read_text(encoding="utf-8")
    combined = provider + "\n" + installer + "\n" + control + "\n" + persistence

    required = (
        "716948f20b12ec1c9b7c6fcebd22a3e7233cda1b",
        ".local/share/hazewave/providers/freellmapi",
        ".local/state/hazewave/providers/freellmapi",
        ".config/hazewave/providers/freellmapi",
        "HOST=127.0.0.1",
        "FREELLMAPI_UPDATE_CHECK=off",
        "server/dist/index.js",
        ".termux/boot",
        "hazewave-freellmapi.sh",
        "HAZEWAVE_HARNESS",
        "_ALLOWED_EGRESS_CLASSES",
        "PUBLIC",
        "DATA_CLASS_NOT_ALLOWED_FOR_FREELLMAPI",
    )
    for value in required:
        if value not in combined:
            raise ValueError(f"HAZEWAVE_FREELLMAPI_CONTRACT_MISSING:{value}")
    if "BR-no-GTA" in combined:
        raise ValueError("HAZEWAVE_FREELLMAPI_CROSS_PROJECT_REFERENCE")

    eligibility = load_json("config/freellmapi-provider-eligibility-v1.json")
    if eligibility.get("authority") != "HAZEWAVE_HARNESS":
        raise ValueError("HAZEWAVE_FREE_FABRIC_AUTHORITY_INVALID")
    if eligibility.get("paid_fallback") != "FORBIDDEN":
        raise ValueError("HAZEWAVE_FREE_FABRIC_PAID_FALLBACK_MUST_BE_FORBIDDEN")
    if eligibility.get("unknown_cost") != "DENY":
        raise ValueError("HAZEWAVE_FREE_FABRIC_UNKNOWN_COST_MUST_DENY")
    default_policy = eligibility.get("default_policy") or {}
    if default_policy.get("trust_lane") != "QUARANTINED" or default_policy.get("enabled") is not False:
        raise ValueError("HAZEWAVE_FREE_FABRIC_DEFAULT_MUST_BE_QUARANTINED")
    for entry in eligibility.get("providers") or []:
        if "CREDENTIAL" in (entry.get("allowed_data_classes") or []):
            raise ValueError(f"HAZEWAVE_FREE_FABRIC_CREDENTIAL_EGRESS_ALLOWED:{entry.get('provider')}")
        if entry.get("enabled") is True:
            monetary = entry.get("monetary_policy")
            billing = entry.get("billing_overflow_policy")
            unconditional = (
                monetary == "ZERO_COST_VERIFIED"
                and billing == "HARD_STOP"
            )
            account_bound = (
                monetary == "ZERO_COST_REQUIRES_ACCOUNT_HARD_CAP"
                and billing == "ACCOUNT_ATTESTATION_REQUIRED"
            )
            if not (unconditional or account_bound):
                raise ValueError(
                    f"HAZEWAVE_FREE_FABRIC_NONZERO_ROUTE_ENABLED:{entry.get('provider')}"
                )


def validate_9router_sidecar_contract() -> None:
    required_files = (
        "config/9router-upstream-v1.json",
        "config/9router-efficiency-policy-v1.json",
        "scripts/install_hazewave_9router_termux.sh",
        "scripts/hazewave_9router_control.sh",
        "scripts/hazewave_9router_free_probe.sh",
    )
    for relative in required_files:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(f"HAZEWAVE_9ROUTER_MISSING:{relative}")

    manifest = load_json("config/9router-upstream-v1.json")
    if manifest.get("authority") != "NONE":
        raise ValueError("HAZEWAVE_9ROUTER_AUTHORITY_MUST_BE_NONE")
    if manifest.get("project_authority") != "HAZEWAVE_HARNESS":
        raise ValueError("HAZEWAVE_9ROUTER_PROJECT_AUTHORITY_INVALID")
    if manifest.get("repository") != "decolua/9router":
        raise ValueError("HAZEWAVE_9ROUTER_REPOSITORY_INVALID")
    if manifest.get("version") != "0.5.95":
        raise ValueError("HAZEWAVE_9ROUTER_VERSION_INVALID")
    if manifest.get("commit") != "a99cf57239ff778b61e434c2786009d5ed1c412c":
        raise ValueError("HAZEWAVE_9ROUTER_COMMIT_INVALID")
    if manifest.get("bind_host") != "127.0.0.1":
        raise ValueError("HAZEWAVE_9ROUTER_MUST_BIND_LOOPBACK")
    if manifest.get("paid_fallback") != "FORBIDDEN":
        raise ValueError("HAZEWAVE_9ROUTER_PAID_FALLBACK_MUST_BE_FORBIDDEN")
    if manifest.get("unknown_cost") != "DENY":
        raise ValueError("HAZEWAVE_9ROUTER_UNKNOWN_COST_MUST_DENY")
    if manifest.get("execution_policy") != "DISCOVERY_ONLY_UNTIL_ROUTE_ADMISSION":
        raise ValueError("HAZEWAVE_9ROUTER_EXECUTION_POLICY_INVALID")

    efficiency = load_json("config/9router-efficiency-policy-v1.json")
    if efficiency.get("schema") != "Hazewave9RouterEfficiencyPolicy/v1":
        raise ValueError("HAZEWAVE_9ROUTER_EFFICIENCY_SCHEMA_INVALID")
    if efficiency.get("authority") != "HAZEWAVE_HARNESS":
        raise ValueError("HAZEWAVE_9ROUTER_EFFICIENCY_AUTHORITY_INVALID")
    if efficiency.get("gateway_authority") != "NONE":
        raise ValueError("HAZEWAVE_9ROUTER_EFFICIENCY_GATEWAY_AUTHORITY_INVALID")

    security = efficiency.get("security") or {}
    if security.get("minimum_fixed_version") != "0.5.8":
        raise ValueError("HAZEWAVE_9ROUTER_SECURITY_FLOOR_INVALID")
    if security.get("bind") != "127.0.0.1:20128":
        raise ValueError("HAZEWAVE_9ROUTER_EFFICIENCY_BIND_INVALID")

    zero_cost = efficiency.get("zero_cost") or {}
    routing = efficiency.get("routing") or {}
    token_efficiency = efficiency.get("token_efficiency") or {}
    optimizer = efficiency.get("optimizer") or {}

    if zero_cost.get("paid_fallback") != "FORBIDDEN":
        raise ValueError("HAZEWAVE_9ROUTER_EFFICIENCY_PAID_FALLBACK_INVALID")
    if zero_cost.get("unknown_cost") != "DENY" or routing.get("unknown_cost") != "DENY":
        raise ValueError("HAZEWAVE_9ROUTER_EFFICIENCY_UNKNOWN_COST_INVALID")
    if routing.get("combos") != "FORBIDDEN":
        raise ValueError("HAZEWAVE_9ROUTER_COMBOS_MUST_BE_FORBIDDEN")
    if routing.get("capacity_adapters") != "FORBIDDEN":
        raise ValueError("HAZEWAVE_9ROUTER_CAPACITY_ADAPTERS_MUST_BE_FORBIDDEN")
    if routing.get("paid_tiers") != "FORBIDDEN" or routing.get("cheap_tiers") != "FORBIDDEN":
        raise ValueError("HAZEWAVE_9ROUTER_NONFREE_TIERS_MUST_BE_FORBIDDEN")
    if token_efficiency.get("rtk") != "FORCE_ON_DURING_GOVERNED_EXECUTION":
        raise ValueError("HAZEWAVE_9ROUTER_RTK_POLICY_INVALID")
    if token_efficiency.get("headroom") != "OFF_UNTIL_MANAGED_LOCAL_PROOF":
        raise ValueError("HAZEWAVE_9ROUTER_HEADROOM_POLICY_INVALID")
    if token_efficiency.get("stream") is not False:
        raise ValueError("HAZEWAVE_9ROUTER_STREAM_POLICY_INVALID")
    if optimizer.get("benchmark_max_models") != 16:
        raise ValueError("HAZEWAVE_9ROUTER_BENCHMARK_BOUND_INVALID")
    if optimizer.get("execution_max_fallbacks") != 3:
        raise ValueError("HAZEWAVE_9ROUTER_FALLBACK_BOUND_INVALID")
    if optimizer.get("benchmark_sample_count") != 3:
        raise ValueError("HAZEWAVE_9ROUTER_BENCHMARK_SAMPLE_COUNT_INVALID")
    if optimizer.get("general_and_code_selection") != "BALANCED_TOKEN_LATENCY_PRODUCT":
        raise ValueError("HAZEWAVE_9ROUTER_BALANCED_SELECTION_INVALID")
    if (
        optimizer.get("deep_reasoning_selection")
        != "REASONING_EVIDENCE_THEN_BALANCED_TOKEN_LATENCY_PRODUCT"
    ):
        raise ValueError("HAZEWAVE_9ROUTER_DEEP_SELECTION_INVALID")
    live_adaptation = optimizer.get("live_adaptation") or {}
    if (
        live_adaptation.get("source") != "ROUTE_HEALTH_EWMA"
        or live_adaptation.get("alpha") != 0.35
    ):
        raise ValueError("HAZEWAVE_9ROUTER_LIVE_ADAPTATION_INVALID")
    semantic_admission = optimizer.get("semantic_admission") or {}
    if (
        semantic_admission.get("sample_count") != 3
        or semantic_admission.get("minimum_semantic_successes") != 2
        or semantic_admission.get("early_stop_statuses") != [400, 401, 403, 429]
        or semantic_admission.get("stop_when_majority_unreachable") is not True
    ):
        raise ValueError("HAZEWAVE_9ROUTER_SEMANTIC_ADMISSION_INVALID")
    live_adaptation = optimizer.get("live_adaptation") or {}
    prior = live_adaptation.get("reliability_prior") or {}
    if (
        prior.get("alpha") != 2
        or prior.get("beta") != 1
        or live_adaptation.get("reliability_penalty_power") != 2
    ):
        raise ValueError("HAZEWAVE_9ROUTER_RELIABILITY_POLICY_INVALID")
    session_affinity = optimizer.get("session_affinity") or {}
    if (
        session_affinity.get("enabled") is not True
        or session_affinity.get("scope") != "TASK"
        or session_affinity.get("downstream_header") != "x-session-id"
        or session_affinity.get("identity") != "SHA256_TASK_ID_32"
        or session_affinity.get("raw_task_id_egress") is not False
    ):
        raise ValueError("HAZEWAVE_9ROUTER_SESSION_AFFINITY_INVALID")
    cooldown = optimizer.get("transient_cooldown") or {}
    if (
        cooldown.get("base_seconds") != 60
        or cooldown.get("max_seconds") != 900
        or cooldown.get("strategy") != "EXPONENTIAL"
    ):
        raise ValueError("HAZEWAVE_9ROUTER_COOLDOWN_POLICY_INVALID")

    combined = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in required_files[1:]
    )
    for required in (
        "9router@0.5.95",
        "a99cf57239ff778b61e434c2786009d5ed1c412c",
        "127.0.0.1",
        "20128",
        "custom-server.js",
        "HOSTNAME=\"$HOST\"",
        "HAZEWAVE_9ROUTER_AUTHORITY=NONE",
        "HAZEWAVE_9ROUTER_PAID_FALLBACK=FORBIDDEN",
        "DISCOVERY_ONLY_UNTIL_ROUTE_ADMISSION",
        "opencode.ai/zen/v1/models",
        "HAZEWAVE_9ROUTER_FREE_PROBE=PASS",
    ):
        if required not in combined:
            raise ValueError(f"HAZEWAVE_9ROUTER_CONTRACT_MISSING:{required}")


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
    validate_freellmapi_provider_contract()
    validate_9router_sidecar_contract()
    validate_profile_migration()
    print(f"HAZEWAVE_JSON_SCHEMA_ENGINE=jsonschema/{version('jsonschema')}")
    print("HAZEWAVE_SCHEMA_PORTABLE_SUBSET=PASS")
    print("HAZEWAVE_SCHEMA_VALIDATION=PASS")
    print("HAZEWAVE_DOCUMENTATION_REGISTRY=PASS")
    print("HAZEWAVE_AGENT_CONTRACT=PASS")
    print("HAZEWAVE_PROJECT_ISOLATION=PASS")
    print("HAZEWAVE_TELEGRAM_RUNTIME_ISOLATION=PASS")
    print("HAZEWAVE_FREELLMAPI_PROVIDER_CONTRACT=PASS")
    print("HAZEWAVE_9ROUTER_SIDECAR_CONTRACT=PASS")
    print("HAZEWAVE_PROJECT_PROFILE_MIGRATION=PASS")
    print("HAZEWAVE_REPOSITORY_CONTRACTS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
