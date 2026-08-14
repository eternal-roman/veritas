"""Fetching a seller's published surfaces, safely, and judging what came back.

The discipline `veritas/diligence.py` establishes has to survive contact with
the network: a document we could not fetch is one we did not observe, so it
must produce UNVERIFIABLE and never FAIL. A seller must not be able to earn a
clean verdict by being unreachable, nor a damning one by being slow.
"""

from __future__ import annotations

import json

import pytest

from veritas.counterparty import (
    MAX_DOCUMENT_BYTES,
    SellerDocuments,
    evaluate_seller,
    fetch_seller,
)
from veritas.diligence import DiligencePolicy, Verdict
from veritas.safeurl import UnsafeUrlError

BASE = "https://seller.test"
PAY_TO = "0x" + "11" * 20
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def _accepts(pay_to=PAY_TO, amount="10000"):
    return {
        "scheme": "exact", "network": "eip155:8453", "asset": ASSET,
        "payTo": pay_to, "maxAmountRequired": amount,
        "resource": f"{BASE}/v1/research",
        "extra": {"name": "USD Coin", "version": "2"},
    }


DISCOVERY = {
    "x402Version": 1,
    "accepts": [_accepts()],
    "links": {"constitution": "/v1/constitution", "trust": "/v1/trust"},
}

CONSTITUTION = {
    "constitution_version": "2.2",
    "articles": [
        {"id": "A1", "title": "One engine", "statement": "One engine.",
         "scope": "service", "evidence_level": "L1",
         "enforcement": [{"kind": "test", "pointer": "tests/test_integration.py::test_x"}]},
    ],
    "known_gaps": [{"id": "G10", "article": "A11", "status": "open",
                    "description": "self-reported"}],
}

TRUST = {
    "overall": None, "recommendation": "UNPROVEN",
    "basis": {"min_samples": 10,
              "score_source": "independent_audits"},
}


def _fetcher(pages, calls=None):
    """A fetch double. `pages` maps URL -> dict payload or an Exception."""

    def fetch(url: str) -> bytes:
        if calls is not None:
            calls.append(url)
        page = pages.get(url)
        if page is None:
            raise OSError(f"404 {url}")
        if isinstance(page, Exception):
            raise page
        if isinstance(page, (bytes, str)):
            return page.encode() if isinstance(page, str) else page
        return json.dumps(page).encode()

    return fetch


def _healthy(calls=None):
    return _fetcher({
        f"{BASE}/.well-known/x402": DISCOVERY,
        f"{BASE}/v1/constitution": CONSTITUTION,
        f"{BASE}/v1/trust": TRUST,
    }, calls)


def _public(host, port=None, *args, **kwargs):
    """Resolve every host to a public address.

    `safeurl.assert_public_destination` binds `socket.getaddrinfo` as a default
    argument at import time, so monkeypatching the module never reaches it —
    the resolver seam is the only way in, which is why it exists.
    """
    return [(2, 1, 6, "", ("93.184.216.34", 0))]


def _fetch(base=BASE, **kw):
    kw.setdefault("resolver", _public)
    return fetch_seller(base, **kw)


def _evaluate(base=BASE, **kw):
    kw.setdefault("resolver", _public)
    return evaluate_seller(base, **kw)


# -- fetching ---------------------------------------------------------------


def test_fetches_every_published_surface():
    docs = _fetch(fetch=_healthy())
    assert isinstance(docs, SellerDocuments)
    assert docs.discovery is not None
    assert docs.constitution is not None
    assert docs.trust is not None
    assert docs.errors == ()


def test_discovery_links_are_followed_rather_than_paths_guessed():
    """Discovery is self-traversing by design; a seller that publishes its
    constitution somewhere else must still be reachable."""
    calls: list[str] = []
    moved = dict(DISCOVERY, links={"constitution": "/norms", "trust": "/reputation"})
    fetch = _fetcher({
        f"{BASE}/.well-known/x402": moved,
        f"{BASE}/norms": CONSTITUTION,
        f"{BASE}/reputation": TRUST,
    }, calls)

    docs = _fetch(fetch=fetch)
    assert docs.constitution is not None
    assert docs.trust is not None
    assert f"{BASE}/norms" in calls


def test_absolute_links_are_honoured():
    other = "https://norms.seller.test/c"
    fetch = _fetcher({
        f"{BASE}/.well-known/x402": dict(DISCOVERY, links={"constitution": other}),
        other: CONSTITUTION,
    })
    docs = _fetch(fetch=fetch)
    assert docs.constitution is not None


def test_an_unreachable_document_is_recorded_as_an_error_not_as_absent():
    fetch = _fetcher({f"{BASE}/.well-known/x402": DISCOVERY})
    docs = _fetch(fetch=fetch)
    assert docs.constitution is None
    assert any("constitution" in e for e in docs.errors)


def test_unreadable_json_is_an_error_not_a_silent_none():
    fetch = _fetcher({
        f"{BASE}/.well-known/x402": DISCOVERY,
        f"{BASE}/v1/constitution": "{not json",
        f"{BASE}/v1/trust": TRUST,
    })
    docs = _fetch(fetch=fetch)
    assert docs.constitution is None
    assert any("constitution" in e for e in docs.errors)


def test_an_oversized_document_is_refused():
    """A counterparty must not be able to make a buyer read gigabytes."""
    fetch = _fetcher({
        f"{BASE}/.well-known/x402": b"[" + b" " * (MAX_DOCUMENT_BYTES + 1),
    })
    docs = _fetch(fetch=fetch)
    assert docs.discovery is None
    assert any("too large" in e or "discovery" in e for e in docs.errors)


def test_fetch_seller_never_raises_on_a_hostile_seller():
    fetch = _fetcher({f"{BASE}/.well-known/x402": RuntimeError("boom")})
    docs = _fetch(fetch=fetch)
    assert docs.discovery is None
    assert docs.errors


# -- the SSRF guard ---------------------------------------------------------


def test_a_non_http_scheme_is_refused():
    with pytest.raises(UnsafeUrlError):
        fetch_seller("file:///etc/passwd", fetch=_healthy())


def test_a_private_destination_is_refused():
    """The base URL is caller-supplied, so this is the SSRF case: a buyer agent
    told to vet http://169.254.169.254 must not fetch cloud metadata."""
    with pytest.raises(UnsafeUrlError):
        fetch_seller("http://169.254.169.254",
                     fetch=_healthy(),
                     resolver=lambda h, p: [(2, 1, 6, "", ("169.254.169.254", 0))])


def test_a_link_pointing_at_a_private_address_is_refused():
    """A hostile seller must not be able to use its own discovery document to
    steer a buyer's fetcher at the buyer's internal network."""
    fetch = _fetcher({
        f"{BASE}/.well-known/x402": dict(
            DISCOVERY, links={"constitution": "http://127.0.0.1:8000/admin"}),
    })

    def resolver(host, port):
        if host == "127.0.0.1":
            return [(2, 1, 6, "", ("127.0.0.1", 0))]
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    docs = fetch_seller(BASE, fetch=fetch, resolver=resolver)
    assert docs.constitution is None
    assert any("constitution" in e for e in docs.errors)


# -- end to end -------------------------------------------------------------


def test_a_healthy_seller_evaluates_to_pass():
    report = _evaluate(challenge={"accepts": [_accepts()]},
                             fetch=_healthy())
    assert report.verdict == Verdict.PASS, report.reasons


def test_a_seller_we_cannot_reach_is_unverifiable_not_failed():
    """The central discipline, carried into the network layer: being offline
    is not evidence of misconduct."""
    fetch = _fetcher({})
    report = _evaluate(challenge={"accepts": [_accepts()]},
                             fetch=fetch)
    assert report.verdict == Verdict.UNVERIFIABLE
    assert report.verdict != Verdict.FAIL


def test_an_unreachable_seller_cannot_earn_a_pass_by_silence():
    report = _evaluate(fetch=_fetcher({}))
    assert report.verdict != Verdict.PASS


def test_a_reachable_but_contradictory_seller_fails():
    hostile = "0x" + "22" * 20
    report = _evaluate(challenge={"accepts": [_accepts(pay_to=hostile)]},
                             fetch=_healthy())
    assert report.verdict == Verdict.FAIL
    assert any("pay_to" in r for r in report.reasons)


def test_fetch_errors_are_surfaced_in_the_report():
    """A buyer must be able to see *why* a verdict was unverifiable."""
    report = _evaluate(fetch=_fetcher({
        f"{BASE}/.well-known/x402": DISCOVERY,
    }), policy=DiligencePolicy(require_challenge_matches_discovery=False))
    assert report.verdict == Verdict.UNVERIFIABLE
    assert any("could not" in r.lower() or "constitution" in r.lower()
               for r in report.reasons)
