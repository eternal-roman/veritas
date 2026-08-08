"""The agent-native payment simulator: structural rigor, declared limits.

Gap G1 (constitution v1.0) recorded that the local simulator accepted any
non-empty payment header and the control plane hardcoded its price. These
tests enforce the fix: the simulator now decodes headers with the same rigor
as the HTTP path and requires the x402 structural shape, and the control
plane's recorded amounts follow payment config. What the simulator still
does not do — verify signatures — is registered as gap G2 and pinned here.
"""

from __future__ import annotations

import base64
import json

import pytest

from veritas.autonomous.local_facilitator import verify_payment


def _encode(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


STRUCTURAL_PAYLOAD = {
    "x402Version": 1,
    "scheme": "exact",
    "network": "eip155:84532",
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


def test_simulator_accepts_structurally_valid_header():
    assert verify_payment({"X-PAYMENT": _encode(STRUCTURAL_PAYLOAD)}, require=True) is True


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
        "What is x402?", headers={"X-PAYMENT": _encode(STRUCTURAL_PAYLOAD)}
    )
    assert result["status"] in {"completed", "refused", "unavailable"}

    settlements = [
        json.loads(line)
        for line in (tmp_path / "runtime" / "settlements.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert settlements, "no settlement recorded"
    if result["billable"]:
        assert settlements[-1]["amount"] == "$0.10"


@pytest.mark.filterwarnings("ignore")
def test_known_gap_simulator_does_not_verify_signatures():
    """Witness for gap G2: a structurally valid payload with a garbage
    signature passes the simulator, which checks structure and config, not
    signatures. The HTTP path's facilitator verification remains the strong
    gate. If this test fails, the gap has been fixed — close G2 in
    veritas/constitution.py and delete this test."""
    forged = json.loads(json.dumps(STRUCTURAL_PAYLOAD))
    forged["payload"]["signature"] = "0x" + "00" * 65
    assert verify_payment({"X-PAYMENT": _encode(forged)}, require=True) is True
