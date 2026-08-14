"""L1: one local account binds identity, wallets, and interest-derived skills."""

from __future__ import annotations

import json

import pytest

from veritas.agent_account import (
    ACCOUNT_SCHEMA,
    SKILL_CATALOG,
    enroll_account,
    load_account,
    whoami_document,
)
from veritas.agent_cli import main
from veritas.hashing import compute_content_hash


def test_enroll_binds_identity_wallet_and_default_skills(tmp_path):
    acc = enroll_account(tmp_path, agent_id="alice")
    assert acc["schema"] == ACCOUNT_SCHEMA
    assert acc["agent_id"] == "alice"
    assert acc["did"] == "did:veritas:plane:alice"
    assert acc["plane_id"].startswith("spiffe://veritas.local/")
    assert [s["id"] for s in acc["skills"]] == ["research", "verify"]
    assert all(s["mapped"] for s in acc["skills"])
    assert acc["wallets"]["plane"]["not_x402_settlement"] is True
    assert acc["binding_hash"]
    assert load_account(tmp_path)["binding_hash"] == acc["binding_hash"]


def test_interests_map_aliases_and_record_unknown(tmp_path):
    acc = enroll_account(
        tmp_path,
        agent_id="bob",
        interests="search,vet,knitting,buy",
    )
    ids = [s["id"] for s in acc["skills"]]
    assert ids == ["research", "diligence", "knitting", "buy"]
    by_id = {s["id"]: s for s in acc["skills"]}
    assert by_id["research"]["mapped"] is True
    assert by_id["diligence"]["command"] == "veritas-diligence"
    assert by_id["knitting"]["mapped"] is False
    assert "recorded as interest only" in by_id["knitting"]["note"]


def test_skill_binding_hash_covers_identity_and_wallet(tmp_path):
    acc = enroll_account(
        tmp_path, agent_id="carol", commerce_address="0x" + "ab" * 20
    )
    skill = acc["skills"][0]
    expect = compute_content_hash(
        json.dumps(
            {
                "agent_id": "carol",
                "did": acc["did"],
                "commerce_address": "0x" + "ab" * 20,
                "skill_id": skill["id"],
            },
            sort_keys=True,
        )
    )
    assert skill["binding_hash"] == expect


def test_whoami_unenrolled(tmp_path):
    doc = whoami_document(tmp_path)
    assert doc["enrolled"] is False
    assert "enroll" in doc["next"]
    assert set(doc["catalog"]) == set(SKILL_CATALOG)


def test_enroll_cli_and_whoami(tmp_path, capsys):
    assert main(["--base-dir", str(tmp_path), "enroll", "--id", "dana",
                 "--interests", "research,sell"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["agent_id"] == "dana"
    assert {s["id"] for s in out["skills"]} == {"research", "sell"}
    assert main(["--base-dir", str(tmp_path), "whoami"]) == 0
    who = json.loads(capsys.readouterr().out)
    assert who["enrolled"] is True
    assert who["did"] == out["did"]
    assert main(["--base-dir", str(tmp_path), "skills"]) == 0
    skills = json.loads(capsys.readouterr().out)
    assert skills["enrolled"] is True
    assert skills["binding_hash"] == out["binding_hash"]


def test_init_auto_enrolls_default_account(tmp_path, capsys):
    pytest.importorskip("eth_account")
    assert main(["--base-dir", str(tmp_path / ".veritas_agent"), "init"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["account"]["agent_id"] == "self"
    assert "research" in payload["account"]["skills"]
    home = tmp_path / ".veritas_agent"
    # main(["init"]) uses default .veritas_agent relative to cwd (tmp_path via fixture?)
    # This test passes --base-dir explicitly.
    acc = load_account(home)
    assert acc is not None
    assert acc["wallets"]["commerce"]["address"]
    assert acc["wallets"]["commerce"]["address"].startswith("0x")
