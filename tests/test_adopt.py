"""Repo adopt card + enroll readiness a directed agent can execute."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from veritas.adopt import ADOPT_SCHEMA, build_adopt_card
from veritas.agent_account import enroll_account, whoami_document
from veritas.agent_cli import main

REPO = Path(__file__).resolve().parent.parent


def test_adopt_json_matches_builder():
    on_disk = json.loads((REPO / "adopt.json").read_text(encoding="utf-8"))
    built = build_adopt_card(public_url=None)
    assert on_disk == built
    assert built["schema"] == ADOPT_SCHEMA
    assert built["public_seller"] is None
    assert built["listed_on_registry"] is False
    assert built["funded_by_enroll"] is False


def test_whoami_readiness_unenrolled(tmp_path):
    doc = whoami_document(tmp_path)
    assert doc["enrolled"] is False
    ready = doc["readiness"]
    assert ready["listed_on_registry"] is False
    assert ready["funded"] is None
    assert "enroll" in ready["next"] or "adopt" in ready["next"]


def test_enroll_signs_ecosystem_identity_and_links_wallet(tmp_path):
    pytest.importorskip("eth_account")
    acc = enroll_account(tmp_path, agent_id="dana")
    addr = acc["wallets"]["commerce"]["address"]
    assert addr and addr.startswith("0x")
    card = acc["ecosystem_identity"]
    assert card["commerce_address"].lower() == addr.lower()
    assert card["did_pkh"].endswith(addr.lower())
    from veritas.agent_identity_card import verify_identity_card

    ok, reason = verify_identity_card(card)
    assert ok is True, reason
    who = whoami_document(tmp_path)
    assert who["readiness"]["ecosystem_identity_signed"] is True
    assert who["readiness"]["listed_on_registry"] is False
    assert who["readiness"]["funded"] is None


def test_adopt_cli_prints_workflow(tmp_path, capsys, monkeypatch):
    pytest.importorskip("eth_account")
    monkeypatch.chdir(tmp_path)
    assert main(["--base-dir", str(tmp_path), "adopt", "--id", "erin"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["enrolled"] is True
    assert out["agent_id"] == "erin"
    assert out["readiness"]["commerce_address"]
    assert out["readiness"]["funded"] is None


def test_adopt_route_and_well_known(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app)
    body = client.get("/adopt.json").json()
    assert body["schema"] == ADOPT_SCHEMA
    assert body["public_seller"] is None
    links = client.get("/.well-known/x402").json()["links"]
    assert links["adopt"] == "/adopt.json"
    assert client.get(links["adopt"]).status_code == 200
    identity = client.get("/v1/identity").json()
    assert identity["endpoints"]["adopt"].endswith("/adopt.json")
