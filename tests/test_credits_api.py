"""M7 HTTP surface: SIWx session, credits balance, credit-paid research, refunds.

Package M7.3 — research debit/refund, topup grant rules, discovery, error codes.
"""

from __future__ import annotations

import base64
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from veritas.facilitator import SettlementResult, VerificationResult

eth_account = pytest.importorskip("eth_account")


DOMAIN = "research.example.org"
PUBLIC = f"https://{DOMAIN}"
NONCE = "0x" + "ab" * 32
OTHER_NONCE = "0x" + "cd" * 32


def _payment_header(nonce: str = NONCE) -> str:
    return base64.b64encode(
        json.dumps(
            {
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
            }
        ).encode()
    ).decode()


class _FacilitatorControl:
    """Test-controlled facilitator for top-up settlement outcomes."""

    def __init__(self) -> None:
        self.settle_result = SettlementResult(
            True,
            transaction="0xdeadbeef",
            network="eip155:84532",
            payer="0xbuyer",
        )
        self.verify_calls = 0
        self.settle_calls = 0

    def verify(self, payload, requirements):
        self.verify_calls += 1
        return VerificationResult(True, payer="0xbuyer")

    def settle(self, payload, requirements):
        self.settle_calls += 1
        return self.settle_result


@pytest.fixture
def paid_credits_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "11" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")
    monkeypatch.setenv("VERITAS_PRICE", "$0.01")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", PUBLIC)
    monkeypatch.setenv("VERITAS_FACILITATOR", "https://facilitator.example/invalid")
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    import veritas.server as main_module

    importlib.reload(main_module)
    control = _FacilitatorControl()
    monkeypatch.setattr(main_module, "get_facilitator", lambda *a, **k: control)
    return TestClient(main_module.app), main_module, control


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.setenv("VERITAS_PUBLIC_URL", PUBLIC)
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    import veritas.server as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


@pytest.fixture
def misconfigured_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    # Invalid pay_to → mode misconfigured; must not invent credits
    monkeypatch.setenv("VERITAS_PAY_TO", "not-an-address")
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", PUBLIC)
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    import veritas.server as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def _open_session(client):
    acct = eth_account.Account.create()
    ch = client.post("/v1/siwx/challenge", json={"address": acct.address})
    assert ch.status_code == 200, ch.text
    body = ch.json()
    from eth_account.messages import encode_defunct

    signed = acct.sign_message(encode_defunct(text=body["message"]))
    sig = signed.signature.hex()
    if not sig.startswith("0x"):
        sig = "0x" + sig
    ver = client.post(
        "/v1/siwx/verify",
        json={"message": body["message"], "signature": sig},
    )
    assert ver.status_code == 200, ver.text
    return acct, ver.json()["session_token"]


def test_siwx_challenge_and_verify(paid_credits_client):
    client, _, _ = paid_credits_client
    acct, token = _open_session(client)
    bal = client.get("/v1/credits", headers={"X-VERITAS-SESSION": token})
    assert bal.status_code == 200
    body = bal.json()
    assert body["account"] == acct.address.lower()
    assert body["balance"] == 0


def test_topup_refuses_in_free_mode(free_client):
    acct, token = _open_session(free_client)
    r = free_client.post(
        "/v1/credits/topup",
        headers={"X-VERITAS-SESSION": token},
    )
    assert r.status_code == 503
    assert r.json()["error"] == "credits_topup_unavailable"
    assert free_client.get(
        "/v1/credits", headers={"X-VERITAS-SESSION": token}
    ).json()["balance"] == 0


def test_topup_refuses_when_misconfigured(misconfigured_client):
    # Challenge still works (no live pay required for SIWx), topup must not grant.
    acct, token = _open_session(misconfigured_client)
    r = misconfigured_client.post(
        "/v1/credits/topup",
        headers={"X-VERITAS-SESSION": token, "X-PAYMENT": _payment_header()},
    )
    assert r.status_code == 503
    assert r.json()["error"] == "payment_misconfigured"


def test_topup_settled_grants_atomic_amount_only(paid_credits_client):
    client, main_module, control = paid_credits_client
    acct, token = _open_session(client)
    assert main_module.credit_ledger.balance(acct.address) == 0

    r = client.post(
        "/v1/credits/topup",
        headers={"X-VERITAS-SESSION": token, "X-PAYMENT": _payment_header()},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["topped_up"] is True
    assert body["granted"] == 10_000  # $0.01 USDC-6
    assert body["balance"] == 10_000
    assert body["account"] == acct.address.lower()
    assert control.settle_calls == 1
    assert main_module.credit_ledger.balance(acct.address) == 10_000


def test_topup_failed_settlement_does_not_grant(paid_credits_client):
    client, main_module, control = paid_credits_client
    control.settle_result = SettlementResult(
        False, error_reason="settlement_rejected", network="eip155:84532",
    )
    acct, token = _open_session(client)
    r = client.post(
        "/v1/credits/topup",
        headers={"X-VERITAS-SESSION": token, "X-PAYMENT": _payment_header()},
    )
    assert r.status_code == 402
    body = r.json()
    assert body["topped_up"] is False
    assert body["reason"] == "settlement_failed"
    assert body["balance"] == 0
    assert main_module.credit_ledger.balance(acct.address) == 0


def test_topup_indeterminate_settlement_does_not_grant(paid_credits_client):
    client, main_module, control = paid_credits_client
    # facilitator_timeout is an indeterminate settlement reason
    control.settle_result = SettlementResult(
        False, error_reason="facilitator_timeout", network="eip155:84532",
    )
    acct, token = _open_session(client)
    r = client.post(
        "/v1/credits/topup",
        headers={
            "X-VERITAS-SESSION": token,
            "X-PAYMENT": _payment_header(OTHER_NONCE),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["topped_up"] is False
    assert body["reason"] == "settlement_indeterminate_no_credit_grant"
    assert body["balance"] == 0
    assert main_module.credit_ledger.balance(acct.address) == 0


def test_topup_without_payment_returns_402_challenge(paid_credits_client):
    client, _, _ = paid_credits_client
    _, token = _open_session(client)
    r = client.post(
        "/v1/credits/topup",
        headers={"X-VERITAS-SESSION": token},
    )
    assert r.status_code == 402
    body = r.json()
    assert "accepts" in body
    assert body.get("x402Version") == 1


def test_research_with_credits_and_refund_on_unavailable(paid_credits_client, monkeypatch):
    client, main_module, _ = paid_credits_client
    acct, token = _open_session(client)
    # Fund credits without chain: direct ledger grant (tests only).
    main_module.credit_ledger.grant(acct.address, 10_000, note="test_fund")

    from veritas.pipeline import run_research as real_run

    def boom(*args, **kwargs):
        out = real_run(
            *args,
            allow_network=False,
            **{k: v for k, v in kwargs.items() if k != "allow_network"},
        )
        # Force unavailable regardless of offline corpus success path.
        out = dict(out)
        out["status"] = "unavailable"
        out["billable"] = False
        out["refusal_reason"] = "retrieval_unavailable"
        return out

    monkeypatch.setattr(main_module, "run_research", boom)
    r = client.post(
        "/v1/research",
        json={"query": "What is x402?"},
        headers={"X-VERITAS-SESSION": token},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unavailable"
    assert body["billable"] is False
    assert "credits" in body.get("payment", {}).get("mode", "")
    bal = client.get("/v1/credits", headers={"X-VERITAS-SESSION": token}).json()
    assert bal["balance"] == 10_000  # refunded


def test_research_with_credits_success_debits(paid_credits_client, monkeypatch):
    client, main_module, _ = paid_credits_client
    acct, token = _open_session(client)
    main_module.credit_ledger.grant(acct.address, 10_000, note="test_fund")

    monkeypatch.setattr(
        main_module,
        "run_research",
        lambda query, max_results=5, request_id=None, **kw: {
            "request_id": request_id or "x",
            "query": query,
            "status": "completed",
            "billable": True,
            "claims": [],
            "evidence": [],
            "custody_chain": [],
            "custody_root": "0" * 64,
            "custody_valid": True,
            "support": {"n_evidence": 0, "n_claims": 0},
        },
    )
    r = client.post(
        "/v1/research",
        json={"query": "What is x402?"},
        headers={"X-VERITAS-SESSION": token},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["payment"]["mode"] == "credits"
    assert body["payment"]["settled"] is True
    bal = client.get("/v1/credits", headers={"X-VERITAS-SESSION": token}).json()
    assert bal["balance"] == 0  # $0.01 = 10000 atomic on USDC-6


def test_insufficient_credits_402(paid_credits_client):
    client, _, _ = paid_credits_client
    _, token = _open_session(client)
    r = client.post(
        "/v1/research",
        json={"query": "What is x402?"},
        headers={"X-VERITAS-SESSION": token},
    )
    assert r.status_code == 402
    assert r.json()["error"] == "credits_insufficient"


def test_research_deadline_refunds_credits(paid_credits_client, monkeypatch):
    """Credit-paid work that overruns the budget refunds the debit (no charge)."""
    client, main_module, _ = paid_credits_client
    acct, token = _open_session(client)
    main_module.credit_ledger.grant(acct.address, 10_000, note="test_fund")

    from veritas.deadline import Deadline

    # Force the post-work deadline check to fire.
    monkeypatch.setattr(Deadline, "expired", lambda self, now=None: True)
    monkeypatch.setattr(
        main_module,
        "run_research",
        lambda query, max_results=5, request_id=None, **kw: {
            "request_id": request_id or "x",
            "query": query,
            "status": "completed",
            "billable": True,
            "claims": [],
            "evidence": [],
            "custody_chain": [],
            "custody_root": "0" * 64,
            "custody_valid": True,
            "support": {"n_evidence": 0, "n_claims": 0},
        },
    )
    r = client.post(
        "/v1/research",
        json={"query": "What is x402?"},
        headers={"X-VERITAS-SESSION": token},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["error"] == "deadline_exceeded"
    assert body["payment"]["mode"] == "credits"
    assert "refund" in body["payment"]["reason"]
    bal = client.get("/v1/credits", headers={"X-VERITAS-SESSION": token}).json()
    assert bal["balance"] == 10_000


def test_x_payment_path_unchanged_when_present(paid_credits_client, monkeypatch):
    """X-PAYMENT wins over session: no credit debit, money path still settles."""
    client, main_module, control = paid_credits_client
    acct, token = _open_session(client)
    main_module.credit_ledger.grant(acct.address, 10_000, note="test_fund")

    monkeypatch.setattr(
        main_module,
        "run_research",
        lambda query, max_results=5, request_id=None, **kw: {
            "request_id": request_id or "x",
            "query": query,
            "status": "completed",
            "billable": True,
            "claims": [],
            "evidence": [],
            "custody_chain": [],
            "custody_root": "0" * 64,
            "custody_valid": True,
            "support": {"n_evidence": 0, "n_claims": 0},
        },
    )
    r = client.post(
        "/v1/research",
        json={"query": "What is x402?"},
        headers={
            "X-VERITAS-SESSION": token,
            "X-PAYMENT": _payment_header(),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # x402 settlement path, not credits mode
    assert body.get("payment", {}).get("mode") != "credits"
    assert control.settle_calls == 1
    # prepaid balance untouched
    assert main_module.credit_ledger.balance(acct.address) == 10_000


def test_invalid_session_refused(paid_credits_client):
    client, _, _ = paid_credits_client
    r = client.post(
        "/v1/research",
        json={"query": "What is x402?"},
        headers={"X-VERITAS-SESSION": "not-a-real-session"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "session_invalid"


def test_errors_registry_includes_m7_codes(free_client):
    reg = free_client.get("/v1/errors").json()["errors"]
    for code in (
        "credits_insufficient",
        "siwx_invalid",
        "session_invalid",
        "credits_topup_unavailable",
    ):
        assert code in reg


def test_discovery_lists_siwx_and_credits(free_client):
    links = free_client.get("/.well-known/x402").json()["links"]
    for name in ("siwx_challenge", "siwx_verify", "credits", "credits_topup"):
        assert name in links, f"missing discovery link {name}"
        path = links[name]
        # existence: not 404 (POST-only routes may 405 on GET)
        assert free_client.get(path).status_code != 404, f"dead link {name}"

    llms = free_client.get("/llms.txt").text
    for path in (
        "/v1/siwx/challenge",
        "/v1/siwx/verify",
        "/v1/credits",
        "/v1/credits/topup",
        "X-VERITAS-SESSION",
    ):
        assert path in llms
