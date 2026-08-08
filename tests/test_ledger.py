"""The financial ledger: what was authorized, what was delivered, what settled.

Three audited defects motivate this module, and each has a test here that
failed before it existed:

* R5 / gap G8 — the settlement, including the on-chain transaction hash, lived
  only in the HTTP response. Nothing durable recorded what was earned, from
  whom, or for what, so revenue could not be reconciled and a disputed charge
  could not be answered.
* R11 / gap G6 — a nonce was burned before the work and never joined to a
  delivery, so a buyer whose connection dropped after settlement was charged
  and got a 409 on retry. The state machine here makes the paid request
  idempotent: a replay returns the deliverable that was paid for.
* R7 — a settlement whose facilitator never answered was recorded as a
  failure. "We do not know" is not "it did not happen"; conflating them
  understates revenue and overstates certainty in both directions.
* R6 — the nonce claim accepted a `request_id` that no caller ever passed, so
  a burned authorization could not be joined to the request that burned it.
"""

from __future__ import annotations

import pytest

from veritas.ledger import Ledger, NonceState

NONCE = "0x" + "ab" * 32
OTHER_NONCE = "0x" + "cd" * 32

OFFER = {
    "network": "eip155:84532",
    "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "amount": "10000",
    "pay_to": "0x" + "11" * 20,
    "price": "$0.01",
    "payer": "0x" + "22" * 20,
}


def _delivered(ledger: Ledger, request_id: str = "req-1", nonce: str = NONCE):
    ledger.claim(nonce, request_id, **OFFER)
    ledger.record_delivery(
        request_id,
        status="completed",
        billable=True,
        custody_root="sha256:root",
        query="What is x402?",
        response={"request_id": request_id, "status": "completed"},
    )
    return request_id


# -- claiming ---------------------------------------------------------------


def test_claim_records_the_request_id_it_burned_the_nonce_for(tmp_path):
    """R6. The claim accepted a request_id no caller passed; a burned
    authorization has to be joinable to the request that burned it."""
    ledger = Ledger(tmp_path)
    assert ledger.claim(NONCE, "req-1", **OFFER).claimed
    auth = ledger.authorization(NONCE)
    assert auth.request_id == "req-1"
    assert auth.state == NonceState.CLAIMED
    assert auth.amount == "10000"
    assert auth.network == "eip155:84532"


def test_second_claim_is_refused_and_names_the_state_it_found(tmp_path):
    """Refusal alone is not enough: the caller decides between replaying a
    paid deliverable and rejecting a duplicate by what state it is in."""
    ledger = Ledger(tmp_path)
    assert ledger.claim(NONCE, "req-1", **OFFER).claimed
    second = ledger.claim(NONCE, "req-2", **OFFER)
    assert second.claimed is False
    assert second.reason == "payment_nonce_already_spent"
    assert second.existing.state == NonceState.CLAIMED
    assert second.existing.request_id == "req-1"


def test_distinct_nonces_both_claim(tmp_path):
    ledger = Ledger(tmp_path)
    assert ledger.claim(NONCE, "req-1", **OFFER).claimed
    assert ledger.claim(OTHER_NONCE, "req-2", **OFFER).claimed


def test_claims_survive_restart(tmp_path):
    """A crash-loop must not become a way to replay paid work."""
    assert Ledger(tmp_path).claim(NONCE, "req-1", **OFFER).claimed
    assert Ledger(tmp_path).claim(NONCE, "req-2", **OFFER).claimed is False


def test_casing_cannot_evade_the_guard(tmp_path):
    ledger = Ledger(tmp_path)
    assert ledger.claim(NONCE, "req-1", **OFFER).claimed
    assert ledger.claim("0x" + "AB" * 32, "req-2", **OFFER).claimed is False


def test_missing_and_malformed_nonces_are_named(tmp_path):
    ledger = Ledger(tmp_path)
    assert ledger.claim(None, "req-1").reason == "payment_nonce_missing"
    assert ledger.claim("0xzz", "req-1").reason == "payment_nonce_malformed"


def test_unusable_store_fails_closed(tmp_path):
    """An unavailable ledger must not silently become no ledger."""
    blocked = tmp_path / "blocked"
    blocked.write_text("a regular file where the ledger directory should be")
    result = Ledger(blocked).claim(NONCE, "req-1", **OFFER)
    assert result.claimed is False
    assert result.reason == "replay_store_unavailable"


def test_failure_reason_carries_no_server_paths(tmp_path):
    """The reason reaches external buyers in a 503 detail; the sqlite error
    text names server filesystem paths."""
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    reason = Ledger(blocked).claim(NONCE, "req-1", **OFFER).reason
    assert "/" not in reason and "\\" not in reason


# -- delivery ---------------------------------------------------------------


def test_delivery_is_durable_and_recoverable(tmp_path):
    """G8/R11. What we delivered has to outlive the response, or a buyer who
    never received it has no way to be made whole."""
    ledger = Ledger(tmp_path)
    _delivered(ledger)
    reopened = Ledger(tmp_path)
    assert reopened.authorization(NONCE).state == NonceState.DELIVERED
    assert reopened.deliverable("req-1")["status"] == "completed"


def test_non_billable_work_abandons_the_authorization(tmp_path):
    """Retrieval failure is ours. Nothing is owed, so nothing may settle."""
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    ledger.record_delivery(
        "req-1", status="unavailable", billable=False, custody_root="sha256:r",
        query="q", response={"status": "unavailable"},
    )
    assert ledger.authorization(NONCE).state == NonceState.ABANDONED


def test_delivery_without_a_claim_is_refused(tmp_path):
    """The paid path claims before it works; a delivery with no authorization
    behind it would be revenue attributed to nobody."""
    ledger = Ledger(tmp_path)
    assert ledger.record_delivery(
        "req-unknown", status="completed", billable=True,
        custody_root="sha256:r", query="q", response={},
    ) is False


# -- settlement -------------------------------------------------------------


def test_settlement_records_the_transaction_hash(tmp_path):
    """G8/R5. The tx hash was base64'd into a response header and discarded."""
    ledger = Ledger(tmp_path)
    _delivered(ledger)
    ledger.record_settlement(
        "req-1", outcome="settled", transaction="0xdeadbeef",
        network="eip155:84532", payer=OFFER["payer"],
    )
    reopened = Ledger(tmp_path)
    assert reopened.authorization(NONCE).state == NonceState.SETTLED
    entries = reopened.settlements("req-1")
    assert [e["transaction"] for e in entries] == ["0xdeadbeef"]
    assert entries[0]["amount"] == "10000"
    assert entries[0]["asset"] == OFFER["asset"]


def test_indeterminate_settlement_is_not_recorded_as_failure(tmp_path):
    """R7/M4. A facilitator that never answered leaves the outcome unknown.
    Recording that as a failure understates revenue and asserts a fact about
    the chain we did not observe."""
    ledger = Ledger(tmp_path)
    _delivered(ledger)
    ledger.record_settlement("req-1", outcome="indeterminate", reason="facilitator_timeout")
    auth = ledger.authorization(NONCE)
    assert auth.state == NonceState.INDETERMINATE
    assert auth.state != NonceState.SETTLEMENT_FAILED
    assert ledger.summary()["indeterminate_count"] == 1
    assert ledger.summary()["failed_count"] == 0


def test_definite_settlement_failure_is_recorded_as_failure(tmp_path):
    ledger = Ledger(tmp_path)
    _delivered(ledger)
    ledger.record_settlement("req-1", outcome="failed", reason="insufficient_funds")
    assert ledger.authorization(NONCE).state == NonceState.SETTLEMENT_FAILED
    assert ledger.summary()["failed_count"] == 1


def test_settlement_attempts_are_append_only(tmp_path):
    """An indeterminate attempt later resolved is two facts, not one
    overwritten one; reconciliation needs both."""
    ledger = Ledger(tmp_path)
    _delivered(ledger)
    ledger.record_settlement("req-1", outcome="indeterminate", reason="facilitator_timeout")
    ledger.record_settlement("req-1", outcome="settled", transaction="0xabc")
    outcomes = [e["outcome"] for e in ledger.settlements("req-1")]
    assert outcomes == ["indeterminate", "settled"]
    assert ledger.authorization(NONCE).state == NonceState.SETTLED


def test_settlement_of_an_abandoned_authorization_is_refused(tmp_path):
    """Never bill for our own failure — enforced by the store, not only by
    the caller that is supposed to skip settle."""
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    ledger.record_delivery(
        "req-1", status="unavailable", billable=False, custody_root="sha256:r",
        query="q", response={},
    )
    with pytest.raises(ValueError):
        ledger.record_settlement("req-1", outcome="settled", transaction="0xdeadbeef")


def test_settlement_before_delivery_is_refused(tmp_path):
    """Verify payment before work, settle after. Settling a request we have
    not delivered would charge for undeliverable work."""
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    with pytest.raises(ValueError):
        ledger.record_settlement("req-1", outcome="settled", transaction="0xdeadbeef")


# -- reconciliation ---------------------------------------------------------


def test_summary_reconciles_delivered_against_settled(tmp_path):
    """G8's acceptance: revenue is answerable from the ledger alone."""
    ledger = Ledger(tmp_path)
    _delivered(ledger, "req-1", NONCE)
    ledger.record_settlement("req-1", outcome="settled", transaction="0xaaa")
    _delivered(ledger, "req-2", OTHER_NONCE)

    summary = ledger.summary()
    assert summary["deliveries"] == 2
    assert summary["billable_deliveries"] == 2
    assert summary["settled_count"] == 1
    assert summary["settled_amounts"] == {"eip155:84532/" + OFFER["asset"]: "10000"}
    assert summary["unsettled_count"] == 1


def test_awaiting_settlement_lists_what_is_owed(tmp_path):
    """The operator's question after a crash: what did we deliver and never
    get paid for?"""
    ledger = Ledger(tmp_path)
    _delivered(ledger, "req-1", NONCE)
    _delivered(ledger, "req-2", OTHER_NONCE)
    ledger.record_settlement("req-1", outcome="settled", transaction="0xaaa")
    owed = ledger.awaiting_settlement()
    assert [a.request_id for a in owed] == ["req-2"]


def test_settled_amounts_sum_atomic_units_not_floats(tmp_path):
    """Money is integer atomic units. Float accumulation is a rounding bug
    waiting for volume."""
    ledger = Ledger(tmp_path)
    for i, nonce in enumerate((NONCE, OTHER_NONCE)):
        rid = f"req-{i}"
        ledger.claim(nonce, rid, **{**OFFER, "amount": "1"})
        ledger.record_delivery(rid, status="completed", billable=True,
                               custody_root="sha256:r", query="q", response={})
        ledger.record_settlement(rid, outcome="settled", transaction=f"0x{i}")
    key = "eip155:84532/" + OFFER["asset"]
    assert ledger.summary()["settled_amounts"][key] == "2"
