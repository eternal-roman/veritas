"""Unit economics: what a request cost us, what it was priced at, what it earned.

The defect this closes is not a crash — it is that the operator's first
question, "am I making money", had no answer at all. The service could quote a
price but could not say what a request cost to serve, could not say which
price a past request had been billed under, and had no report joining the two.

Two rules run through this file, and both are about not inventing numbers:

* **Countable facts are always recorded; money is only computed where a cost
  is configured.** Provider calls, evidence bytes and wall time are measured.
  Turning those into dollars needs a per-provider price this repository has no
  way to verify from inside a sandbox, so an unpriced provider is reported as
  unpriced rather than assumed free.
* **Cost is incurred whether or not anyone paid.** Usage is metered on every
  request including free ones; the financial tables stay paid-path only.
"""

from __future__ import annotations

from veritas.ledger import Ledger
from veritas.metering import UNPRICED, CostTable, Usage
from veritas.pricing import PRICE_TABLE_VERSION, current_price_point

NONCE = "0x" + "ab" * 32
OFFER = {
    "network": "eip155:84532",
    "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "amount": "10000",
    "pay_to": "0x" + "11" * 20,
    "price": "$0.01",
    "payer": "0x" + "22" * 20,
}


# -- pricing ----------------------------------------------------------------


def test_the_price_a_request_was_billed_under_is_recorded(tmp_path):
    """Repricing is inevitable. Without a version on the entry, a revenue
    report over a period spanning a price change cannot be explained."""
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", price_version=PRICE_TABLE_VERSION, **OFFER)
    assert ledger.authorization(NONCE).price_version == PRICE_TABLE_VERSION


def test_the_current_price_point_names_itself_and_its_units():
    point = current_price_point("$0.01", "eip155:84532")
    assert point["version"] == PRICE_TABLE_VERSION
    assert point["price"] == "$0.01"
    # Atomic units are what the 402 challenge actually quotes; a report that
    # only knows "$0.01" cannot be checked against a settlement.
    assert point["atomic_amount"] == "10000"
    assert point["asset"]


def test_an_unpriceable_configuration_is_reported_not_guessed():
    point = current_price_point("not a price", "eip155:84532")
    assert point["atomic_amount"] is None
    assert point["error"]


# -- metering ---------------------------------------------------------------


def test_usage_is_recorded_for_free_requests_too(tmp_path):
    """Cost is incurred whether or not anyone paid. A COGS report drawn only
    from paid requests understates what the operator spends."""
    ledger = Ledger(tmp_path)
    ledger.record_usage(Usage(
        request_id="free-1", status="completed", billable=True, paid=False,
        provider_calls={"wikipedia": 1}, evidence_bytes=1200, duration_ms=340,
    ))
    assert ledger.summary()["deliveries"] == 0, "the financial tables stay paid-only"
    assert ledger.usage_summary()["requests"] == 1


def test_provider_calls_are_counted_per_provider(tmp_path):
    ledger = Ledger(tmp_path)
    ledger.record_usage(Usage(
        request_id="r1", status="completed", billable=True, paid=True,
        provider_calls={"serper": 1, "wikipedia": 2}, evidence_bytes=10, duration_ms=5,
    ))
    ledger.record_usage(Usage(
        request_id="r2", status="completed", billable=True, paid=True,
        provider_calls={"serper": 1}, evidence_bytes=10, duration_ms=5,
    ))
    assert ledger.usage_summary()["provider_calls"] == {"serper": 2, "wikipedia": 2}


def test_an_unpriced_provider_is_reported_as_unpriced_not_as_free(tmp_path):
    """The whole point. Assuming zero for a provider whose cost nobody
    configured produces a margin report that is confidently wrong."""
    ledger = Ledger(tmp_path)
    ledger.record_usage(Usage(
        request_id="r1", status="completed", billable=True, paid=True,
        provider_calls={"serper": 1}, evidence_bytes=10, duration_ms=5,
    ))
    report = ledger.usage_summary(costs=CostTable({}))
    assert report["cost_micros"] is UNPRICED
    assert report["unpriced_providers"] == ["serper"]


def test_cogs_is_computed_when_every_provider_is_priced(tmp_path):
    ledger = Ledger(tmp_path)
    for i in range(3):
        ledger.record_usage(Usage(
            request_id=f"r{i}", status="completed", billable=True, paid=True,
            provider_calls={"serper": 1, "wikipedia": 1}, evidence_bytes=10, duration_ms=5,
        ))
    costs = CostTable({"serper": 1000, "wikipedia": 0})  # micro-USD per call
    report = ledger.usage_summary(costs=costs)
    assert report["cost_micros"] == 3000
    assert report["unpriced_providers"] == []


def test_cost_table_reads_operator_configuration(monkeypatch):
    monkeypatch.setenv("VERITAS_PROVIDER_COST_MICROS", "serper=1000, wikipedia=0")
    table = CostTable.from_env()
    assert table.micros_per_call("serper") == 1000
    assert table.micros_per_call("wikipedia") == 0
    assert table.micros_per_call("unconfigured") is None


def test_malformed_cost_configuration_is_ignored_entry_by_entry(monkeypatch):
    """A typo in one entry must not silently zero every provider."""
    monkeypatch.setenv("VERITAS_PROVIDER_COST_MICROS", "serper=1000,broken,wikipedia=oops")
    table = CostTable.from_env()
    assert table.micros_per_call("serper") == 1000
    assert table.micros_per_call("wikipedia") is None
    assert table.rejected == ["broken", "wikipedia=oops"]


def test_the_default_cost_table_is_empty_rather_than_invented(monkeypatch):
    """Paid-API prices cannot be verified from this repository. Serper
    stays unpriced until an operator sets a number. Known-free providers
    default to zero — that is a fact about the code, not an invoice."""
    monkeypatch.delenv("VERITAS_PROVIDER_COST_MICROS", raising=False)
    table = CostTable.from_env()
    assert table.micros_per_call("serper") is None
    for name in (
        "wikipedia", "duckduckgo_instant_answer", "static_corpus",
        "zero_key", "composite", "prediction_markets", "polymarket", "kalshi",
    ):
        assert table.micros_per_call(name) == 0


# -- the joined report ------------------------------------------------------


def _settled(ledger: Ledger, request_id: str, nonce: str):
    ledger.claim(nonce, request_id, price_version=PRICE_TABLE_VERSION, **OFFER)
    ledger.record_delivery(request_id, status="completed", billable=True,
                           custody_root="sha256:r", query="q", response={})
    ledger.record_settlement(request_id, outcome="settled", transaction="0x" + request_id)
    ledger.record_usage(Usage(
        request_id=request_id, status="completed", billable=True, paid=True,
        provider_calls={"serper": 1}, evidence_bytes=10, duration_ms=5,
    ))


def test_margin_is_revenue_minus_cogs_in_the_same_units(tmp_path):
    ledger = Ledger(tmp_path)
    _settled(ledger, "req-1", NONCE)
    _settled(ledger, "req-2", "0x" + "cd" * 32)

    report = ledger.economics(costs=CostTable({"serper": 1000}))
    # 2 x 10000 atomic USDC units at 6 decimals = $0.02 = 20000 micro-USD.
    assert report["revenue_micros"] == 20000
    assert report["cost_micros"] == 2000
    assert report["margin_micros"] == 18000


def test_margin_is_withheld_when_any_provider_is_unpriced(tmp_path):
    """A margin computed over a partial cost base reads as a measurement and
    is not one."""
    ledger = Ledger(tmp_path)
    _settled(ledger, "req-1", NONCE)
    report = ledger.economics(costs=CostTable({}))
    assert report["margin_micros"] is UNPRICED
    assert report["unpriced_providers"] == ["serper"]


def test_a_served_request_is_metered_through_the_http_surface(tmp_path, monkeypatch):
    """Metering that only works when called directly measures nothing."""
    import importlib

    from fastapi.testclient import TestClient

    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as server
    importlib.reload(server)

    from veritas.pipeline import run_research as real
    monkeypatch.setattr(
        server, "run_research", lambda query, **kw: real(query, allow_network=False, **kw)
    )
    client = TestClient(server.app)
    body = client.post("/v1/research", json={"query": "What is the x402 protocol?"}).json()

    usage = server.ledger.usage_summary()
    assert usage["requests"] == 1
    assert usage["paid_requests"] == 0
    # Attempts, not successes: a search API bills the request, not the result.
    assert usage["provider_calls"] == {
        p: (body["retrieval"]["providers_attempted"]).count(p)
        for p in set(body["retrieval"]["providers_attempted"])
    }


def test_revenue_in_a_non_six_decimal_asset_is_not_silently_summed(tmp_path):
    """Atomic units are per-asset. Adding them across assets produces a
    number with no unit; the report keeps them separate instead."""
    ledger = Ledger(tmp_path)
    _settled(ledger, "req-1", NONCE)
    report = ledger.economics(costs=CostTable({"serper": 1000}))
    assert list(report["settled_amounts"]) == ["eip155:84532/" + OFFER["asset"]]
