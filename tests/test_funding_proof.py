"""Observe USDC Transfer custody for an enrolled commerce address.

Not a faucet. Not product settlement. A Transfer log to the address is the
only thing that sets funded=true.
"""

from __future__ import annotations

from veritas.funding_proof import TRANSFER_TOPIC, prove_funding
from veritas.x402 import USDC_ASSETS

USDC = USDC_ASSETS["eip155:84532"]["address"]
ALICE = "0x" + "ab" * 20
FAUCET = "0x" + "11" * 20
TX = "0x" + "cd" * 32


def _pad(addr: str) -> str:
    return "0x" + addr.lower().removeprefix("0x").zfill(64)


def test_prove_funding_from_transfer_log():
    def transport(_url: str, method: str, params: list):
        if method == "eth_getLogs":
            return [
                {
                    "address": USDC,
                    "topics": [TRANSFER_TOPIC, _pad(FAUCET), _pad(ALICE)],
                    "data": hex(20_000_000),
                    "transactionHash": TX,
                    "blockNumber": "0x10",
                }
            ]
        if method == "eth_call":
            return hex(20_000_000)
        raise AssertionError(method)

    proof = prove_funding(
        ALICE,
        network="eip155:84532",
        rpc_url="https://sepolia.base.org",
        transport=transport,
    )
    assert proof["funded"] is True
    assert proof["not_x402_settlement"] is True
    assert proof["transfers"][0]["amount_atomic"] == 20_000_000
    assert proof["transfers"][0]["tx"] == TX
    assert proof["balance_atomic"] == 20_000_000


def test_prove_funding_absent_is_not_funded():
    def transport(_url: str, method: str, _params: list):
        if method == "eth_getLogs":
            return []
        if method == "eth_call":
            return "0x0"
        raise AssertionError(method)

    proof = prove_funding(
        ALICE,
        network="eip155:84532",
        rpc_url="https://sepolia.base.org",
        transport=transport,
    )
    assert proof["funded"] is False
    assert proof["transfers"] == []
    assert "faucet.circle.com" in proof["next"]


def test_prove_funding_log_scan_failure_is_not_funded():
    """Public RPCs often refuse 0x0→latest. Balance is not Transfer custody."""

    def transport(_url: str, method: str, _params: list):
        if method == "eth_getLogs":
            raise RuntimeError("block range too large")
        if method == "eth_call":
            return hex(20_000_000)
        raise AssertionError(method)

    proof = prove_funding(
        ALICE,
        network="eip155:84532",
        rpc_url="https://sepolia.base.org",
        transport=transport,
    )
    assert proof["funded"] is False
    assert proof["balance_atomic"] == 20_000_000
    assert "logs_error" in proof
    assert "error" not in proof


def test_prove_funding_specific_tx():
    def transport(_url: str, method: str, params: list):
        if method == "eth_getTransactionReceipt":
            assert params[0] == TX
            return {
                "status": "0x1",
                "logs": [
                    {
                        "address": USDC,
                        "topics": [TRANSFER_TOPIC, _pad(FAUCET), _pad(ALICE)],
                        "data": hex(5_000_000),
                        "transactionHash": TX,
                        "blockNumber": "0x11",
                    }
                ],
            }
        if method == "eth_call":
            return hex(5_000_000)
        raise AssertionError(method)

    proof = prove_funding(
        ALICE,
        network="eip155:84532",
        tx_hash=TX,
        rpc_url="https://sepolia.base.org",
        transport=transport,
    )
    assert proof["funded"] is True
    assert proof["transfers"][0]["amount_atomic"] == 5_000_000
