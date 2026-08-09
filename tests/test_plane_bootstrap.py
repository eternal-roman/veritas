"""L1: plane bootstrap mints VAAT + issues visas."""

from __future__ import annotations

from veritas.agent_identity import PlaneIdentityIssuer
from veritas.agent_money import AgentMoneyLedger
from veritas.plane_bootstrap import DEFAULT_ROSTER, bootstrap


def test_bootstrap(tmp_path):
    out = bootstrap(tmp_path)
    assert out["not_x402_settlement"] is True
    assert out["visa_count"] == len(DEFAULT_ROSTER)
    led = AgentMoneyLedger(tmp_path / "agent_money.sqlite3")
    assert led.balance("money_loop") == 1000
    assert led.balance("overseer") == 1000
    led.verify_chain()
    led.close()
    issuer = PlaneIdentityIssuer(secret=tmp_path / "plane_identity.secret")
    import json

    visas = json.loads((tmp_path / "plane_visas.json").read_text(encoding="utf-8"))
    issuer.verify(visas["legal_identity"], expected_role="legal_identity")
