"""Phase 0.1-R money loop: offline pins — no live sockets, no invented green."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from veritas.chain_reconcile import DEFAULT_PUBLIC_RPC_URLS, ENV_RPC_URL
from veritas.money_loop import (
    EXIT_HONEST,
    EXIT_OK,
    EXIT_TRANSPORT,
    classify_exit,
    run_money_loop,
    run_reconcile,
    run_settle,
)


def test_mainnet_never_in_public_defaults():
    assert "eip155:8453" not in DEFAULT_PUBLIC_RPC_URLS
    assert "eip155:84532" in DEFAULT_PUBLIC_RPC_URLS


def test_default_transport_sends_versioned_user_agent():
    """UA is load-bearing for Cloudflare-fronted RPC (live defect class)."""
    import inspect

    from veritas import chain_reconcile

    source = inspect.getsource(chain_reconcile._default_transport)
    assert "User-Agent" in source
    assert "veritas-chain-reconcile/" in source


def test_run_settle_missing_buyer_key_is_honest_not_ok():
    report = run_settle(base_url="http://127.0.0.1:9", buyer_key="")
    assert report["acceptance"]["met"] is False
    assert report["error_class"] == "honest"
    assert classify_exit(report, None) == EXIT_HONEST


def test_run_settle_transport_failure(monkeypatch):
    def boom(method, url, body, headers):
        raise OSError("connection refused")

    report = run_settle(
        base_url="http://127.0.0.1:9",
        buyer_key="0x" + "11" * 32,
        http_json=boom,
    )
    assert report["error_class"] == "transport"
    assert classify_exit(report, None) == EXIT_TRANSPORT


def test_run_settle_simulated_is_honest():
    def http(method, url, body, headers):
        if method == "GET":
            return 200, {"status": "ok"}, {}
        if headers and "X-PAYMENT" in headers:
            return (
                200,
                {
                    "request_id": "r1",
                    "status": "completed",
                    "settlement": {"transaction": "simulated:abc", "network": "eip155:84532"},
                },
                {},
            )
        return (
            402,
            {
                "accepts": [
                    {
                        "scheme": "exact",
                        "network": "eip155:84532",
                        "maxAmountRequired": "10000",
                        "asset": "0x" + "aa" * 20,
                        "payTo": "0x" + "bb" * 20,
                        "resource": "http://127.0.0.1:8000/v1/signals",
                        "description": "t",
                        "mimeType": "application/json",
                        "maxTimeoutSeconds": 60,
                        "extra": {"name": "USDC", "version": "2"},
                    }
                ]
            },
            {},
        )

    # pay_via_policy will fail on fake key — still honest path
    report = run_settle(
        base_url="http://127.0.0.1:8000",
        buyer_key="not-a-key",
        http_json=http,
    )
    assert report["acceptance"]["met"] is False
    assert report["error_class"] == "honest"


def test_reconcile_empty_ledger_honest_not_green(monkeypatch):
    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        report = run_reconcile(runtime_dir=tmp)
        assert report["candidates"] == 0
        assert report["error_class"] == "honest"
        assert report.get("chain_checked") is False
        assert classify_exit(None, report) == EXIT_HONEST


def test_reconcile_testnet_default_stamps_rpc_source(monkeypatch):
    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    tx = "0x" + "ab" * 32

    def transport(url, method, params):
        assert url == DEFAULT_PUBLIC_RPC_URLS["eip155:84532"]
        assert method == "eth_getTransactionReceipt"
        return {"status": "0x1"}

    report = run_reconcile(
        settlements=[
            {
                "request_id": "r-loop",
                "transaction": tx,
                "network": "eip155:84532",
            }
        ],
        transport=transport,
    )
    assert report["chain_checked"] is True
    assert report["results"][0]["status"] == "confirmed"
    assert report["results"][0]["rpc_source"] == "default_public_rpc:eip155:84532"
    assert classify_exit(None, report) == EXIT_OK


def test_reconcile_mainnet_unconfigured_without_env(monkeypatch):
    monkeypatch.delenv(ENV_RPC_URL, raising=False)

    def transport(url, method, params):  # pragma: no cover - must not run
        raise AssertionError("mainnet must not hit transport without env")

    report = run_reconcile(
        settlements=[
            {
                "request_id": "m",
                "transaction": "0x" + "cd" * 32,
                "network": "eip155:8453",
            }
        ],
        transport=transport,
    )
    assert report["results"][0]["status"] == "rpc_not_configured"
    assert report["results"][0]["rpc_source"] == "unconfigured"
    assert classify_exit(None, report) == EXIT_HONEST


def test_money_loop_settle_then_reconcile_confirmed(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    tx = "0x" + "11" * 32
    settle = {
        "phase": "settle",
        "acceptance": {"met": True, "transaction": tx, "notes": []},
        "proof": {"request_id": "req-1", "network": "eip155:84532"},
        "requirements": {"network": "eip155:84532"},
        "error_class": None,
    }

    def transport(url, method, params):
        return {"status": "0x1"}

    code, evidence = run_money_loop(
        do_settle=True,
        do_reconcile=True,
        settle_report=settle,
        transport=transport,
        out_dir=tmp_path,
    )
    assert code == EXIT_OK
    assert evidence["acceptance"]["met"] is True
    assert evidence["reconcile"]["results"][0]["status"] == "confirmed"
    assert evidence["reconcile"]["results"][0]["rpc_source"].startswith(
        "default_public_rpc:"
    )
    wrote = Path(evidence["wrote"])
    assert wrote.is_file()
    body = json.loads(wrote.read_text(encoding="utf-8"))
    assert body["exit_code"] == EXIT_OK
    assert body["defaults"]["mainnet_never_defaulted"] is True


def test_money_loop_does_not_invent_green_on_unconfirmed(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    tx = "0x" + "22" * 32
    settle = {
        "phase": "settle",
        "acceptance": {"met": True, "transaction": tx, "notes": []},
        "proof": {"request_id": "req-2", "network": "eip155:84532"},
        "requirements": {"network": "eip155:84532"},
        "error_class": None,
    }

    def transport(url, method, params):
        return None  # not_found

    code, evidence = run_money_loop(
        settle_report=settle,
        transport=transport,
        out_dir=tmp_path,
    )
    assert code == EXIT_HONEST
    assert evidence["acceptance"]["met"] is False
    assert evidence["reconcile"]["results"][0]["status"] == "not_found"


def test_money_loop_rpc_unavailable_is_transport(tmp_path, monkeypatch):
    from veritas.chain_reconcile import ChainReconcileError

    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    tx = "0x" + "33" * 32
    settle = {
        "phase": "settle",
        "acceptance": {"met": True, "transaction": tx, "notes": []},
        "proof": {"request_id": "req-3", "network": "eip155:84532"},
        "requirements": {"network": "eip155:84532"},
        "error_class": None,
    }

    def transport(url, method, params):
        raise ChainReconcileError("rpc_transport_error:URLError")

    code, evidence = run_money_loop(
        settle_report=settle,
        transport=transport,
        out_dir=tmp_path,
    )
    assert code == EXIT_TRANSPORT
    assert evidence["reconcile"]["error_class"] == "transport"


def test_g9_note_mentions_testnet_defaults_and_gap_open():
    from veritas.chain_reconcile import G9_NOTE

    lower = G9_NOTE.lower()
    assert "testnet" in lower or "default" in lower
    assert "mainnet" in lower
    assert "does not rewrite" in lower or "not rewrite" in lower
