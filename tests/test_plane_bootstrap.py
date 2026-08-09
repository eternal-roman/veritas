"""L1: plane bootstrap mints VAAT + issues visas."""

from __future__ import annotations

import json

import pytest

from veritas.agent_identity import PlaneIdentityIssuer, bootstrap_plane_roster
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
    visas = json.loads((tmp_path / "plane_visas.json").read_text(encoding="utf-8"))
    issuer.verify(visas["legal_identity"], expected_role="legal_identity")
    # All roster visas verify with same secret (no strip race)
    for agent_id, role in DEFAULT_ROSTER.items():
        issuer.verify(visas[agent_id], expected_role=role)


def test_bootstrap_legacy_binary_secret_no_strip(tmp_path):
    """Raw digest ending with whitespace byte must still verify (CI flake)."""
    raw = bytes([0xAB] * 31 + [0x0A])  # ends with newline byte
    secret_path = tmp_path / "plane_identity.secret"
    secret_path.write_bytes(raw)  # legacy binary form
    visas = bootstrap_plane_roster(
        {"legal_identity": "legal_identity"}, secret=raw
    )
    (tmp_path / "plane_visas.json").write_text(
        json.dumps(visas), encoding="utf-8"
    )
    issuer = PlaneIdentityIssuer(secret=secret_path)
    issuer.verify(visas["legal_identity"], expected_role="legal_identity")


@pytest.mark.parametrize("_i", range(20))
def test_bootstrap_verify_stable(_i, tmp_path):
    """Regression: repeated bootstrap must not flaky-fail signature verify."""
    out = bootstrap(tmp_path / f"b{_i}")
    assert out["visa_count"] == len(DEFAULT_ROSTER)
    path = tmp_path / f"b{_i}"
    issuer = PlaneIdentityIssuer(secret=path / "plane_identity.secret")
    visas = json.loads((path / "plane_visas.json").read_text(encoding="utf-8"))
    issuer.verify(visas["overseer"], expected_role="overseer")
