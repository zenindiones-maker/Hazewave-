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
