"""Zero-key multi-source retrieval for fully agent-native operation.

Uses only free, no-API-key sources:
- Wikipedia MediaWiki Extracts API (official ``prop=extracts&explaintext=1``)
- DuckDuckGo Instant Answer API (keyless)

Search hits that are only a snippet stay labelled ``search_snippet``.
Wikipedia extracts are the publisher's own plaintext. Full-page bodies
for other URLs go through ``notary.observe`` on the served path
(``observe_urls``, default on) — not a second scraper.

Every failure path records a RetrievalError instead of silently returning an
empty list. The previous version wrapped all network access in bare
`except Exception: pass`, which meant a proxy rejection, a missing dependency
and a genuinely empty result were indistinguishable to the caller — and the
service would then tell a paying agent "no evidence exists" when it had in
fact never reached the network.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from veritas.retrieval import (
    UNKNOWN_LICENSE,
    USER_AGENT,
    RetrievalError,
    RetrievalResult,
    classify_transport_error,
)
from veritas.safeurl import require_http_url

TIMEOUT_SECONDS = 8

#: Official MediaWiki extracts can be the whole article (tens of KB). Cap
#: so one article cannot dominate a paid request's evidence budget. 4000
#: is well above the REST summary (~400–800) and below a full dump.
WIKIPEDIA_EXTRACT_CHARS = 4000


def _classify(exc: Exception) -> tuple[str, str]:
    """Map an exception onto a stable (error_type, detail) pair."""
    return classify_transport_error(exc, TIMEOUT_SECONDS)


def _get_json(url: str) -> dict[str, Any]:
    # Hardcoded provider hosts today, but urlopen honours file: and custom
    # schemes, so the allowlist is enforced at the call rather than assumed.
    req = urllib.request.Request(require_http_url(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(  # nosec B310 - scheme checked by require_http_url
            req, timeout=TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode())


def wikipedia_summary(query: str, limit: int = 2) -> RetrievalResult:
    """Wikipedia via the official MediaWiki Extracts API.

    ``action=query&prop=extracts&explaintext=1`` is the documented plaintext
    extract (https://www.mediawiki.org/wiki/Extension:TextExtracts). This
    replaces the REST ``page/summary`` endpoint, which is a lead-paragraph
    snippet by design.

    MediaWiki booleans are true if the parameter is *present* at all, so
    ``exintro`` is omitted (sending ``exintro=0`` would still request the
    lead only). Multiple extracts are only returned when ``exintro`` is
    set, so each title is fetched on its own request.
    """
    result = RetrievalResult(providers_attempted=["wikipedia"])
    try:
        search_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": limit,
        })
        data = _get_json(search_url)
    except Exception as exc:  # noqa: BLE001 - classified and surfaced below
        etype, detail = _classify(exc)
        result.errors.append(RetrievalError("wikipedia", etype, detail))
        return result

    titles = [
        item.get("title", "")
        for item in data.get("query", {}).get("search", [])[:limit]
        if item.get("title")
    ]
    if not titles:
        result.providers_succeeded.append("wikipedia")
        return result

    extracted_any = False
    for title in titles:
        try:
            page = _wikipedia_extract_page(title)
        except Exception as exc:  # noqa: BLE001
            etype, detail = _classify(exc)
            result.errors.append(RetrievalError("wikipedia", etype, detail))
            continue
        if page is None:
            continue
        extracted_any = True
        extract = (page.get("extract") or "").strip()
        if not extract:
            continue
        page_url = (
            page.get("fullurl")
            or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title, safe='')}"
        )
        result.sources.append(_wikipedia_source(title, extract, page_url))

    if extracted_any or not result.errors:
        result.providers_succeeded.append("wikipedia")
    return result


def _wikipedia_extract_page(title: str) -> dict[str, Any] | None:
    """One title, one extract. ``exintro`` is deliberately absent.

    TextExtracts will not return more than one full-article extract per
    request. Sending ``exintro`` at all (even as 0) requests the lead
    only — MediaWiki treats a present boolean as true.
    """
    extract_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query",
        "prop": "extracts|info",
        "explaintext": 1,
        "inprop": "url",
        "redirects": 1,
        "format": "json",
        "titles": title,
    })
    extracted = _get_json(extract_url)
    pages = (extracted.get("query") or {}).get("pages") or {}
    if not isinstance(pages, dict):
        return None
    for page in pages.values():
        if isinstance(page, dict) and page.get("extract"):
            return page
    return None


def _wikipedia_source(title: str, extract: str, page_url: str) -> dict:
    """Build a Wikipedia source carrying the licence its text is under.

    Wikipedia article text is CC BY-SA. Reusing it commercially is permitted;
    reusing it *silently* is not. Shipping the licence with the excerpt lets a
    buying agent know what obligations attach to text it is about to reuse.
    """
    return {
        "url": page_url,
        "title": title,
        "text": extract[:WIKIPEDIA_EXTRACT_CHARS],
        "provider": "wikipedia",
        "provenance": "wikipedia_extract",
        "license": {
            "id": "CC-BY-SA-4.0",
            "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        },
        "attribution": {
            "required": True,
            "text": f"Wikipedia contributors, \"{title}\", {page_url}",
        },
    }


def duckduckgo_instant_answer(query: str, max_results: int = 4) -> RetrievalResult:
    """DuckDuckGo's keyless Instant Answer API — one engine, named truthfully.

    This replaces a `ddgs` call that ran on the library's `auto` backend, which
    shuffles across google, bing, yandex, brave, yahoo, startpage and mojeek and
    scrapes their result pages. Every result was then labelled
    `provider: "duckduckgo"`. That is both a redistribution problem and, in a
    product selling provenance, a falsified provenance label. The Instant Answer
    API is a documented keyless endpoint, and the answers it returns credit the
    publisher they came from. The abstract is a snippet; the served path
    re-observes ``AbstractURL`` through notary.observe when observe_urls is on.
    """
    result = RetrievalResult(providers_attempted=["duckduckgo_instant_answer"])
    try:
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({
            "q": query, "format": "json", "no_html": 1,
        })
        data = _get_json(url)
    except Exception as exc:  # noqa: BLE001
        etype, detail = _classify(exc)
        result.errors.append(RetrievalError("duckduckgo_instant_answer", etype, detail))
        return result

    abstract = data.get("Abstract")
    if abstract:
        # AbstractSource names the underlying publisher; dropping it (as the
        # previous version did) discards the attribution the API asks us to keep.
        publisher = data.get("AbstractSource") or "DuckDuckGo Instant Answer"
        abstract_url = data.get("AbstractURL") or "https://duckduckgo.com"
        result.sources.append({
            "url": abstract_url,
            "title": data.get("Heading") or query,
            "text": abstract[:600],
            "provider": "duckduckgo_instant_answer",
            "provenance": "search_snippet",
            "license": dict(UNKNOWN_LICENSE),
            "attribution": {
                "required": True,
                "text": f"{publisher}, via DuckDuckGo Instant Answer, {abstract_url}",
            },
        })
    result.providers_succeeded.append("duckduckgo_instant_answer")
    return result


class ZeroKeyRetriever:
    """Retriever facade over the keyless providers."""

    name = "zero_key"

    def retrieve(self, query: str, max_results: int = 5) -> RetrievalResult:
        merged = RetrievalResult()
        seen = set()

        for sub in (wikipedia_summary(query, limit=2),
                    duckduckgo_instant_answer(query, max_results=max_results)):
            merged.providers_attempted.extend(sub.providers_attempted)
            merged.providers_succeeded.extend(sub.providers_succeeded)
            merged.errors.extend(sub.errors)
            for src in sub.sources:
                url = src.get("url") or ""
                if url and url not in seen:
                    seen.add(url)
                    merged.sources.append(src)

        merged.sources = merged.sources[:max_results]
        return merged


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "x402 protocol"
    res = ZeroKeyRetriever().retrieve(q)
    print(f"providers ok: {res.providers_succeeded} | errors: {len(res.errors)}")
    for err in res.errors:
        print(f"  ! {err.provider}: {err.error_type} - {err.detail}")
    for r in res.sources:
        print(r["title"], "-", r["url"])
        print(r["text"][:150], "...\n")
