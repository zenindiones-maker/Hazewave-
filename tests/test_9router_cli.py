from __future__ import annotations

import json
import sys

from hazewave.ninerouter import NineRouterExecutionResult


def test_cli_parses_governed_9router_execute_defaults() -> None:
    from hazewave.cli import build_parser

    args = build_parser().parse_args(
        ["9router", "execute", "--prompt", "hello"]
    )

    assert args.command == "9router"
    assert args.ninerouter_command == "execute"
    assert args.model == "auto"
    assert args.max_fallbacks == 3
    assert args.capability == "reason.general"
    assert args.domain == "HAZE"
    assert args.data_classification == "PUBLIC"
    assert args.max_tokens == 1024


def test_cli_executes_only_through_harness_authorization(monkeypatch, capsys) -> None:
    import hazewave.cli as cli

    captured = {}

    def fake_execute(**kwargs):
        authorization = kwargs["authorization"]
        captured["authority"] = authorization.authority
        captured["task_id"] = authorization.task_id
        captured["capability"] = authorization.capability_id
        captured["domain"] = authorization.domain
        captured["model_id"] = kwargs["model_id"]
        captured["prompt"] = kwargs["prompt"]
        captured["classification"] = kwargs["data_classification"]
        return NineRouterExecutionResult(
            status="PASS",
            task_id=authorization.task_id,
            authorization_id=authorization.authorization_id,
            model_id=kwargs["model_id"],
            content="governed answer",
            prompt_tokens=3,
            completion_tokens=2,
            total_tokens=5,
        )

    monkeypatch.setattr(cli, "execute_9router_text", fake_execute)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hazewave",
            "9router",
            "execute",
            "--prompt",
            "hello",
            "--task-id",
            "cli-task-1",
        ],
    )

    rc = cli.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert captured == {
        "authority": "HAZEWAVE_HARNESS",
        "task_id": "cli-task-1",
        "capability": "reason.general",
        "domain": "HAZE",
        "model_id": "auto",
        "prompt": "hello",
        "classification": "PUBLIC",
    }
    assert "HAZEWAVE_9ROUTER_EXECUTION=PASS" in out
    payload = json.loads(out.splitlines()[-1])
    assert payload["content"] == "governed answer"
    assert payload["zero_cost_verified"] is True


def test_cli_parses_9router_efficiency_status() -> None:
    from hazewave.cli import build_parser

    args = build_parser().parse_args(["9router", "status"])

    assert args.command == "9router"
    assert args.ninerouter_command == "status"


def test_cli_prints_9router_efficiency_status(monkeypatch, capsys) -> None:
    import hazewave.cli as cli

    monkeypatch.setattr(
        cli,
        "build_9router_efficiency_status",
        lambda: {
            "schema": "Hazewave9RouterEfficiencyStatus/v1",
            "project_id": "HAZEWAVE",
            "authority": "HAZEWAVE_HARNESS",
            "receipt_present": True,
            "admitted_model_count": 3,
            "ranked_models": ["oc/mimo-v2.6-flash-free"],
        },
    )
    monkeypatch.setattr(sys, "argv", ["hazewave", "9router", "status"])

    rc = cli.main()
    out = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(out.splitlines()[-1])
    assert payload["schema"] == "Hazewave9RouterEfficiencyStatus/v1"
    assert payload["admitted_model_count"] == 3


def test_cli_accepts_messages_file_instead_of_prompt(tmp_path) -> None:
    from hazewave.cli import build_parser

    messages_file = tmp_path / "messages.json"
    messages_file.write_text(
        json.dumps([{"role": "user", "content": "hello"}]),
        encoding="utf-8",
    )

    args = build_parser().parse_args(
        ["9router", "execute", "--messages-file", str(messages_file)]
    )

    assert args.prompt is None
    assert args.messages_file == str(messages_file)


def test_cli_routes_messages_file_through_governed_messages_executor(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import hazewave.cli as cli

    messages = [
        {"role": "user", "content": "inspect"},
        {"role": "tool", "tool_call_id": "c1", "content": "public output"},
    ]
    messages_file = tmp_path / "messages.json"
    messages_file.write_text(json.dumps(messages), encoding="utf-8")

    captured = {}

    def fake_execute_messages(**kwargs):
        captured.update(kwargs)
        authorization = kwargs["authorization"]
        return NineRouterExecutionResult(
            status="PASS",
            task_id=authorization.task_id,
            authorization_id=authorization.authorization_id,
            model_id="oc/mimo-v2.6-flash-free",
            content="done",
            prompt_tokens=20,
            completion_tokens=2,
            total_tokens=22,
        )

    monkeypatch.setattr(
        cli,
        "execute_9router_messages",
        fake_execute_messages,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hazewave",
            "9router",
            "execute",
            "--messages-file",
            str(messages_file),
            "--task-id",
            "tool-cli-1",
            "--capability",
            "code.review",
        ],
    )

    rc = cli.main()

    assert rc == 0
    assert captured["messages"] == messages
    assert captured["authorization"].authority == "HAZEWAVE_HARNESS"
    assert captured["data_classification"] == "PUBLIC"
