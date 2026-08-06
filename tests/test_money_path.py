"""The paid request end to end: claim, work, record, settle, replay.

This file pins the ordering and the idempotency that gaps G6 and G8 were
witnesses for. The old path claimed a nonce, did the work, settled, and kept
no record of any of it — so a buyer whose connection dropped after settlement
was charged, received nothing, and got a 409 on retry, while the transaction
hash that proved they had paid existed only in the response they never saw.
"""

from __future__ import annotations

import base64
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from veritas.facilitator import SettlementResult, VerificationResult
from veritas.ledger import NonceState

NONCE = "0x" + "ab" * 32
OTHER_NONCE = "0x" + "cd" * 32


def _header(nonce: str = NONCE) -> str:
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


class _Control:
    """Test-controlled facilitator plus a counter for retrieval passes."""

    def __init__(self):
        self.settle_result = SettlementResult(
            True, transaction="0xdeadbeef", network="eip155:84532", payer="0xbuyer",
        )
        self.work_calls = 0
        self.owed_at_settle_time: list[str] = []
        self.ledger = None

    def verify(self, payload, requirements):
        return VerificationResult(True, payer="0xbuyer")

    def settle(self, payload, requirements):
        # Snapshot what the ledger already knows at the moment settlement is
        # attempted: the delivery must already be durable by now.
        self.owed_at_settle_time = [a.request_id for a in self.ledger.awaiting_settlement()]
        return self.settle_result


@pytest.fixture
def money_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "11" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")
    monkeypatch.setenv("VERITAS_FACILITATOR", "https://facilitator.test")

    import veritas.server as server
    importlib.reload(server)

    control = _Control()
    control.ledger = server.ledger
    monkeypatch.setattr(server, "get_facilitator", lambda *a, **k: control)

    real_run = server.run_research

    def counting_run(query, **kwargs):
        control.work_calls += 1
        return real_run(query, allow_network=False, **kwargs)

    monkeypatch.setattr(server, "run_research", counting_run)
    return server, TestClient(server.app), control


BODY = {"query": "What is the x402 payment protocol?"}


# -- the happy path records itself ------------------------------------------


def test_settlement_is_recorded_durably(money_client):
    """G8/R5. The transaction hash used to exist only in the response."""
    server, client, _control = money_client
    response = client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    assert response.status_code == 200, response.text
    request_id = response.json()["request_id"]

    entries = server.ledger.settlements(request_id)
    assert [e["transaction"] for e in entries] == ["0xdeadbeef"]
    assert entries[0]["amount"] == "10000"
    assert server.ledger.authorization(NONCE).state == NonceState.SETTLED


def test_revenue_is_answerable_from_the_ledger_alone(money_client):
    server, client, _control = money_client
    for nonce in (NONCE, OTHER_NONCE):
        assert client.post("/v1/research", json=BODY,
                           headers={"X-PAYMENT": _header(nonce)}).status_code == 200
    summary = server.ledger.summary()
    assert summary["settled_count"] == 2
    assert summary["unsettled_count"] == 0
    assert list(summary["settled_amounts"].values()) == ["20000"]


def test_the_nonce_is_joined_to_the_request_it_burned_for(money_client):
    """R6. `claim` accepted a request_id no caller ever passed."""
    server, client, _control = money_client
    response = client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    assert server.ledger.authorization(NONCE).request_id == response.json()["request_id"]


def test_delivery_is_durable_before_settlement_is_attempted(money_client):
    """A crash between the two must leave a record that we owe the buyer,
    not silence. The facilitator stub reads the ledger as it is called."""
    _server, client, control = money_client
    response = client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    assert control.owed_at_settle_time == [response.json()["request_id"]]


# -- replay: the G6 fix -----------------------------------------------------


def test_replayed_authorization_returns_the_deliverable_it_paid_for(money_client):
    """G6/R11. The buyer's connection dropped; they retry the only
    authorization they have. Previously: 409, charged, nothing delivered."""
    _server, client, control = money_client
    headers = {"X-PAYMENT": _header()}

    first = client.post("/v1/research", json=BODY, headers=headers)
    assert first.status_code == 200

    second = client.post("/v1/research", json=BODY, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["request_id"] == first.json()["request_id"]
    assert second.json()["claims"] == first.json()["claims"]
    assert second.json()["payment"]["replayed"] is True
    assert second.json()["payment"]["transaction"] == "0xdeadbeef"


def test_a_replay_does_not_run_the_work_again(money_client):
    """Roadmap 0.4's acceptance criterion, unchanged by the G6 fix: the
    retrieval pass we are not paid twice for must not run twice."""
    _server, client, control = money_client
    headers = {"X-PAYMENT": _header()}
    client.post("/v1/research", json=BODY, headers=headers)
    client.post("/v1/research", json=BODY, headers=headers)
    assert control.work_calls == 1


def test_a_replay_does_not_settle_again(money_client):
    """The authorization is single-use on chain; a second settle would be a
    second facilitator call for money that already moved."""
    server, client, _control = money_client
    headers = {"X-PAYMENT": _header()}
    request_id = client.post("/v1/research", json=BODY, headers=headers).json()["request_id"]
    client.post("/v1/research", json=BODY, headers=headers)
    assert len(server.ledger.settlements(request_id)) == 1


def test_a_fresh_nonce_still_works_after_a_replay(money_client):
    _server, client, control = money_client
    client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    third = client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header(OTHER_NONCE)})
    assert third.status_code == 200
    assert control.work_calls == 2


# -- settlement outcomes ----------------------------------------------------


def test_indeterminate_settlement_delivers_and_says_so(money_client):
    """R7/M4. The facilitator never answered, so the funds may have moved.
    Withholding the work is the one outcome that is certainly wrong."""
    server, client, control = money_client
    control.settle_result = SettlementResult(False, error_reason="facilitator_timeout")

    response = client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    assert response.status_code == 200, response.text
    payment = response.json()["payment"]
    assert payment["settled"] is False
    assert payment["state"] == "indeterminate"
    assert response.json()["claims"], "the deliverable must still be delivered"
    assert server.ledger.authorization(NONCE).state == NonceState.INDETERMINATE


def test_indeterminate_settlement_is_visible_as_exposure(money_client):
    server, client, control = money_client
    control.settle_result = SettlementResult(False, error_reason="facilitator_bad_response")
    client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    summary = server.ledger.summary()
    assert summary["indeterminate_count"] == 1
    assert summary["failed_count"] == 0
    assert summary["settled_amounts"] == {}


def test_definite_settlement_failure_returns_402_and_is_recorded(money_client):
    """The facilitator answered: the payment did not settle. The buyer is not
    charged and does not get the work."""
    server, client, control = money_client
    control.settle_result = SettlementResult(False, error_reason="insufficient_funds")

    response = client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    assert response.status_code == 402
    assert response.json()["error"] == "settlement_failed"
    assert server.ledger.authorization(NONCE).state == NonceState.SETTLEMENT_FAILED
    assert server.ledger.summary()["failed_count"] == 1


def test_a_failed_settlement_can_be_retried_and_is_appended(money_client):
    """A buyer who tops up and retries the same authorization must not be
    told the nonce is spent — nothing settled, so nothing was spent."""
    server, client, control = money_client
    headers = {"X-PAYMENT": _header()}
    control.settle_result = SettlementResult(False, error_reason="insufficient_funds")
    assert client.post("/v1/research", json=BODY, headers=headers).status_code == 402

    control.settle_result = SettlementResult(True, transaction="0xlater")
    second = client.post("/v1/research", json=BODY, headers=headers)
    assert second.status_code == 200, second.text
    request_id = second.json()["request_id"]
    assert [e["outcome"] for e in server.ledger.settlements(request_id)] == [
        "failed", "settled",
    ]
    assert control.work_calls == 1, "the retry must reuse the stored deliverable"


# -- our own failures are never billed --------------------------------------


def test_retrieval_failure_abandons_the_authorization_and_never_settles(money_client):
    """Invariant 3: never bill for our own failure. The ledger enforces it
    rather than trusting the handler to skip the settle call."""
    server, client, control = money_client

    class _Broken:
        name = "broken"

        def retrieve(self, query, max_results=5):
            raise ConnectionError("simulated outage")

    from veritas.pipeline import run_research as real

    def failing(query, **kwargs):
        control.work_calls += 1
        return real(query, retriever=_Broken(), **{k: v for k, v in kwargs.items()
                                                   if k != "allow_network"})

    server.run_research = failing
    response = client.post("/v1/research", json=BODY, headers={"X-PAYMENT": _header()})
    assert response.status_code == 503
    assert response.json()["billable"] is False
    assert server.ledger.authorization(NONCE).state == NonceState.ABANDONED
    assert server.ledger.settlements(response.json()["request_id"]) == []


def test_free_mode_writes_nothing_to_the_financial_ledger(tmp_path, monkeypatch):
    """The ledger is a record of revenue. Unpaid traffic is not revenue, and
    padding it with free requests would make every report a lie by omission."""
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as server
    importlib.reload(server)

    from veritas.pipeline import run_research as real
    monkeypatch.setattr(
        server, "run_research", lambda query, **kw: real(query, allow_network=False, **kw)
    )
    client = TestClient(server.app)
    assert client.post("/v1/research", json=BODY).status_code == 200
    assert server.ledger.summary()["deliveries"] == 0
