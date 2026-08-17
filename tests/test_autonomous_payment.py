"""The agent-native payment simulator: EIP-712 signatures, declared limits.

Gap G1 (constitution v1.0) recorded that the local simulator accepted any
non-empty payment header. G2 recorded that a forged signature still passed.
Both are closed: the simulator decodes via the shared x402 path and recovers
the EIP-3009 signer.
"""

from __future__ import annotations

import base64
import json
import secrets
import time

import pytest

from veritas.autonomous.local_facilitator import ENV_CHAIN_CHECKS, verify_payment
from veritas.chain_reconcile import ENV_RPC_URL, ChainReconcileError
from veritas.eip3009 import (
    AUTHORIZATION_STATE_SELECTOR,
    BALANCE_OF_SELECTOR,
    typed_data_for_authorization,
)
from veritas.x402 import USDC_ASSETS

pytest.importorskip("eth_account")


def _encode(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


NETWORK = "eip155:84532"
USDC = USDC_ASSETS[NETWORK]["address"]


def _signed_payload(*, now: int | None = None, valid_for: int = 600) -> dict:
    from eth_account import Account
    from eth_account.messages import encode_typed_data

    account = Account.create()
    ts = now if now is not None else int(time.time())
    authorization = {
        "from": account.address,
        "to": "0x" + "2" * 40,
        "value": "10000",
        "validAfter": str(ts - 1),
        "validBefore": str(ts + valid_for),
        "nonce": "0x" + secrets.token_bytes(32).hex(),
    }
    typed = typed_data_for_authorization(authorization, network=NETWORK)
    signature = "0x" + account.sign_message(
        encode_typed_data(full_message=typed)
    ).signature.hex()
    return {
        "x402Version": 1,
        "scheme": "exact",
        "network": NETWORK,
        "payload": {"signature": signature, "authorization": authorization},
        "payer": account.address,
    }


STRUCTURAL_PAYLOAD = {
    "x402Version": 1,
    "scheme": "exact",
    "network": NETWORK,
    "payload": {
        "signature": "0x" + "ab" * 65,
        "authorization": {
            "from": "0x" + "1" * 40,
            "to": "0x" + "2" * 40,
            "value": "250000",
            "nonce": "0x" + "3" * 64,
        },
    },
}


def _enable_chain_checks(monkeypatch) -> None:
    monkeypatch.setenv(ENV_CHAIN_CHECKS, "1")
    monkeypatch.setenv(ENV_RPC_URL, "https://rpc.example")


def test_simulator_rejects_malformed_header_when_required():
    """Previously any non-empty string bought access (gap G1, now closed)."""
    assert verify_payment({"X-PAYMENT": "garbage-not-a-payment"}, require=True) is False
    assert verify_payment({"PAYMENT-SIGNATURE": "hello"}, require=True) is False
    assert verify_payment({}, require=True) is False
    assert verify_payment({"X-PAYMENT": _encode({"no": "authorization"})}, require=True) is False


def test_simulator_rejects_structurally_valid_forged_signature():
    """G2 closed: a garbage signature on a well-shaped payload is refused."""
    assert verify_payment({"X-PAYMENT": _encode(STRUCTURAL_PAYLOAD)}, require=True) is False


def test_simulator_accepts_a_real_eip3009_signature():
    assert verify_payment({"X-PAYMENT": _encode(_signed_payload())}, require=True) is True


def test_known_gap_simulator_does_not_check_nonce_or_balance(monkeypatch):
    """Witness for gap G13: a freshly signed authorization passes with no
    chain lookup. The signer may have zero USDC and the nonce may already
    have been submitted; the local simulator cannot see either. If this
    test fails, the gap has been fixed — close G13 in
    veritas/constitution.py and delete this test."""
    monkeypatch.delenv(ENV_CHAIN_CHECKS, raising=False)
    payload = _signed_payload()
    assert verify_payment({"X-PAYMENT": _encode(payload)}, require=True) is True
    # A second presentation of the same nonce is still accepted locally.
    assert verify_payment({"X-PAYMENT": _encode(payload)}, require=True) is True


def test_simulator_free_mode_performs_no_verification():
    """require=False means free mode: allowed through, and documented as
    unverified rather than pretended-verified."""
    assert verify_payment({}, require=False) is True


def test_chain_checks_opt_in_rejects_used_nonce(monkeypatch):
    """Opt-in + RPC saying the EIP-3009 nonce is already used → refuse."""
    _enable_chain_checks(monkeypatch)
    payload = _signed_payload()
    auth = payload["payload"]["authorization"]
    calls: list[str] = []

    def transport(url: str, method: str, params: list):
        assert url == "https://rpc.example"
        assert method == "eth_call"
        data = params[0]["data"]
        calls.append(data)
        if data.startswith(AUTHORIZATION_STATE_SELECTOR):
            assert params[0]["to"] == USDC
            assert auth["from"].lower().removeprefix("0x") in data.lower()
            assert auth["nonce"].removeprefix("0x").lower() in data.lower()
            return "0x" + "0" * 63 + "1"
        raise AssertionError(f"unexpected call {data}")

    assert verify_payment(
        {"X-PAYMENT": _encode(payload)}, require=True, transport=transport
    ) is False
    assert calls and calls[0].startswith(AUTHORIZATION_STATE_SELECTOR)


def test_chain_checks_opt_in_rejects_zero_balance(monkeypatch):
    """Opt-in + unused nonce but balanceOf == 0 → refuse."""
    _enable_chain_checks(monkeypatch)
    payload = _signed_payload()

    def transport(_url: str, method: str, params: list):
        assert method == "eth_call"
        data = params[0]["data"]
        if data.startswith(AUTHORIZATION_STATE_SELECTOR):
            return "0x" + "0" * 64
        if data.startswith(BALANCE_OF_SELECTOR):
            return "0x" + "0" * 64
        raise AssertionError(data)

    assert verify_payment(
        {"X-PAYMENT": _encode(payload)}, require=True, transport=transport
    ) is False


def test_chain_checks_opt_in_rpc_error_fails_closed(monkeypatch):
    """Opt-in + RPC error/timeout → refuse; do not pass an unchecked payment."""
    _enable_chain_checks(monkeypatch)
    payload = _signed_payload()

    def transport(_url: str, _method: str, _params: list):
        raise ChainReconcileError("rpc_transport_error:TimeoutError")

    assert verify_payment(
        {"X-PAYMENT": _encode(payload)}, require=True, transport=transport
    ) is False


def test_chain_checks_opt_out_does_not_consult_chain(monkeypatch):
    """Opt-in off: even a failing RPC is never consulted. Witness stays meaningful."""
    monkeypatch.delenv(ENV_CHAIN_CHECKS, raising=False)
    monkeypatch.setenv(ENV_RPC_URL, "https://rpc.example")
    called: list[str] = []

    def transport(_url: str, method: str, _params: list):
        called.append(method)
        raise RuntimeError("rpc would fail")

    payload = _signed_payload()
    assert verify_payment(
        {"X-PAYMENT": _encode(payload)}, require=True, transport=transport
    ) is True
    assert verify_payment(
        {"X-PAYMENT": _encode(payload)}, require=True, transport=transport
    ) is True
    assert called == []


def test_chain_checks_opt_in_without_rpc_fails_closed(monkeypatch):
    """Flag on but no VERITAS_RPC_URL: cannot check, so refuse."""
    monkeypatch.setenv(ENV_CHAIN_CHECKS, "1")
    monkeypatch.delenv(ENV_RPC_URL, raising=False)
    payload = _signed_payload()
    assert verify_payment({"X-PAYMENT": _encode(payload)}, require=True) is False


def test_chain_checks_opt_in_accepts_unused_nonce_and_balance(monkeypatch):
    """Opt-in + unused nonce + balance >= value → still accept."""
    _enable_chain_checks(monkeypatch)
    payload = _signed_payload()

    def transport(_url: str, method: str, params: list):
        assert method == "eth_call"
        data = params[0]["data"]
        if data.startswith(AUTHORIZATION_STATE_SELECTOR):
            return "0x" + "0" * 64
        if data.startswith(BALANCE_OF_SELECTOR):
            return hex(10_000)
        raise AssertionError(data)

    assert verify_payment(
        {"X-PAYMENT": _encode(payload)}, require=True, transport=transport
    ) is True


def test_control_plane_price_follows_payment_config(tmp_path, monkeypatch):
    """The recorded settlement amount was hardcoded '$0.25'; it must follow
    the configured price."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("VERITAS_PRICE", "$0.10")

    import importlib

    import veritas.autonomous.local_facilitator as lf
    importlib.reload(lf)
    import veritas.autonomous.control_plane as cp
    importlib.reload(cp)

    from veritas.autonomous.bootstrap import bootstrap_free_mode

    config = bootstrap_free_mode()
    config_path = tmp_path / ".veritas_agent" / "config.json"
    config["require_payment"] = True
    config_path.write_text(json.dumps(config))

    result = cp.agent_research(
        "What is x402?", headers={"X-PAYMENT": _encode(_signed_payload())}
    )
    assert result["status"] in {"completed", "refused", "unavailable"}

    settlements = [
        json.loads(line)
        for line in (tmp_path / "runtime" / "settlements.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert settlements, "no settlement recorded"
    if result["billable"]:
        assert settlements[-1]["amount"] == "$0.10"
