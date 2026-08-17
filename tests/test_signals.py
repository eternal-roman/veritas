"""Prediction-market snapshots: prices stored as evidence, not verdicts."""

from __future__ import annotations

import importlib
import json
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient

from veritas.evidence_store import EvidenceStore
from veritas.hashing import compute_content_hash
from veritas.signals import (
    ALLOWED_HOSTS,
    METHOD,
    VENUE_ENDPOINTS,
    SignalsError,
    SignalStore,
    analyze,
    as_evidence,
    fetch_json,
    hash_signal,
    pull,
    pull_kalshi,
    pull_polymarket,
)

POLYMARKET_SEARCH = {
    "events": [
        {
            "markets": [
                {
                    "id": "m-fed",
                    "question": "Will the Fed cut rates in October?",
                    "outcomes": '["Yes", "No"]',
                    "outcomePrices": '["0.42", "0.58"]',
                    "volumeNum": 1234.5,
                    "closed": False,
                    "endDate": "2026-10-31T00:00:00Z",
                }
            ]
        }
    ]
}

KALSHI_MARKETS = {
    "markets": [
        {
            "ticker": "FED-24OCT",
            "title": "Fed funds rate decision October",
            "last_price": 42,
            "status": "open",
            "volume": 900,
            "close_time": "2026-10-31T00:00:00Z",
        },
        {
            "ticker": "RAIN-NYC",
            "title": "Rain in New York tomorrow",
            "last_price": 10,
            "status": "open",
        },
    ]
}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener_for(*payloads):
    queue = list(payloads)

    def open_url(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if "127.0.0.1" in url or "169.254." in url:
            raise SignalsError("venue_host_refused:internal")
        if not queue:
            raise URLError("no more fixtures")
        return _FakeResponse(queue.pop(0))

    return open_url


def test_empty_query_and_unknown_venue_are_refused():
    with pytest.raises(SignalsError, match="query_empty"):
        pull("   ")
    with pytest.raises(SignalsError, match="venue_unknown:betfair"):
        pull("fed", venues=["betfair"])


def test_off_allowlist_host_is_refused():
    with pytest.raises(SignalsError, match="venue_host_refused"):
        fetch_json("https://evil.example/markets")
    with pytest.raises(SignalsError, match="venue_url_refused"):
        fetch_json("file:///etc/passwd")
    assert ALLOWED_HOSTS == frozenset(
        spec["host"] for spec in VENUE_ENDPOINTS.values()
    )


def test_pull_polymarket_normalizes_and_hashes():
    signals = pull_polymarket("fed", opener=_opener_for(POLYMARKET_SEARCH))
    assert len(signals) == 1
    item = signals[0]
    assert item["venue"] == "polymarket"
    assert item["method"] == METHOD
    assert item["note"] == "market-implied prices, not a verdict"
    assert item["outcomes"][0] == {"name": "Yes", "price": 0.42}
    assert item["content_hash"] == hash_signal(item)
    assert item["content_hash"].startswith("sha256:")


def test_pull_kalshi_clamps_cents_and_filters():
    signals = pull_kalshi("fed", opener=_opener_for(KALSHI_MARKETS))
    assert len(signals) == 1
    item = signals[0]
    assert item["market_id"] == "FED-24OCT"
    assert item["outcomes"][0]["price"] == 0.42
    assert item["outcomes"][1]["price"] == pytest.approx(0.58)


def test_pull_kalshi_does_not_dump_the_book_on_short_tokens():
    """A query that matches nothing must not return unfiltered open markets."""
    signals = pull_kalshi("zz", opener=_opener_for(KALSHI_MARKETS))
    assert signals == []
    signals = pull_kalshi("x", opener=_opener_for(KALSHI_MARKETS))
    assert signals == []


def test_kalshi_last_price_one_is_one_cent_not_certainty():
    """Kalshi last_price is cents. 1 must be 0.01, not 1.00 (review-2)."""
    payload = {
        "markets": [
            {
                "ticker": "ONE-CENT",
                "title": "One cent last trade",
                "last_price": 1,
                "status": "open",
            }
        ]
    }
    signals = pull_kalshi("cent", opener=_opener_for(payload))
    assert len(signals) == 1
    assert signals[0]["outcomes"][0]["price"] == 0.01
    assert signals[0]["outcomes"][1]["price"] == pytest.approx(0.99)


def test_kalshi_prefers_dollars_fields_over_cents():
    payload = {
        "markets": [
            {
                "ticker": "USD-FIELD",
                "title": "Dollars field wins",
                "last_price": 42,
                "last_price_dollars": "0.17",
                "status": "open",
            }
        ]
    }
    signals = pull_kalshi("dollars", opener=_opener_for(payload))
    assert signals[0]["outcomes"][0]["price"] == 0.17


def test_signal_store_lands_in_evidence_store(tmp_path):
    """The structured snapshot hashes to the body we store — GET /v1/evidence
    can serve it. Hashing the document *with* content_hash used to make
    EvidenceStore.put refuse the write."""
    store = SignalStore(tmp_path)
    signals = pull_polymarket("fed", opener=_opener_for(POLYMARKET_SEARCH))
    digest = store.put(signals[0])
    assert digest == signals[0]["content_hash"]
    loaded = store.get(digest)
    assert loaded["question"] == signals[0]["question"]
    evidence = EvidenceStore(tmp_path).get(digest)
    assert evidence is not None
    assert evidence["excerpt"]
    # excerpt is the canonical body *without* content_hash
    assert compute_content_hash(evidence["excerpt"]) == digest
    assert store.get("../etc/passwd") is None


def test_as_evidence_is_not_a_verdict_and_uses_license():
    signals = pull_polymarket("fed", opener=_opener_for(POLYMARKET_SEARCH))
    item = as_evidence(signals[0])
    assert "Not a verdict" in item["text"]
    assert item["license"]["id"] == "venue-terms"
    assert item["provider"] == "polymarket"
    assert "licence" not in item


def test_venue_unavailable_is_not_an_empty_catalog():
    with pytest.raises(SignalsError, match="venue"):
        pull_polymarket("fed", opener=_opener_for())


def test_venue_unavailable_is_not_settled(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "ab" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")
    import veritas.server as server

    importlib.reload(server)
    monkeypatch.setattr(
        server,
        "pull_signals",
        lambda *a, **k: (_ for _ in ()).throw(SignalsError("venues_unavailable:down")),
    )
    client = TestClient(server.app)
    # Unpaid: 402, no catalog invented.
    unpaid = client.post("/v1/signals", json={"query": "fed"})
    assert unpaid.status_code == 402


def test_raising_opener_becomes_signals_error():
    def boom(request, timeout=None):
        raise URLError("down")

    with pytest.raises(SignalsError):
        pull_kalshi("fed", opener=boom)


def test_pull_caps_limit():
    many = {
        "events": [
            {
                "markets": [
                    {
                        "id": f"m-{i}",
                        "question": f"Fed item {i}",
                        "outcomes": '["Yes", "No"]',
                        "outcomePrices": '["0.4", "0.6"]',
                        "closed": False,
                    }
                    for i in range(20)
                ]
            }
        ]
    }
    signals = pull_polymarket("fed", limit=3, opener=_opener_for(many))
    assert len(signals) <= 3


def test_catalog_response_conforms_to_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    fixtures = pull_polymarket("fed", opener=_opener_for(POLYMARKET_SEARCH))
    import veritas.server as server

    importlib.reload(server)
    monkeypatch.setattr(server, "pull_signals", lambda *a, **k: fixtures)
    client = TestClient(server.app)
    body = client.post("/v1/signals", json={"query": "fed", "venues": ["polymarket"]}).json()
    assert body["method"] == METHOD
    assert "not a verdict" in body["note"]
    assert isinstance(body["signals"], list)
    assert "analysis" in body


def test_snapshots_state_they_are_not_verdicts():
    signals = pull_polymarket("fed", opener=_opener_for(POLYMARKET_SEARCH))
    assert all("not a verdict" in item["note"] for item in signals)


def test_live_mode_unpaid_pull_returns_402(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "ab" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")
    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app)
    response = client.post("/v1/signals", json={"query": "fed"})
    assert response.status_code == 402
    accepts = response.json().get("accepts") or []
    assert accepts
    assert "/v1/signals" in str(accepts[0].get("resource") or "")


def test_http_pull_persists_and_lists(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    fixtures = pull_polymarket("fed", opener=_opener_for(POLYMARKET_SEARCH))

    import veritas.server as server

    monkeypatch.setattr(server, "pull_signals", lambda *a, **k: fixtures)
    importlib.reload(server)
    monkeypatch.setattr(server, "pull_signals", lambda *a, **k: fixtures)
    client = TestClient(server.app)
    pulled = client.post("/v1/signals", json={"query": "fed", "venues": ["polymarket"]})
    assert pulled.status_code == 200, pulled.text
    body = pulled.json()
    assert body["method"] == METHOD
    assert body["signals"]
    assert "analysis" in body
    assert body["analysis"]["note"].startswith("arithmetic")
    assert body["analysis"]["n_signals"] == len(body["signals"])
    digest = body["signals"][0]["content_hash"]
    fetched = client.get(f"/v1/signals/{digest}")
    assert fetched.status_code == 200
    assert fetched.json()["question"]
    listed = client.get("/v1/signals")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1
    hist = client.get(
        "/v1/signals/history",
        params={"venue": "polymarket", "market_id": body["signals"][0]["market_id"]},
    )
    assert hist.status_code == 200
    assert hist.json()["count"] >= 1
    assert hist.json()["analysis"]["n_signals"] >= 1
    evidence = client.get(f"/v1/evidence/{digest}")
    assert evidence.status_code == 200
    empty = client.post("/v1/signals", json={"query": ""})
    assert empty.status_code == 422
    unknown = client.post("/v1/signals", json={"query": "fed", "venues": ["betfair"]})
    assert unknown.status_code == 422
    assert client.get("/v1/signals/not-a-hash").status_code == 404
    bad_hist = client.get(
        "/v1/signals/history", params={"venue": "betfair", "market_id": "x"}
    )
    assert bad_hist.status_code == 422


def test_polymarket_search_miss_does_not_dump_the_book():
    empty = {"events": [], "markets": []}
    signals = pull_polymarket("nomatch", opener=_opener_for(empty))
    assert signals == []


def test_kalshi_pages_cursor_until_match(tmp_path):
    page1 = {
        "markets": [
            {
                "ticker": "RAIN-NYC",
                "title": "Rain in New York tomorrow",
                "last_price": 10,
                "status": "open",
            }
        ],
        "cursor": "page-2",
    }
    page2 = {
        "markets": [
            {
                "ticker": "FED-24OCT",
                "title": "Fed funds rate decision October",
                "last_price": 42,
                "status": "open",
            }
        ],
        "cursor": "",
    }
    signals = pull_kalshi("fed", opener=_opener_for(page1, page2))
    assert len(signals) == 1
    assert signals[0]["market_id"] == "FED-24OCT"


def test_catalog_list_is_latest_per_market_and_searchable(tmp_path):
    store = SignalStore(tmp_path)
    first = {
        "venue": "polymarket",
        "market_id": "m-fed",
        "question": "Will the Fed cut rates in October?",
        "outcomes": [{"name": "Yes", "price": 0.40}],
        "observed_at": "2026-08-01T00:00:00Z",
        "source_url": "https://gamma-api.polymarket.com/markets/m-fed",
        "method": METHOD,
        "note": "market-implied prices, not a verdict",
    }
    second = dict(first)
    second["outcomes"] = [{"name": "Yes", "price": 0.55}]
    second["observed_at"] = "2026-08-02T00:00:00Z"
    other = {
        "venue": "kalshi",
        "market_id": "RAIN-NYC",
        "question": "Rain in New York tomorrow",
        "outcomes": [{"name": "Yes", "price": 0.10}],
        "observed_at": "2026-08-02T00:00:00Z",
        "source_url": "https://external-api.kalshi.com/trade-api/v2/markets/RAIN-NYC",
        "method": METHOD,
        "note": "market-implied prices, not a verdict",
    }
    assert store.put(first)
    assert store.put(second)
    assert store.put(other)
    listed = store.list()
    assert len(listed) == 2
    fed = next(item for item in listed if item["market_id"] == "m-fed")
    assert fed["outcomes"][0]["price"] == 0.55
    searched = store.list(q="fed")
    assert len(searched) == 1
    assert searched[0]["market_id"] == "m-fed"
    hist = store.history(venue="polymarket", market_id="m-fed")
    assert [row["observed_at"] for row in hist] == [
        "2026-08-02T00:00:00Z",
        "2026-08-01T00:00:00Z",
    ]


def test_ingest_watchlist_stores(tmp_path, monkeypatch):
    from veritas.signals import ingest

    store = SignalStore(tmp_path)
    monkeypatch.delenv("VERITAS_SIGNALS_WATCHLIST", raising=False)
    report = ingest(
        ["fed"],
        venues=["polymarket"],
        opener=_opener_for(POLYMARKET_SEARCH),
        store=store,
    )
    assert report["stored"] == 1
    assert report["pulled"] == 1
    assert store.list(q="fed")


def test_analyze_is_arithmetic_not_a_forecast():
    signals = pull_polymarket("fed", opener=_opener_for(POLYMARKET_SEARCH))
    report = analyze(signals)
    assert report["method"] == "veritas.signals.analyze.v1"
    assert "not a forecast" in report["note"]
    assert report["n_signals"] == len(signals)
    assert report["markets"]
    assert report["markets"][0]["price_mean"] == 0.42

