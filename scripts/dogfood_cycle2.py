"""Dogfood cycle 2 — a paying buyer, end to end, both sides real.

The point of a dogfooding cycle is to use the product the way a customer will
and write down what breaks, rather than to assert what we already believe. So
this script drives the *real* buyer path (`veritas.buyer_payment.pay_via_policy`
→ EIP-712 signature over the challenge we actually publish) against the *real*
server, and only the facilitator is a local stand-in.

That stand-in is the honest boundary of this cycle, and it is a real one: the
sandbox this was authored in has no route to Base Sepolia or to any public
facilitator, so **no on-chain settlement is exercised here and none is
claimed**. What is exercised is everything on either side of the facilitator
call: challenge construction, spend-cap enforcement, signing, verification,
the authorization state machine, delivery-before-settle ordering, replay, and
the ledger.

Seven scenarios, chosen because each is a way a real buyer loses money or work:

    happy                       the ordinary path, once
    replay                      the connection drops after settlement (gap G6)
    double_spend                a distinct request on a spent authorization
    settle_timeout              the facilitator never answers (defect R7)
    settle_refused              the facilitator answers no
    buyer_view_indeterminate    what our own published buyer helper concludes
    expired_window              the authorization expires mid-work (defect R4)

The cycle found one defect on its first run, recorded in `double_spend`: a
resubmitted authorization carrying a *different* question was answered 200
with the earlier deliverable. It is fixed, and the scenario now pins the
refusal.

Run it: `python -m scripts.dogfood_cycle2` (or `python scripts/dogfood_cycle2.py`).
It writes a JSON artifact and exits non-zero if any scenario's observed
behaviour differs from what the documentation promises.
"""

from __future__ import annotations

import argparse
import base64
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:  # running as a script rather than a module
    sys.path.insert(0, str(REPO))

# A well-known throwaway key. It holds nothing, on any chain, ever: this
# script never touches a network, and committing a funded key would be the
# exact failure this repository exists to be careful about.
BUYER_KEY = "0x" + "11" * 32

QUERY = "What is the x402 payment protocol?"


def _build_client(tmp: Path, facilitator):
    """A live-mode server whose facilitator is the supplied stand-in."""
    from fastapi.testclient import TestClient

    os.environ.update({
        "VERITAS_RUNTIME_DIR": str(tmp),
        "VERITAS_REQUIRE_PAYMENT": "true",
        "VERITAS_PUBLIC_URL": "https://veritas.example",
        "VERITAS_PAY_TO": "0x" + "22" * 20,
        "VERITAS_NETWORK": "eip155:84532",
        "VERITAS_FACILITATOR": "https://facilitator.invalid",
        "VERITAS_RATE_LIMIT_PER_MINUTE": "0",
        "VERITAS_MAX_PER_REQUEST": "1000000",
        "VERITAS_MAX_PER_DAY": "1000000",
    })
    import veritas.server as server
    importlib.reload(server)
    server.get_facilitator = lambda *a, **k: facilitator

    # Offline retrieval: this cycle is about the money path, and a provider
    # outage would be measuring the sandbox's egress rather than the product.
    calls = {"n": 0}

    def counting(query, **kwargs):
        calls["n"] += 1
        return [
            {
                "venue": "polymarket",
                "market_id": "m-cycle2",
                "question": query,
                "outcomes": [{"name": "Yes", "price": 0.5}],
                "observed_at": "2026-08-17T00:00:00Z",
                "source_url": "https://gamma-api.polymarket.com/markets/m-cycle2",
                "method": "veritas.signals.v1",
                "note": "market-implied prices, not a verdict",
            }
        ]

    server.pull_signals = counting
    return server, TestClient(server.app, raise_server_exceptions=False), calls


class Facilitator:
    """Local stand-in. Verifies structurally; settles however told to."""

    def __init__(self, settle="ok"):
        self.settle_mode = settle
        self.verify_calls = 0
        self.settle_calls = 0

    def verify(self, payload, requirements):
        from veritas.facilitator import VerificationResult
        self.verify_calls += 1
        auth = (payload.get("payload") or {}).get("authorization") or {}
        if not auth.get("nonce") or not (payload.get("payload") or {}).get("signature"):
            return VerificationResult(False, invalid_reason="malformed_payload")
        if payload.get("network") != requirements.get("network"):
            return VerificationResult(False, invalid_reason="network_mismatch")
        if int(auth.get("value", "0")) < int(requirements["maxAmountRequired"]):
            return VerificationResult(False, invalid_reason="insufficient_amount")
        return VerificationResult(True, payer=auth.get("from"))

    def settle(self, payload, requirements):
        from veritas.facilitator import SettlementResult
        self.settle_calls += 1
        auth = (payload.get("payload") or {}).get("authorization") or {}
        if self.settle_mode == "timeout":
            return SettlementResult(False, error_reason="facilitator_timeout")
        if self.settle_mode == "refused":
            return SettlementResult(False, error_reason="insufficient_funds")
        return SettlementResult(
            True,
            transaction="0xlocal-harness-not-onchain-" + (auth.get("nonce") or "")[:10],
            network=requirements.get("network"),
            payer=auth.get("from"),
        )


def _challenge(client) -> dict[str, Any]:
    """Do what a buyer does first: ask, and be told the price."""
    response = client.post("/v1/signals", json={"query": QUERY})
    assert response.status_code == 402, f"expected a challenge, got {response.status_code}"
    return response.json()["accepts"][0]


def _pay(accepts: dict[str, Any], journal: Path, validity_seconds: int = 60) -> str:
    """The real buyer path: validate the challenge, apply caps, sign."""
    from veritas.buyer_payment import default_spend_policy, pay_via_policy

    header, _payload = pay_via_policy(
        accepts, BUYER_KEY,
        policy=default_spend_policy(str(journal)),
        validity_seconds=validity_seconds,
    )
    return header


def _finding(name: str, expected: str, observed: str, ok: bool, **extra) -> dict[str, Any]:
    return {"scenario": name, "expected": expected, "observed": observed,
            "pass": ok, **extra}


def scenario_happy(tmp: Path) -> dict[str, Any]:
    server, client, calls = _build_client(tmp / "happy", Facilitator())
    accepts = _challenge(client)
    header = _pay(accepts, tmp / "happy-journal")
    response = client.post("/v1/signals", json={"query": QUERY},
                           headers={"X-PAYMENT": header})
    body = response.json() if response.status_code == 200 else {}
    request_id = body.get("request_id", "")
    settlements = server.ledger.settlements(request_id) if request_id else []
    auth = server.ledger.authorization(
        json.loads(base64.b64decode(header))["payload"]["authorization"]["nonce"].lower()
    )
    ok = (
        response.status_code == 200
        and body.get("payment", {}).get("settled") is True
        and len(settlements) == 1
        and auth is not None and auth.state == "settled"
        and calls["n"] == 1
    )
    return _finding(
        "happy",
        "200, one settlement recorded, authorization settled, one retrieval pass",
        f"{response.status_code}, settlements={len(settlements)}, "
        f"state={getattr(auth, 'state', None)}, retrievals={calls['n']}",
        ok,
        transaction=settlements[0]["transaction"] if settlements else None,
        revenue_micros=server.ledger.economics()["revenue_micros"],
    )


def scenario_replay(tmp: Path) -> dict[str, Any]:
    """The buyer's connection drops after settlement. They retry the only
    authorization they have — it is single-use on chain, so they cannot sign
    another for the money that already moved."""
    server, client, calls = _build_client(tmp / "replay", Facilitator())
    header = _pay(_challenge(client), tmp / "replay-journal")
    first = client.post("/v1/signals", json={"query": QUERY},
                        headers={"X-PAYMENT": header})
    second = client.post("/v1/signals", json={"query": QUERY},
                         headers={"X-PAYMENT": header})
    same = (
        first.status_code == 200 and second.status_code == 200
        and first.json()["request_id"] == second.json()["request_id"]
        and first.json()["signals"] == second.json()["signals"]
    )
    ok = same and calls["n"] == 1 and second.json()["payment"].get("replayed") is True
    return _finding(
        "replay",
        "200 with the same deliverable, marked replayed, one retrieval pass",
        f"{second.status_code}, same_body={same}, retrievals={calls['n']}, "
        f"replayed={second.json().get('payment', {}).get('replayed')}",
        ok,
    )


def scenario_double_spend(tmp: Path) -> dict[str, Any]:
    """A *different* question on a spent authorization must not be served.

    The first run of this cycle returned 200 with the earlier answer, whose
    only sign of mismatch was the echoed `query` — something a client has no
    reason to inspect on a success. Fixed by binding the authorization to the
    request it bought; recorded here because a cycle that only re-asserts what
    already worked is not a dogfooding cycle.
    """
    server, client, calls = _build_client(tmp / "double", Facilitator())
    header = _pay(_challenge(client), tmp / "double-journal")
    client.post("/v1/signals", json={"query": QUERY}, headers={"X-PAYMENT": header})
    other = client.post("/v1/signals", json={"query": "What is EIP-3009?"},
                        headers={"X-PAYMENT": header})
    ok = (
        other.status_code == 409
        and other.json().get("error") == "payment_authorization_bound_to_another_request"
        and calls["n"] == 1
    )
    return _finding(
        "double_spend",
        "409 payment_authorization_bound_to_another_request; no second retrieval pass",
        f"{other.status_code}, error={other.json().get('error')}, retrievals={calls['n']}",
        ok,
        found_defect=(
            "First run returned 200 with the previous answer; fixed in the same "
            "commit as this cycle."
        ),
    )


def scenario_buyer_reads_an_indeterminate_settlement(tmp: Path) -> dict[str, Any]:
    """Use our own published buyer helper on the awkward response.

    `acceptance_met` is what a buying agent is told to call. On a 200 whose
    settlement is indeterminate it must not report success: the work arrived,
    but whether the buyer paid for it is unknown, and a client that books it as
    paid will under-count what it owes.
    """
    from veritas.buyer_payment import acceptance_met, extract_settlement_proof

    server, client, _calls = _build_client(tmp / "buyerview", Facilitator("timeout"))
    header = _pay(_challenge(client), tmp / "buyerview-journal")
    response = client.post("/v1/signals", json={"query": QUERY},
                           headers={"X-PAYMENT": header})
    body = response.json()
    proof = extract_settlement_proof(body)
    accepted = acceptance_met(response.status_code, proof.get("transaction"))
    ok = accepted is False and body.get("payment", {}).get("state") == "indeterminate"
    return _finding(
        "buyer_view_indeterminate",
        "the published buyer helper reports NOT accepted on an unresolved settlement",
        f"acceptance_met={accepted}, state={body.get('payment', {}).get('state')}",
        ok,
    )


def scenario_settle_timeout(tmp: Path) -> dict[str, Any]:
    """The facilitator never answers. The funds may have moved, so the buyer
    must get their work and the exposure must be recorded, not written off."""
    server, client, _calls = _build_client(tmp / "timeout", Facilitator("timeout"))
    header = _pay(_challenge(client), tmp / "timeout-journal")
    response = client.post("/v1/signals", json={"query": QUERY},
                           headers={"X-PAYMENT": header})
    body = response.json() if response.status_code == 200 else {}
    summary = server.ledger.summary()
    ok = (
        response.status_code == 200
        and body.get("payment", {}).get("state") == "indeterminate"
        and bool(body.get("signals"))
        and summary["indeterminate_count"] == 1
        and summary["failed_count"] == 0
    )
    return _finding(
        "settle_timeout",
        "200 with the deliverable, payment.state=indeterminate, recorded as exposure",
        f"{response.status_code}, state={body.get('payment', {}).get('state')}, "
        f"indeterminate={summary['indeterminate_count']}, failed={summary['failed_count']}",
        ok,
    )


def scenario_settle_refused(tmp: Path) -> dict[str, Any]:
    server, client, _calls = _build_client(tmp / "refused", Facilitator("refused"))
    header = _pay(_challenge(client), tmp / "refused-journal")
    response = client.post("/v1/signals", json={"query": QUERY},
                           headers={"X-PAYMENT": header})
    summary = server.ledger.summary()
    ok = (
        response.status_code == 402
        and response.json().get("error") == "settlement_failed"
        and summary["failed_count"] == 1
        and summary["settled_amounts"] == {}
    )
    return _finding(
        "settle_refused",
        "402 settlement_failed, nothing counted as revenue",
        f"{response.status_code}, error={response.json().get('error')}, "
        f"revenue={summary['settled_amounts']}",
        ok,
    )


def scenario_expired_window(tmp: Path) -> dict[str, Any]:
    """An authorization too short to finish the work must cost the buyer
    nothing: no retrieval pass, no burned nonce."""
    server, client, calls = _build_client(tmp / "expired", Facilitator())
    accepts = _challenge(client)
    header = _pay(accepts, tmp / "expired-journal", validity_seconds=1)
    response = client.post("/v1/signals", json={"query": QUERY},
                           headers={"X-PAYMENT": header})
    summary = server.ledger.summary()
    ok = (
        response.status_code == 402
        and calls["n"] == 0
        and summary["deliveries"] == 0
        and summary["states"] == {}
    )
    return _finding(
        "expired_window",
        "402 challenge, no work done, no authorization claimed",
        f"{response.status_code}, retrievals={calls['n']}, "
        f"authorizations={summary['states']}",
        ok,
    )


SCENARIOS = (
    scenario_happy,
    scenario_replay,
    scenario_double_spend,
    scenario_settle_timeout,
    scenario_settle_refused,
    scenario_buyer_reads_an_indeterminate_settlement,
    scenario_expired_window,
)


def run() -> dict[str, Any]:
    findings = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for scenario in SCENARIOS:
            try:
                findings.append(scenario(tmp))
            except Exception as exc:  # noqa: BLE001 - a crash IS the finding
                findings.append(_finding(
                    scenario.__name__.removeprefix("scenario_"),
                    "the scenario completes",
                    f"raised {type(exc).__name__}: {exc}",
                    False,
                ))
    return {
        "cycle": 2,
        "title": "Paying buyer, end to end",
        "buyer_path": "veritas.buyer_payment.pay_via_policy (real EIP-712 signing)",
        "facilitator": "local stand-in — NO on-chain settlement was performed",
        "retrieval": "offline corpus, so the money path is what is measured",
        "scenarios": findings,
        "passed": sum(1 for f in findings if f["pass"]),
        "total": len(findings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="Write the JSON report here as well as stdout.")
    args = parser.parse_args(argv)

    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
