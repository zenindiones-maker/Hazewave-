from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import httpx

from hazewave.freellmapi import (
    FreeLLMAPIClient,
    FreeLLMAPILocalCatalog,
    build_free_fabric_inventory,
    build_free_fabric_eligibility_report,
    run_live_probe,
)


def _db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE api_keys (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          encrypted_key TEXT,
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
        INSERT INTO api_keys(id,platform,encrypted_key,enabled,status)
          VALUES(1,'kilo','TOP_SECRET_CIPHERTEXT',1,'healthy');
        INSERT INTO models(
          id,platform,model_id,display_name,intelligence_rank,speed_rank,
          context_window,enabled,supports_vision,supports_tools,key_id
        ) VALUES(1,'kilo','dots-free','Dots Free',1,1,65536,1,0,1,NULL);
        INSERT INTO media_models(
          id,platform,model_id,display_name,modality,priority,enabled,quota_label,key_id,meta_json
        ) VALUES(1,'pollinations','image-free','Image Free','image',1,1,'',NULL,NULL);
        """
    )
    con.commit()
    con.close()


def test_inventory_is_secret_free_and_reports_runtime_surface(tmp_path: Path) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db)

    inventory = build_free_fabric_inventory(catalog=FreeLLMAPILocalCatalog(db))
    serialized = json.dumps(inventory, sort_keys=True)

    assert inventory["schema"] == "HazewaveFreeFabricInventory/v1"
    assert inventory["authority"] == "HAZEWAVE_HARNESS"
    assert inventory["provider_gateway_authority"] == "NONE"
    assert inventory["counts"]["chat_routable"] == 1
    assert inventory["counts"]["image_routable"] == 1
    assert "TOP_SECRET_CIPHERTEXT" not in serialized


def test_eligibility_report_only_exposes_zero_cost_governed_routes(tmp_path: Path) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db)

    report = build_free_fabric_eligibility_report(
        catalog=FreeLLMAPILocalCatalog(db),
        data_classification="PUBLIC",
    )

    assert report["schema"] == "HazewaveFreeFabricEligibilityReport/v1"
    assert report["paid_fallback"] == "FORBIDDEN"
    assert report["unknown_cost"] == "DENY"
    assert report["surfaces"]["text"]["models"] == ["kilo:dots-free"]
    assert report["surfaces"]["image"]["models"] == ["pollinations:image-free"]
    assert report["surfaces"]["video"]["models"] == []
    assert report["surfaces"]["credential_egress"] == "DENY"


def test_live_probe_uses_governed_provider_qualified_route(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "freellmapi.db"
    _db(db)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "kilo:dots-free"
        assert payload["model"] != "auto"
        return httpx.Response(
            200,
            headers={"X-Routed-Via": "kilo/dots-free"},
            json={
                "id": "probe",
                "model": "dots-free",
                "choices": [{"message": {"role": "assistant", "content": "Stable pulse."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7, "cost": 0},
            },
        )

    fake = FreeLLMAPIClient("http://127.0.0.1:3001/v1", api_key="router-secret")
    fake._client.close()
    fake._client = httpx.Client(
        base_url="http://127.0.0.1:3001/v1",
        headers={"Authorization": "Bearer router-secret"},
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr("hazewave.freellmapi.FreeLLMAPIClient", lambda *a, **k: fake)

    receipt = run_live_probe(
        api_key="router-secret",
        task_id="governed-live-proof",
        catalog=FreeLLMAPILocalCatalog(db),
    )
    fake.close()

    assert receipt["schema"] == "HazewaveProviderProbeReceipt/v2"
    assert receipt["provider"] == "kilo"
    assert receipt["requested_model"] == "kilo:dots-free"
    assert receipt["zero_cost_verified"] is True
    assert receipt["usage"]["cost"] == 0
    assert "router-secret" not in json.dumps(receipt, sort_keys=True)


def test_control_doctor_declares_governed_zero_cost_invariants() -> None:
    root = Path(__file__).resolve().parents[1]
    control = (root / "scripts" / "hazewave_freellmapi_control.sh").read_text(
        encoding="utf-8"
    )

    assert "HAZEWAVE_FREE_FABRIC=ENFORCED" in control
    assert "HAZEWAVE_FREE_FABRIC_ZERO_COST_GUARD=ENFORCED" in control
    assert "HAZEWAVE_FREE_FABRIC_PAID_FALLBACK=FORBIDDEN" in control
    assert "HAZEWAVE_FREE_FABRIC_UNKNOWN_COST=DENY" in control
    assert "HAZEWAVE_FREE_FABRIC_PRIVATE_MEDIA_DEFAULT_EGRESS=DENY" in control
    assert "HAZEWAVE_FREE_FABRIC_UNREVIEWED_PROVIDER=QUARANTINED" in control
