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

from veritas.autonomous.local_facilitator import verify_payment
from veritas.eip3009 import typed_data_for_authorization

pytest.importorskip("eth_account")


def _encode(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


NETWORK = "eip155:84532"


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


def test_known_gap_simulator_does_not_check_nonce_or_balance():
    """Witness for gap G13: a freshly signed authorization passes with no
    chain lookup. The signer may have zero USDC and the nonce may already
    have been submitted; the local simulator cannot see either. If this
    test fails, the gap has been fixed — close G13 in
    veritas/constitution.py and delete this test."""
    payload = _signed_payload()
    assert verify_payment({"X-PAYMENT": _encode(payload)}, require=True) is True
    # A second presentation of the same nonce is still accepted locally.
    assert verify_payment({"X-PAYMENT": _encode(payload)}, require=True) is True


def test_simulator_free_mode_performs_no_verification():
    """require=False means free mode: allowed through, and documented as
    unverified rather than pretended-verified."""
    assert verify_payment({}, require=False) is True


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
