from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from hazewave.acestep import AceStepClient, AceStepError


def _client(handler) -> AceStepClient:
    client = AceStepClient("http://testserver/")
    client._client.close()
    client._client = httpx.Client(
        base_url="http://testserver/",
        transport=httpx.MockTransport(handler),
    )
    return client


def test_cover_upload_is_forced_instrumental(tmp_path: Path) -> None:
    source = tmp_path / "clean.wav"
    source.write_bytes(b"wave")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/release_task"
        body = request.read()
        assert b"[Instrumental]" in body
        assert b"Instrumental only" in body
        assert b'name="src_audio"' in body
        assert b'name="task_type"' in body
        assert b"cover" in body
        return httpx.Response(
            200,
            json={
                "data": {"task_id": "task-123", "status": "queued"},
                "code": 200,
                "error": None,
            },
        )

    with _client(handler) as client:
        task_id = client.submit_instrumental(
            "dark psychedelic Brazilian rock",
            audio_path=source,
            mode="cover",
            cover_strength=0.85,
        )

    assert task_id == "task-123"


def test_reference_upload_uses_reference_audio(tmp_path: Path) -> None:
    source = tmp_path / "reference.wav"
    source.write_bytes(b"wave")

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b'name="reference_audio"' in body
        assert b"text2music" in body
        return httpx.Response(
            200,
            json={
                "data": {"task_id": "task-ref", "status": "queued"},
                "code": 200,
                "error": None,
            },
        )

    with _client(handler) as client:
        assert (
            client.submit_instrumental(
                "organic percussion and distorted guitar",
                audio_path=source,
                mode="reference",
            )
            == "task-ref"
        )


def test_generate_downloads_completed_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / "generated.wav"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/release_task":
            return httpx.Response(
                200,
                json={
                    "data": {"task_id": "task-1", "status": "queued"},
                    "code": 200,
                    "error": None,
                },
            )
        if request.url.path == "/query_result":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "task_id": "task-1",
                            "status": 1,
                            "result": json.dumps(
                                [{"file": "/v1/audio?path=generated.wav", "status": 1}]
                            ),
                        }
                    ],
                    "code": 200,
                    "error": None,
                },
            )
        if request.url.path == "/v1/audio":
            return httpx.Response(200, content=b"generated-audio")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    monkeypatch.setattr("hazewave.acestep.time.sleep", lambda _: None)

    with _client(handler) as client:
        result = client.generate_instrumental(
            "instrumental rock",
            destination=destination,
            mode="text",
        )

    assert result.task_id == "task-1"
    assert destination.read_bytes() == b"generated-audio"


def test_cover_requires_audio() -> None:
    with _client(lambda _: httpx.Response(500)) as client:
        with pytest.raises(AceStepError, match="requires an audio file"):
            client.submit_instrumental("rock", mode="cover")
