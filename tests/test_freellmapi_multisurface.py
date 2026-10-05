from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from hazewave.freellmapi import (
    FreeLLMAPIClient,
    FreeLLMAPIError,
    FreeLLMAPILocalCatalog,
)
from hazewave.harness import HazewaveTask, issue_authorization, route_task


def _auth(task_id: str, capability: str, domain: str):
    return issue_authorization(
        route_task(
            HazewaveTask(
                task_id=task_id,
                goal="bounded provider surface test",
                required_capability=capability,
                requested_domain=domain,
            )
        )
    )


def _db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE api_keys (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL DEFAULT 'unknown'
        );
        CREATE TABLE models (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          model_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          intelligence_rank INTEGER NOT NULL DEFAULT 999,
          speed_rank INTEGER NOT NULL DEFAULT 999,
          context_window INTEGER,
          enabled INTEGER NOT NULL DEFAULT 1,
          supports_vision INTEGER NOT NULL DEFAULT 0,
          supports_tools INTEGER NOT NULL DEFAULT 0,
          key_id INTEGER
        );
        CREATE TABLE embedding_models (
          id INTEGER PRIMARY KEY,
          family TEXT NOT NULL,
          platform TEXT NOT NULL,
          model_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          dimensions INTEGER NOT NULL,
          max_input_tokens INTEGER,
          priority INTEGER NOT NULL DEFAULT 0,
          enabled INTEGER NOT NULL DEFAULT 1,
          quota_label TEXT NOT NULL DEFAULT '',
          key_id INTEGER
        );
        CREATE TABLE media_models (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          model_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          modality TEXT NOT NULL,
          priority INTEGER NOT NULL DEFAULT 0,
          enabled INTEGER NOT NULL DEFAULT 1,
          quota_label TEXT NOT NULL DEFAULT '',
          key_id INTEGER,
          meta_json TEXT
        );
        """
    )
    return con


def _client(handler) -> FreeLLMAPIClient:
    client = FreeLLMAPIClient("http://127.0.0.1:3001/v1", api_key="router-secret")
    client._client.close()
    client._client = httpx.Client(
        base_url="http://127.0.0.1:3001/v1",
        headers={"Authorization": "Bearer router-secret"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_embedding_family_is_allowed_only_when_every_routable_member_is_eligible(
    tmp_path: Path,
) -> None:
    db = tmp_path / "freellmapi.db"
    con = _db(db)
    con.execute("INSERT INTO api_keys VALUES(1,'github',1,'healthy')")
    con.execute("INSERT INTO api_keys VALUES(2,'huggingface',1,'healthy')")
    con.execute(
        "INSERT INTO embedding_models VALUES(1,'safe-family','github','embed-safe','Safe',4,8192,1,1,'',NULL)"
    )
    con.execute(
        "INSERT INTO embedding_models VALUES(2,'mixed-family','github','embed-mixed','Mixed Safe',4,8192,1,1,'',NULL)"
    )
    con.execute(
        "INSERT INTO embedding_models VALUES(3,'mixed-family','huggingface','embed-mixed-hf','Mixed HF',4,8192,2,1,'',NULL)"
    )
    con.commit()
    con.close()

    catalog = FreeLLMAPILocalCatalog(db)

    safe = catalog.eligible_embedding_families(
        capability_id="embedding.create",
        data_classification="PUBLIC",
    )
    assert [family.family for family in safe] == ["safe-family"]


def test_governed_embeddings_binds_family_dimensions_and_provider_receipt(
    tmp_path: Path,
) -> None:
    db = tmp_path / "freellmapi.db"
    con = _db(db)
    con.execute("INSERT INTO api_keys VALUES(1,'github',1,'healthy')")
    con.execute(
        "INSERT INTO embedding_models VALUES(1,'safe-family','github','embed-safe','Safe',4,8192,1,1,'',NULL)"
    )
    con.commit()
    con.close()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        payload = json.loads(request.content)
        assert payload["model"] == "safe-family"
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}],
                "model": "safe-family",
                "provider": "github",
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    authorization = _auth("embed-1", "embedding.create", "HAZE")
    with _client(handler) as client:
        result = client.governed_embeddings(
            input_texts=["sonic motif"],
            authorization=authorization,
            task_id="embed-1",
            capability_id="embedding.create",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
        )

    assert result.raw["data"][0]["embedding"] == [0.1, 0.2, 0.3, 0.4]
    assert result.receipt["embedding_family"] == "safe-family"
    assert result.receipt["dimensions"] == 4
    assert result.receipt["provider"] == "github"
    assert result.receipt["zero_cost_verified"] is True


def test_media_catalog_requires_unique_routable_model_id_across_providers(
    tmp_path: Path,
) -> None:
    db = tmp_path / "freellmapi.db"
    con = _db(db)
    con.execute("INSERT INTO api_keys VALUES(1,'nvidia',1,'healthy')")
    con.execute(
        "INSERT INTO media_models VALUES(1,'pollinations','shared-image','Pollinations','image',1,1,'',NULL,NULL)"
    )
    con.execute(
        "INSERT INTO media_models VALUES(2,'nvidia','shared-image','NVIDIA','image',2,1,'',NULL,NULL)"
    )
    con.commit()
    con.close()

    catalog = FreeLLMAPILocalCatalog(db)
    with pytest.raises(FreeLLMAPIError, match="AMBIGUOUS_MEDIA_MODEL"):
        catalog.eligible_media_candidates(
            modality="image",
            capability_id="visual.image",
            data_classification="PUBLIC",
        )


@pytest.mark.parametrize(
    ("method_name", "endpoint", "modality", "capability", "model_id", "binary"),
    [
        ("governed_image", "/v1/images/generations", "image", "visual.image", "pollinations-image", False),
        ("governed_video", "/v1/videos/generations", "video", "visual.video", "pollinations-video", True),
        ("governed_speech", "/v1/audio/speech", "audio", "audio.voice", "pollinations-speech", True),
    ],
)
def test_governed_public_media_never_uses_auto(
    tmp_path: Path,
    method_name: str,
    endpoint: str,
    modality: str,
    capability: str,
    model_id: str,
    binary: bool,
) -> None:
    db = tmp_path / "freellmapi.db"
    con = _db(db)
    con.execute(
        "INSERT INTO media_models VALUES(1,'pollinations',?,?,?,1,1,'',NULL,NULL)",
        (model_id, model_id, modality),
    )
    con.commit()
    con.close()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == endpoint
        payload = json.loads(request.content)
        assert payload["model"] == model_id
        assert payload["model"] != "auto"
        if binary:
            return httpx.Response(
                200,
                content=b"media-bytes",
                headers={
                    "Content-Type": "video/mp4" if modality == "video" else "audio/mpeg",
                    "X-Provider": "pollinations",
                    "X-Model": model_id,
                },
            )
        return httpx.Response(
            200,
            json={
                "created": 1,
                "data": [{"url": "https://example.invalid/generated.png"}],
                "model": model_id,
                "provider": "pollinations",
            },
        )

    domain = "WAVE" if capability.startswith("visual.") else "HAZE"
    authorization = _auth(f"media-{modality}", capability, domain)
    kwargs = dict(
        authorization=authorization,
        task_id=f"media-{modality}",
        capability_id=capability,
        data_classification="PUBLIC",
        catalog=FreeLLMAPILocalCatalog(db),
    )
    if method_name == "governed_speech":
        kwargs["text"] = "public scratch narration"
    else:
        kwargs["prompt"] = "public generative test prompt"

    with _client(handler) as client:
        result = getattr(client, method_name)(**kwargs)

    assert result.receipt["provider"] == "pollinations"
    assert result.receipt["zero_cost_verified"] is True
    assert "router-secret" not in json.dumps(result.receipt, sort_keys=True)


def test_governed_transcription_sends_public_audio_to_exact_unique_model(
    tmp_path: Path,
) -> None:
    db = tmp_path / "freellmapi.db"
    con = _db(db)
    con.execute("INSERT INTO api_keys VALUES(1,'groq',1,'healthy')")
    con.execute(
        "INSERT INTO media_models VALUES(1,'groq','whisper-free','Whisper','transcription',1,1,'',NULL,NULL)"
    )
    con.commit()
    con.close()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/audio/transcriptions"
        assert "multipart/form-data" in request.headers["content-type"]
        body = request.content
        assert b"whisper-free" in body
        assert b"audio-bytes" in body
        return httpx.Response(
            200,
            headers={"X-Provider": "groq", "X-Model": "whisper-free"},
            json={"text": "transcribed"},
        )

    authorization = _auth("stt-1", "audio.transcribe", "HAZE")
    with _client(handler) as client:
        result = client.governed_transcription(
            audio_bytes=b"audio-bytes",
            filename="public.wav",
            mime_type="audio/wav",
            authorization=authorization,
            task_id="stt-1",
            capability_id="audio.transcribe",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
        )

    assert result.raw["text"] == "transcribed"
    assert result.receipt["provider"] == "groq"


def test_governed_fusion_uses_only_explicit_policy_eligible_panel_and_judge(
    tmp_path: Path,
) -> None:
    db = tmp_path / "freellmapi.db"
    con = _db(db)
    con.execute("INSERT INTO api_keys VALUES(1,'kilo',1,'healthy')")
    con.execute("INSERT INTO api_keys VALUES(2,'ovh',1,'healthy')")
    con.execute(
        "INSERT INTO models VALUES(1,'kilo','panel-a','Panel A',1,1,65536,1,0,0,NULL)"
    )
    con.execute(
        "INSERT INTO models VALUES(2,'ovh','panel-b','Panel B',2,2,65536,1,0,0,NULL)"
    )
    con.commit()
    con.close()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "fusion"
        assert payload["fusion"]["models"] == ["kilo:panel-a", "ovh:panel-b"]
        assert payload["fusion"]["judge"] == "kilo:panel-a"
        return httpx.Response(
            200,
            headers={"X-Routed-Via": "fusion"},
            json={
                "model": "fusion",
                "choices": [{"message": {"role": "assistant", "content": "synthesis"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cost": 0},
                "x_fusion": {
                    "panel": [
                        {"platform": "kilo", "model": "panel-a"},
                        {"platform": "ovh", "model": "panel-b"},
                    ],
                    "judge": {"platform": "kilo", "model": "panel-a"},
                },
            },
        )

    authorization = _auth("fusion-1", "reason.fusion", "WAVE")
    with _client(handler) as client:
        result = client.governed_fusion(
            messages=[{"role": "user", "content": "compare two public design ideas"}],
            authorization=authorization,
            task_id="fusion-1",
            capability_id="reason.fusion",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
            panel_size=2,
        )

    assert result.content == "synthesis"
    assert result.receipt["quota_cost_class"] == "HIGH"
    assert result.receipt["panel_models"] == ["kilo:panel-a", "ovh:panel-b"]
    assert result.receipt["zero_cost_verified"] is True


def test_tool_call_is_a_proposal_not_tool_execution(
    tmp_path: Path,
) -> None:
    db = tmp_path / "freellmapi.db"
    con = _db(db)
    con.execute("INSERT INTO api_keys VALUES(1,'kilo',1,'healthy')")
    con.execute(
        "INSERT INTO models VALUES(1,'kilo','tool-model','Tool Model',1,1,65536,1,0,1,NULL)"
    )
    con.commit()
    con.close()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["tools"][0]["function"]["name"] == "lookup_asset"
        return httpx.Response(
            200,
            headers={"X-Routed-Via": "kilo/tool-model"},
            json={
                "model": "tool-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {"name": "lookup_asset", "arguments": "{}"},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"cost": 0},
            },
        )

    authorization = _auth("tool-1", "reason.general", "HAZE")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_asset",
                "description": "Propose an asset lookup",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    with _client(handler) as client:
        result = client.governed_chat(
            messages=[{"role": "user", "content": "find the asset"}],
            authorization=authorization,
            task_id="tool-1",
            capability_id="reason.general",
            data_classification="PUBLIC",
            catalog=FreeLLMAPILocalCatalog(db),
            tools=tools,
            tool_choice="auto",
        )

    assert result.content == ""
    assert result.raw["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "lookup_asset"
    assert result.receipt["tool_execution_authority"] == "HAZEWAVE_HARNESS"
