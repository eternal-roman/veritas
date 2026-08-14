"""`veritas-ops`: the operator's answers, drawn from the ledger only.

An operator running this service has four questions and, before this CLI,
no way to ask any of them: how much did I earn, what did I deliver and never
get paid for, what needs my attention, and what did it cost me.

The rule that governs the reconcile command is the same one that governs the
ledger: it reports what this instance recorded, and says plainly that it has
not checked any of it against the chain. A reconcile
report that implies on-chain confirmation it never performed would be the most
damaging possible lie in this codebase.
"""

from __future__ import annotations

import json

from veritas.ledger import Ledger
from veritas.ops_cli import main

NONCE = "0x" + "ab" * 32
OTHER_NONCE = "0x" + "cd" * 32
OFFER = {
    "network": "eip155:84532",
    "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "amount": "10000",
    "pay_to": "0x" + "11" * 20,
    "price": "$0.01",
}


def _run(capsys, *args) -> dict:
    code = main(list(args))
    assert code == 0, f"exit {code}"
    return json.loads(capsys.readouterr().out)


def _settled(ledger: Ledger, request_id: str, nonce: str):
    ledger.claim(nonce, request_id, **OFFER)
    ledger.record_delivery(request_id, status="completed", billable=True,
                           custody_root="sha256:r", query="q", response={})
    ledger.record_settlement(request_id, outcome="settled", transaction="0xtx-" + request_id)


def _delivered_unpaid(ledger: Ledger, request_id: str, nonce: str):
    ledger.claim(nonce, request_id, **OFFER)
    ledger.record_delivery(request_id, status="completed", billable=True,
                           custody_root="sha256:r", query="q", response={})


def test_revenue_reports_settled_amounts(tmp_path, capsys):
    ledger = Ledger(tmp_path)
    _settled(ledger, "req-1", NONCE)
    report = _run(capsys, "--runtime-dir", str(tmp_path), "revenue")
    assert report["financial"]["settled_count"] == 1
    assert report["revenue_micros"] == 10000


def test_owed_lists_delivered_work_with_no_settlement(tmp_path, capsys):
    ledger = Ledger(tmp_path)
    _settled(ledger, "req-1", NONCE)
    _delivered_unpaid(ledger, "req-2", OTHER_NONCE)
    report = _run(capsys, "--runtime-dir", str(tmp_path), "owed")
    assert [a["request_id"] for a in report["awaiting_settlement"]] == ["req-2"]
    assert report["count"] == 1


def test_reconcile_flags_delivered_but_unsettled_work(tmp_path, capsys):
    ledger = Ledger(tmp_path)
    _delivered_unpaid(ledger, "req-2", OTHER_NONCE)
    report = _run(capsys, "--runtime-dir", str(tmp_path), "reconcile")
    assert report["needs_attention"]
    assert any(item["reason"] == "delivered_not_settled" for item in report["needs_attention"])


def test_reconcile_flags_indeterminate_settlements(tmp_path, capsys):
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    ledger.record_delivery("req-1", status="completed", billable=True,
                           custody_root="sha256:r", query="q", response={})
    ledger.record_settlement("req-1", outcome="indeterminate", reason="facilitator_timeout")
    report = _run(capsys, "--runtime-dir", str(tmp_path), "reconcile")
    assert any(item["reason"] == "settlement_indeterminate"
               for item in report["needs_attention"])


def test_reconcile_flags_a_settlement_with_no_transaction_hash(tmp_path, capsys):
    """A `settled` entry a facilitator returned without a transaction is not
    evidence of anything; it must not quietly count as revenue."""
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    ledger.record_delivery("req-1", status="completed", billable=True,
                           custody_root="sha256:r", query="q", response={})
    ledger.record_settlement("req-1", outcome="settled", transaction=None)
    report = _run(capsys, "--runtime-dir", str(tmp_path), "reconcile")
    assert any(item["reason"] == "settled_without_transaction"
               for item in report["needs_attention"])


def test_reconcile_states_that_it_has_not_checked_the_chain(tmp_path, capsys):
    """The local reconcile report must never read as on-chain confirmation."""
    ledger = Ledger(tmp_path)
    _settled(ledger, "req-1", NONCE)
    report = _run(capsys, "--runtime-dir", str(tmp_path), "reconcile")
    assert report["chain_checked"] is False
    assert "reconcile-chain" in report["limitation"]


def test_a_clean_ledger_reconciles_with_nothing_to_do(tmp_path, capsys):
    ledger = Ledger(tmp_path)
    _settled(ledger, "req-1", NONCE)
    report = _run(capsys, "--runtime-dir", str(tmp_path), "reconcile")
    assert report["needs_attention"] == []
    assert report["clean"] is True


def test_usage_reports_unpriced_providers_rather_than_assuming_free(tmp_path, capsys, monkeypatch):
    from veritas.metering import Usage

    monkeypatch.delenv("VERITAS_PROVIDER_COST_MICROS", raising=False)
    ledger = Ledger(tmp_path)
    ledger.record_usage(Usage(
        request_id="r1", status="completed", billable=True, paid=False,
        provider_calls={"serper": 1}, evidence_bytes=10, duration_ms=5,
    ))
    report = _run(capsys, "--runtime-dir", str(tmp_path), "usage")
    assert report["cost_micros"] is None
    assert report["unpriced_providers"] == ["serper"]


def test_authorization_shows_one_payment_end_to_end(tmp_path, capsys):
    ledger = Ledger(tmp_path)
    _settled(ledger, "req-1", NONCE)
    report = _run(capsys, "--runtime-dir", str(tmp_path), "authorization", NONCE)
    assert report["authorization"]["request_id"] == "req-1"
    assert report["settlements"][0]["transaction"] == "0xtx-req-1"


def test_an_unknown_authorization_exits_nonzero(tmp_path, capsys):
    assert main(["--runtime-dir", str(tmp_path), "authorization", OTHER_NONCE]) == 1


def test_pricing_reports_the_version_entries_are_stamped_with(tmp_path, capsys):
    from veritas.pricing import PRICE_TABLE_VERSION

    report = _run(capsys, "--runtime-dir", str(tmp_path), "pricing")
    assert report["version"] == PRICE_TABLE_VERSION
    assert report["atomic_amount"]


def test_owed_counts_an_indeterminate_settlement_as_exposure(tmp_path, capsys):
    """Found by dogfood cycle 4. `owed` reported zero while `reconcile`
    flagged an unresolved settlement — an operator told "you are owed nothing"
    while holding delivered work nobody could show was paid for."""
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    ledger.record_delivery("req-1", status="completed", billable=True,
                           custody_root="sha256:r", query="q", response={})
    ledger.record_settlement("req-1", outcome="indeterminate",
                             reason="facilitator_timeout")

    report = _run(capsys, "--runtime-dir", str(tmp_path), "owed")
    assert report["count"] == 1
    assert report["by_state"] == {"indeterminate": 1}
    assert report["amount_at_risk"] == {"eip155:84532/" + OFFER["asset"]: "10000"}


def test_owed_separates_the_three_ways_work_goes_unpaid(tmp_path, capsys):
    """They are owed in different senses and an operator acts differently on
    each, so one undifferentiated count would hide the distinction."""
    ledger = Ledger(tmp_path)
    for i, (nonce, outcome) in enumerate((
        (NONCE, None), (OTHER_NONCE, "failed"), ("0x" + "ef" * 32, "indeterminate"),
    )):
        rid = f"req-{i}"
        ledger.claim(nonce, rid, **OFFER)
        ledger.record_delivery(rid, status="completed", billable=True,
                               custody_root="sha256:r", query="q", response={})
        if outcome:
            ledger.record_settlement(rid, outcome=outcome, reason="x")

    report = _run(capsys, "--runtime-dir", str(tmp_path), "owed")
    assert report["by_state"] == {
        "delivered": 1, "settlement_failed": 1, "indeterminate": 1,
    }
    assert report["amount_at_risk"] == {"eip155:84532/" + OFFER["asset"]: "30000"}


def test_reconcile_reports_one_problem_once(tmp_path, capsys):
    """An indeterminate settlement is owed AND needs attention, but it is one
    problem. Listing it under two labels tells an operator there are two."""
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    ledger.record_delivery("req-1", status="completed", billable=True,
                           custody_root="sha256:r", query="q", response={})
    ledger.record_settlement("req-1", outcome="indeterminate",
                             reason="facilitator_timeout")

    report = _run(capsys, "--runtime-dir", str(tmp_path), "reconcile")
    reasons = [item["reason"] for item in report["needs_attention"]]
    assert reasons == ["settlement_indeterminate"]


def test_prune_reports_json_counts_against_tmp_runtime(tmp_path, capsys):
    """O.6: veritas-ops prune ages custody + ledger with one cutoff; JSON only,
    never claims chain contact."""
    import json
    import sqlite3
    from datetime import datetime

    from veritas.custody import CustodyStore, ReceiptPresence

    ledger = Ledger(tmp_path)
    _settled(ledger, "req-old", NONCE)
    conn = sqlite3.connect(ledger.path)
    conn.execute(
        "UPDATE authorizations SET claimed_at = ?, updated_at = ? WHERE request_id = ?",
        ("2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z", "req-old"),
    )
    conn.commit()
    conn.close()

    store = CustodyStore(str(tmp_path))
    store.save({
        "request_id": "req-old", "query": "q", "status": "completed",
        "custody_root": "sha256:r", "custody_valid": True, "evidence": [],
    })
    path = store.base_dir / "req-old.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["stored_at"] = "2020-01-01T00:00:00Z"
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")

    report = _run(capsys, "--runtime-dir", str(tmp_path), "prune", "--days", "30")
    assert report["chain_checked"] is False
    assert "reconcile-chain" in report["limitation"]
    assert report["custody"]["deleted"] == 1
    assert report["ledger"]["authorizations_deleted"] == 1
    assert store.lookup("req-old") is ReceiptPresence.GONE
    assert ledger.authorization(NONCE) is None
    # Fresh cutoff math is exercised; days is echoed for the operator.
    assert report["retention_days"] == 30
    datetime.fromisoformat(report["cutoff"].replace("Z", "+00:00"))


def test_prune_rejects_nonsense_retention_without_mass_delete(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("VERITAS_RETENTION_DAYS", "0")
    code = main(["--runtime-dir", str(tmp_path), "prune"])
    assert code == 1
    report = json.loads(capsys.readouterr().out)
    assert report["error"] == "retention_misconfigured"
