"""L1: agent identity + limited VAAT wallet + quality compensation."""

from __future__ import annotations

import pytest

from veritas.agent_economy import (
    AgentEconomy,
    QualityError,
    bootstrap_economy,
    pay_for_quality,
)
from veritas.agent_money import SupplyExhausted


def test_pay_for_quality_table():
    assert pay_for_quality(0) == 0
    assert pay_for_quality(1) == 25
    assert pay_for_quality(2) == 50
    assert pay_for_quality(3) == 100
    with pytest.raises(QualityError):
        pay_for_quality(4)


def test_ensure_agent_identity_and_wallet(tmp_path):
    eco = AgentEconomy(tmp_path)
    acc = eco.ensure_agent("steward", "steward", stipend=100)
    assert acc.balance_vaat == 100
    assert acc.did == "did:veritas:plane:steward"
    assert acc.plane_id.startswith("spiffe://veritas.local/")
    assert acc.visa["agent_id"] == "steward"
    eco.issuer.verify(acc.visa, expected_role="steward")
    eco.close()


def test_quality_compensation_and_effort_journal(tmp_path):
    eco = AgentEconomy(tmp_path)
    eco.ensure_agent("pruner", "pruner", stipend=0)
    r0 = eco.compensate(
        "pruner", 0, effort_kind="noop_idle", evidence="free HOLD"
    )
    assert r0["pay_vaat"] == 0
    assert eco.ledger.balance("pruner") == 0
    r3 = eco.compensate(
        "pruner",
        3,
        effort_kind="ship_ok_veto",
        evidence="battery green + delete bloat",
    )
    assert r3["pay_vaat"] == 100
    assert eco.ledger.balance("pruner") == 100
    hist = eco.effort_history("pruner")
    assert len(hist) == 2
    assert hist[1]["quality"] == 3
    eco.ledger.verify_chain()
    eco.close()


def test_limited_supply_blocks_mint(tmp_path):
    eco = AgentEconomy(tmp_path, max_supply=50)
    eco.ensure_agent("a", "role_a", stipend=40)
    with pytest.raises(SupplyExhausted):
        eco.ensure_agent("b", "role_b", stipend=20)
    eco.close()


def test_bootstrap_full_roster(tmp_path):
    out = bootstrap_economy(tmp_path, stipend=10)
    assert out["not_x402_settlement"] is True
    assert out["money"]["limited_supply"] is True
    assert out["money"]["max_supply"] >= out["money"]["total_minted"]
    assert len(out["accounts"]) >= 10
    ids = {a["agent_id"] for a in out["accounts"]}
    assert "overseer" in ids and "unblock" in ids and "architect" in ids
