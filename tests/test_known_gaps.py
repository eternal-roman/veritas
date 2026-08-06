"""Witnesses for the gaps the constitution registers as open.

Each test here pins **current, defective behaviour**. That is deliberate: the
constitution's register may only carry an open gap if a test proves the gap is
real, so the register cannot rot into a list of things someone once believed.

When a gap is fixed the corresponding test starts failing. That is the signal to
close the gap in `veritas/constitution.py` and delete the witness — not to patch
the test.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_known_gap_settlements_are_never_checked_against_the_chain():
    """G9. The ledger records what the facilitator told us — including the
    entries where it told us nothing. No code re-checks any of it against an
    RPC endpoint, so `settled` means "we were told so", not "the chain
    agrees". An operator can state what this instance believes it earned, not
    what it holds.

    If this test fails, the gap has been fixed — close G9 and delete this test.
    """
    from veritas import ledger as ledger_module

    source = Path(ledger_module.__file__).read_text()
    assert "eth_getTransactionReceipt" not in source
    assert not hasattr(ledger_module.Ledger, "reconcile_against_chain")


def test_known_gap_free_traffic_moves_the_trust_score(tmp_path, monkeypatch):
    """G7 (defect T1). `/v1/trust` is derived from an outcome log that records
    every request including unpaid ones, and the endpoint is unauthenticated,
    so anyone can move the service's own reputation signal for free.

    If this test fails, the gap has been fixed — close G7 and delete this test.
    """
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)

    import veritas.server as server
    importlib.reload(server)
    client = TestClient(server.app)

    assert client.get("/v1/trust").json()["recommendation"] == "UNPROVEN"

    from veritas.trust import MIN_SAMPLES_FOR_SCORE
    for _ in range(MIN_SAMPLES_FOR_SCORE):
        client.post("/v1/research", json={"query": "What is x402?"})

    scored = client.get("/v1/trust").json()
    assert scored["recommendation"] != "UNPROVEN", (
        "free traffic no longer establishes a trust score"
    )
    assert scored["overall"] is not None
