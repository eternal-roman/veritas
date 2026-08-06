"""Witnesses for the gaps the constitution registers as open.

Each test here pins **current, defective behaviour**. That is deliberate: the
constitution's register may only carry an open gap if a test proves the gap is
real, so the register cannot rot into a list of things someone once believed.

When a gap is fixed the corresponding test starts failing. That is the signal to
close the gap in `veritas/constitution.py` and delete the witness — not to patch
the test.
"""

from __future__ import annotations

import base64
import importlib
import json

import pytest
from fastapi.testclient import TestClient

VALID_NONCE = "0x" + "ab" * 32


def _payment_header(nonce: str = VALID_NONCE) -> str:
    return base64.b64encode(json.dumps({
        "x402Version": 1,
        "scheme": "exact",
        "network": "eip155:84532",
        "payload": {
            "signature": "0x" + "cd" * 65,
            "authorization": {
                "from": "0x" + "1" * 40,
                "to": "0x" + "2" * 40,
                "value": "10000",
                "nonce": nonce,
            },
        },
    }).encode()).decode()


@pytest.fixture
def settling_client(tmp_path, monkeypatch):
    """A live-mode client whose facilitator always verifies and settles."""
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "1" * 40)
    monkeypatch.setenv("VERITAS_FACILITATOR", "https://facilitator.test")

    import veritas.server as server
    importlib.reload(server)

    from veritas.facilitator import SettlementResult, VerificationResult

    class _AlwaysSettles:
        def verify(self, payload, requirements):
            return VerificationResult(True, payer="0xbuyer")

        def settle(self, payload, requirements):
            return SettlementResult(
                True, transaction="0xdeadbeef", network=requirements.get("network"),
                payer="0xbuyer",
            )

    monkeypatch.setattr(server, "get_facilitator", lambda *a, **k: _AlwaysSettles())
    monkeypatch.setattr(
        server, "run_research",
        lambda query, max_results=5: __import__(
            "veritas.pipeline", fromlist=["run_research"]
        ).run_research(query, allow_network=False),
    )
    return server, TestClient(server.app)


def test_known_gap_completed_paid_request_is_not_replayable(settling_client):
    """G6 (defect R11). A buyer whose connection drops after settlement is
    charged and receives nothing: the nonce is burned, and retrying the same
    authorization returns 409 rather than the deliverable they paid for.

    If this test fails, the gap has been fixed — close G6 in
    veritas/constitution.py and delete this test.
    """
    _server, client = settling_client
    header = _payment_header()

    first = client.post("/v1/research", json={"query": "What is x402?"},
                        headers={"X-PAYMENT": header})
    assert first.status_code == 200, first.text

    # The buyer never received the body; they retry the identical authorization.
    second = client.post("/v1/research", json={"query": "What is x402?"},
                         headers={"X-PAYMENT": header})
    assert second.status_code == 409
    assert second.json()["error"] == "payment_nonce_already_spent"


def test_known_gap_no_settlement_record_is_written(settling_client, tmp_path):
    """G8 (defect R5). The settlement — including the on-chain transaction
    hash — exists only in the HTTP response. Nothing durable records what was
    earned, from whom, or for what, so revenue cannot be reconciled.

    If this test fails, the gap has been fixed — close G8 and delete this test.
    """
    _server, client = settling_client
    response = client.post("/v1/research", json={"query": "What is x402?"},
                           headers={"X-PAYMENT": _payment_header()})
    assert response.status_code == 200
    assert response.json()["payment"]["transaction"] == "0xdeadbeef"

    # The transaction hash appears nowhere on disk.
    on_disk = "".join(
        path.read_text(errors="ignore")
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert "0xdeadbeef" not in on_disk, "a settlement ledger now exists"


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
