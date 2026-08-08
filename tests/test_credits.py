"""M7.1 CreditLedger: double-entry topup/grant/debit/refund in atomic units.

PROPERTY: balance is the sum of signed journal entries; debit refuses when
balance is insufficient; refund requires a prior debit and never exceeds it;
debit and refund are idempotent per (account, request_id).

EVIDENCE LEVEL: L1 (these cases). NOT PROVEN: multi-instance shared store;
on-chain funding of topups (settlement is outside this module).
"""

from __future__ import annotations

import pytest

from veritas.credits import (
    CreditError,
    CreditKind,
    CreditLedger,
    InsufficientCredits,
    RefundNotAllowed,
    normalize_account,
)

ADDR = "0xAbcDef0123456789AbcDef0123456789AbcDef01"
ADDR_FOLD = "0xabcdef0123456789abcdef0123456789abcdef01"
OTHER = "0x" + "22" * 20


def test_normalize_folds_case():
    assert normalize_account(ADDR) == ADDR_FOLD


def test_normalize_rejects_empty():
    with pytest.raises(CreditError):
        normalize_account("")
    with pytest.raises(CreditError):
        normalize_account("   ")


def test_grant_and_topup_are_positive_atomic_entries(tmp_path):
    ledger = CreditLedger(tmp_path)
    g = ledger.grant(ADDR, 10_000, note="test_grant")
    assert g.kind == CreditKind.GRANT.value
    assert g.amount == 10_000
    t = ledger.topup(ADDR, 2_500, request_id="top-1", note="settled_x402")
    assert t.kind == CreditKind.TOPUP.value
    assert t.amount == 2_500
    assert t.request_id == "top-1"
    assert ledger.balance(ADDR) == 12_500
    assert ledger.balance(ADDR_FOLD) == 12_500  # case-fold identity
    ledger.close()


def test_grant_via_topup_kind(tmp_path):
    ledger = CreditLedger(tmp_path)
    e = ledger.grant(ADDR, 100, kind=CreditKind.TOPUP, note="post_settle")
    assert e.kind == CreditKind.TOPUP.value
    assert ledger.balance(ADDR) == 100
    ledger.close()


def test_debit_subtracts_and_writes_negative_journal(tmp_path):
    ledger = CreditLedger(tmp_path)
    ledger.grant(ADDR, 10_000, note="test_grant")
    d = ledger.debit(ADDR, 3_000, request_id="r1")
    assert d.kind == CreditKind.DEBIT.value
    assert d.amount == -3_000
    assert d.request_id == "r1"
    assert ledger.balance(ADDR) == 7_000
    kinds = {e.kind: e.amount for e in ledger.entries(ADDR)}
    assert kinds[CreditKind.DEBIT.value] == -3_000
    assert kinds[CreditKind.GRANT.value] == 10_000
    ledger.close()


def test_debit_insufficient_fails_closed(tmp_path):
    ledger = CreditLedger(tmp_path)
    ledger.grant(ADDR, 100)
    with pytest.raises(InsufficientCredits):
        ledger.debit(ADDR, 101, request_id="r-over")
    assert ledger.balance(ADDR) == 100
    # zero balance, any positive debit refuses
    ledger.debit(ADDR, 100, request_id="drain")
    with pytest.raises(InsufficientCredits):
        ledger.debit(ADDR, 1, request_id="r-empty")
    assert ledger.balance(ADDR) == 0
    ledger.close()


def test_debit_idempotent_per_request_id(tmp_path):
    ledger = CreditLedger(tmp_path)
    ledger.grant(ADDR, 10_000)
    e1 = ledger.debit(ADDR, 4_000, request_id="same")
    e2 = ledger.debit(ADDR, 4_000, request_id="same")
    assert e1.id == e2.id
    assert ledger.balance(ADDR) == 6_000
    # retry after balance would not cover a *new* debit of the same amount
    ledger.debit(ADDR, 6_000, request_id="drain")
    assert ledger.balance(ADDR) == 0
    e3 = ledger.debit(ADDR, 4_000, request_id="same")
    assert e3.id == e1.id
    assert ledger.balance(ADDR) == 0
    ledger.close()


def test_debit_idempotent_ignores_retry_amount(tmp_path):
    """A resubmitted request_id returns the original debit; no second spend."""
    ledger = CreditLedger(tmp_path)
    ledger.grant(ADDR, 10_000)
    e1 = ledger.debit(ADDR, 1_000, request_id="req-a")
    e2 = ledger.debit(ADDR, 9_999, request_id="req-a")
    assert e1.id == e2.id
    assert e2.amount == -1_000
    assert ledger.balance(ADDR) == 9_000
    ledger.close()


def test_refund_restores_full_debit_once(tmp_path):
    ledger = CreditLedger(tmp_path)
    ledger.topup(ADDR, 5_000, request_id="top1")
    ledger.debit(ADDR, 5_000, request_id="research-1")
    assert ledger.balance(ADDR) == 0
    r1 = ledger.refund(ADDR, request_id="research-1", note="refund_unavailable")
    assert r1.kind == CreditKind.REFUND.value
    assert r1.amount == 5_000
    assert ledger.balance(ADDR) == 5_000
    r2 = ledger.refund(ADDR, request_id="research-1")
    assert r2.id == r1.id
    assert ledger.balance(ADDR) == 5_000
    ledger.close()


def test_refund_without_debit_refuses(tmp_path):
    ledger = CreditLedger(tmp_path)
    ledger.grant(ADDR, 1)
    with pytest.raises(RefundNotAllowed):
        ledger.refund(ADDR, request_id="never-debited")
    assert ledger.balance(ADDR) == 1
    ledger.close()


def test_refund_never_exceeds_prior_debit(tmp_path):
    """Refund amount is exactly abs(debit); a second refund is a no-op."""
    ledger = CreditLedger(tmp_path)
    ledger.grant(ADDR, 10_000)
    ledger.debit(ADDR, 3_333, request_id="mid")
    ledger.refund(ADDR, request_id="mid")
    assert ledger.balance(ADDR) == 10_000
    refunds = [e for e in ledger.entries(ADDR) if e.kind == CreditKind.REFUND.value]
    debits = [e for e in ledger.entries(ADDR) if e.kind == CreditKind.DEBIT.value]
    assert len(refunds) == 1
    assert len(debits) == 1
    assert refunds[0].amount == abs(debits[0].amount)
    # third call still does not invent extra credit
    ledger.refund(ADDR, request_id="mid")
    assert ledger.balance(ADDR) == 10_000
    ledger.close()


def test_accounts_are_isolated(tmp_path):
    ledger = CreditLedger(tmp_path)
    ledger.grant(ADDR, 1_000)
    ledger.grant(OTHER, 50)
    ledger.debit(ADDR, 200, request_id="a1")
    assert ledger.balance(ADDR) == 800
    assert ledger.balance(OTHER) == 50
    with pytest.raises(RefundNotAllowed):
        ledger.refund(OTHER, request_id="a1")
    ledger.close()


def test_rejects_non_positive_and_non_int_amounts(tmp_path):
    ledger = CreditLedger(tmp_path)
    with pytest.raises(CreditError):
        ledger.grant(ADDR, 0)
    with pytest.raises(CreditError):
        ledger.grant(ADDR, -1)
    with pytest.raises(CreditError):
        ledger.topup(ADDR, 0)
    with pytest.raises(CreditError):
        ledger.debit(ADDR, 0, request_id="z")
    with pytest.raises(CreditError):
        ledger.debit(ADDR, -5, request_id="z")
    with pytest.raises(CreditError):
        ledger.grant(ADDR, True)  # type: ignore[arg-type]
    with pytest.raises(CreditError):
        ledger.debit(ADDR, 1, request_id="")
    ledger.close()


def test_balance_is_journal_sum(tmp_path):
    ledger = CreditLedger(tmp_path)
    ledger.topup(ADDR, 10_000, request_id="t1")
    ledger.debit(ADDR, 4_000, request_id="d1")
    ledger.refund(ADDR, request_id="d1")
    ledger.debit(ADDR, 1_500, request_id="d2")
    entries = ledger.entries(ADDR, limit=100)
    assert sum(e.amount for e in entries) == ledger.balance(ADDR)
    assert ledger.balance(ADDR) == 8_500
    ledger.close()


def test_persists_across_reopen(tmp_path):
    CreditLedger(tmp_path).grant(ADDR, 777)
    CreditLedger(tmp_path).debit(ADDR, 77, request_id="persist")
    assert CreditLedger(tmp_path).balance(ADDR) == 700


def test_summary_shape(tmp_path):
    ledger = CreditLedger(tmp_path)
    ledger.grant(ADDR, 50)
    s = ledger.summary(ADDR)
    assert s["account"] == ADDR_FOLD
    assert s["balance"] == 50
    assert s["unit"] == "atomic_usdc"
    assert s["entries"]
    assert s["entries"][0]["kind"] == CreditKind.GRANT.value
    ledger.close()
