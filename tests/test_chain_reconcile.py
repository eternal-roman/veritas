"""G9 design: chain reconcile fail-closed without RPC; classifies with inject."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from veritas.chain_reconcile import (
    ENV_RPC_URL,
    check_transaction,
    classify_receipt,
    reconcile_settlements,
)
from veritas.ledger import Ledger


def test_classify_receipt_statuses():
    assert classify_receipt(None) == "not_found"
    assert classify_receipt({"status": "0x1"}) == "confirmed"
    assert classify_receipt({"status": "0x0"}) == "reverted"
    assert classify_receipt({"status": "0x2"}) == "unknown_status"
    assert classify_receipt({}) == "unknown_status"


def test_check_transaction_without_rpc(monkeypatch):
    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    out = check_transaction("0x" + "ab" * 32)
    assert out["chain_checked"] is False
    assert out["status"] == "rpc_not_configured"


def test_check_transaction_invalid_hash(monkeypatch):
    monkeypatch.setenv(ENV_RPC_URL, "https://rpc.example")
    out = check_transaction("not-a-hash")
    assert out["status"] == "invalid_hash"
    assert out["chain_checked"] is False


def test_check_transaction_with_injected_transport_confirmed(monkeypatch):
    monkeypatch.setenv(ENV_RPC_URL, "https://rpc.example")

    def transport(url, method, params):
        assert url == "https://rpc.example"
        assert method == "eth_getTransactionReceipt"
        assert params == ["0x" + "cd" * 32]
        return {"status": "0x1", "blockNumber": "0x10"}

    out = check_transaction("0x" + "cd" * 32, transport=transport)
    assert out["chain_checked"] is True
    assert out["status"] == "confirmed"


def test_check_transaction_rpc_error(monkeypatch):
    monkeypatch.setenv(ENV_RPC_URL, "https://rpc.example")

    def transport(url, method, params):
        from veritas.chain_reconcile import ChainReconcileError

        raise ChainReconcileError("rpc_error:-32000")

    out = check_transaction("0x" + "ef" * 32, transport=transport)
    assert out["chain_checked"] is False
    assert out["status"] == "rpc_unavailable"


def test_reconcile_settlements_mix(monkeypatch):
    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    rows = [
        {"request_id": "a", "transaction": "0x" + "11" * 32},
        {"request_id": "b", "transaction": None},
    ]
    report = reconcile_settlements(rows)
    assert report["rpc_configured"] is False
    assert report["chain_checked"] is False
    statuses = {r["request_id"]: r["status"] for r in report["results"]}
    assert statuses["a"] == "rpc_not_configured"
    assert statuses["b"] == "missing_transaction"


def test_ledger_settled_with_transaction_candidates():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Ledger(tmp)
        # claim + deliver + settle with hash
        claim = ledger.claim(
            "0x" + "aa" * 32,
            "req-g9-1",
            network="eip155:84532",
            asset="0xusdc",
            amount="10000",
            pay_to="0x" + "22" * 20,
            payer="0x" + "33" * 20,
            price="$0.01",
            price_version="test",
        )
        assert claim.claimed
        ledger.record_delivery(
            "req-g9-1",
            status="completed",
            billable=True,
            custody_root="sha256:" + "00" * 32,
            query="q",
            response={"ok": True},
        )
        ledger.record_settlement(
            "req-g9-1",
            outcome="settled",
            transaction="0x" + "dd" * 32,
            network="eip155:84532",
            payer="0x" + "33" * 20,
        )
        with_tx = ledger.settled_with_transaction()
        assert len(with_tx) == 1
        assert with_tx[0]["transaction"] == "0x" + "dd" * 32
        assert ledger.settled_without_transaction() == []


def test_ops_reconcile_chain_fail_closed(monkeypatch, capsys):
    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("VERITAS_RUNTIME_DIR", tmp)
        from veritas.ops_cli import main

        code = main(["--runtime-dir", tmp, "reconcile-chain"])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["rpc_configured"] is False
        assert payload["chain_checked"] is False
        assert "G9" in payload["limitation"] or "G9" in payload.get("note", "")


def test_g9_witness_still_holds_on_ledger():
    """Design module may RPC; ledger module must not claim chain reconcile."""
    from veritas import ledger as ledger_module

    source = Path(ledger_module.__file__).read_text(encoding="utf-8")
    assert "eth_getTransactionReceipt" not in source
    assert not hasattr(ledger_module.Ledger, "reconcile_against_chain")
