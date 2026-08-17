"""L1: guided buyer journey — discover → diligence → pay-surface, no settle."""

from __future__ import annotations

import json

from veritas.buyer_journey import (
    EXIT_DILIGENCE_FAIL,
    EXIT_OK,
    EXIT_UNVERIFIABLE,
    main,
    probe_research_pay_surface,
    run_buyer_journey,
)
from veritas.diligence import DiligencePolicy, Verdict
from veritas.hashing import compute_content_hash

BASE = "https://seller.example"
PAY_TO = "0x" + "11" * 20
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def _public(host, port=None, *args, **kwargs):
    return [(2, 1, 6, "", ("93.184.216.34", 0))]


def _fetch_map():
    """Coherent seller surfaces matching counterparty diligence fixtures."""
    discovery = {
        "x402Version": 1,
        "accepts": [{
            "scheme": "exact",
            "network": "eip155:8453",
            "asset": ASSET,
            "payTo": PAY_TO,
            "maxAmountRequired": "10000",
            "resource": f"{BASE}/v1/signals",
            "extra": {"name": "USD Coin", "version": "2"},
        }],
        "links": {"constitution": "/v1/constitution", "trust": "/v1/trust"},
    }
    constitution = {
        "constitution_version": "2.2",
        "articles": [
            {
                "id": "A1",
                "title": "One engine",
                "statement": "One engine.",
                "scope": "service",
                "evidence_level": "L1",
                "enforcement": [{
                    "kind": "test",
                    "pointer": "tests/test_integration.py::test_x",
                }],
            }
        ],
        "known_gaps": [{
            "id": "G10",
            "article": "A11",
            "status": "open",
            "description": "self-reported",
        }],
    }
    trust = {
        "overall": None,
        "recommendation": "UNPROVEN",
        "basis": {
            "min_samples": 10,
            "score_source": "independent_audits",
        },
    }
    table = {
        f"{BASE}/.well-known/x402": discovery,
        f"{BASE}/v1/constitution": constitution,
        f"{BASE}/v1/trust": trust,
    }

    def fetch(url: str) -> bytes:
        if url not in table:
            raise OSError(f"missing fixture {url}")
        return json.dumps(table[url]).encode("utf-8")

    return fetch


def _exchange_402(url: str, **kwargs) -> dict:
    if url.endswith("/v1/signals") and kwargs.get("method") == "POST":
        body = json.dumps({
            "x402Version": 1,
            "accepts": [{"scheme": "exact", "network": "eip155:84532"}],
        }).encode("utf-8")
        return {"status": 402, "body": body, "error": None}
    if url.endswith("/.well-known/x402") or "/v1/" in url:
        # unused when fetch inject used
        return {"status": 200, "body": b"{}", "error": None}
    return {"status": 404, "body": b"{}", "error": None}


def _exchange_free(url: str, **kwargs) -> dict:
    if url.endswith("/v1/signals") and kwargs.get("method") == "POST":
        body = json.dumps({
            "status": "supported",
            "request_id": "req-free-1",
            "content_hash": compute_content_hash("hello"),
            "billable": False,
        }).encode("utf-8")
        return {"status": 200, "body": body, "error": None}
    return {"status": 404, "body": b"{}", "error": None}


def test_journey_402_pay_surface_not_settled():
    report = run_buyer_journey(
        BASE,
        fetch=_fetch_map(),
        exchange=_exchange_402,
        resolver=_public,
        policy=DiligencePolicy(
            require_challenge_matches_discovery=False,
        ),
    )
    assert report["schema"] == "veritas.buyer_journey.v0"
    assert report["not_settled"] is True
    assert report["diligence_verdict"] in (Verdict.PASS, Verdict.UNVERIFIABLE)
    steps = {s["step"]: s for s in report["steps"]}
    assert steps["discover"]["ok"] is True
    assert steps["pay_surface_probe"]["payment_required"] is True
    assert steps["pay_surface_probe"]["accepts_count"] == 1
    assert steps["pay_surface_probe"]["not_settled"] is True
    assert "paid settlement" in report["not_proven"]


def test_journey_free_mode_exposes_hash_path():
    report = run_buyer_journey(
        BASE,
        fetch=_fetch_map(),
        exchange=_exchange_free,
        resolver=_public,
        policy=DiligencePolicy(require_challenge_matches_discovery=False),
    )
    steps = {s["step"]: s for s in report["steps"]}
    assert steps["pay_surface_probe"]["payment_required"] is False
    fr = steps["pay_surface_probe"]["free_response"]
    assert fr["request_id"] == "req-free-1"
    assert fr["content_hash"]


def test_journey_content_hash_mismatch_is_not_ok():
    """verify_content_hash returns (bool, meta). bool(tuple) is always True —
    the journey must unpack the first element."""
    report = run_buyer_journey(
        BASE,
        fetch=_fetch_map(),
        exchange=_exchange_free,
        resolver=_public,
        policy=DiligencePolicy(require_challenge_matches_discovery=False),
        content="this is not hello",
        content_hash=compute_content_hash("hello"),
    )
    steps = {s["step"]: s for s in report["steps"]}
    verify = steps["verify_content_hash"]
    assert verify["ok"] is False
    assert verify["matched"] is False


def test_probe_research_records_network_error():
    def bad_exchange(url, **kwargs):
        return {"status": None, "body": b"", "error": "URLError: down"}

    out = probe_research_pay_surface(
        BASE, "q", exchange=bad_exchange, resolver=_public
    )
    assert out["ok"] is False
    assert out["not_settled"] is True
    assert "URLError" in (out.get("error") or "")


def test_cli_json_and_exit(capsys):
    # Inject via monkeypatch of module internals through run path — call main
    # with skip and fixtures by patching run_buyer_journey is heavy; use
    # subprocess-free main with allow-private would hit network. Unit path:
    from veritas import buyer_journey as bj

    captured = {}

    def fake_run(url, **kwargs):
        captured["url"] = url
        return {
            "schema": "veritas.buyer_journey.v0",
            "base_url": url,
            "diligence_verdict": "pass",
            "steps": [],
            "errors": [],
            "exit_hint": EXIT_OK,
            "not_proven": [],
            "not_settled": True,
        }

    orig = bj.run_buyer_journey
    bj.run_buyer_journey = fake_run  # type: ignore[assignment]
    try:
        code = main(["https://seller.example", "--query", "x"])
    finally:
        bj.run_buyer_journey = orig  # type: ignore[assignment]
    assert code == EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out["not_settled"] is True
    assert captured["url"] == "https://seller.example"


def test_exit_hints_constants_stable():
    assert EXIT_OK == 0
    assert EXIT_DILIGENCE_FAIL == 1
    assert EXIT_UNVERIFIABLE == 2
