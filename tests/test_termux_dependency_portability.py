from __future__ import annotations

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_dev_schema_validation_stack_is_termux_portable() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = config["project"]["optional-dependencies"]["dev"]

    assert "jsonschema==4.17.3" in dev
    assert any(item.startswith("pyrsistent>=") for item in dev)
    assert not any("rpds" in item.lower() for item in dev)


def test_ci_exercises_supported_desktop_and_termux_python_minor() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'python-version: ["3.12", "3.14"]' in workflow


def test_validator_reports_schema_engine_for_runtime_diagnostics() -> None:
    validator = (
        ROOT / "scripts" / "validate_repository_contracts.py"
    ).read_text(encoding="utf-8")

    assert "HAZEWAVE_JSON_SCHEMA_ENGINE=" in validator
