"""Zero-key multi-source retrieval for fully agent-native operation.

Uses only free, no-API-key sources:
- Wikipedia REST API
- DuckDuckGo via the optional `ddgs` package, falling back to the Instant
  Answer endpoint

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

from veritas import __version__
from veritas.retrieval import RetrievalError, RetrievalResult, classify_transport_error

USER_AGENT = f"VeritasAgent/{__version__} (+https://github.com/eternal-roman/veritas)"
TIMEOUT_SECONDS = 8


def _classify(exc: Exception) -> tuple[str, str]:
    """Map an exception onto a stable (error_type, detail) pair."""
    return classify_transport_error(exc, TIMEOUT_SECONDS)


def _get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode())


def wikipedia_summary(query: str, limit: int = 2) -> RetrievalResult:
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

    for item in data.get("query", {}).get("search", [])[:limit]:
        title = item.get("title", "")
        if not title:
            continue
        try:
            summary_url = (
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(title, safe="")
            )
            sdata = _get_json(summary_url)
            extract = sdata.get("extract") or ""
            page_url = (
                sdata.get("content_urls", {}).get("desktop", {}).get("page")
                or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title, safe='')}"
            )
        except Exception as exc:  # noqa: BLE001
            etype, detail = _classify(exc)
            result.errors.append(RetrievalError("wikipedia", etype, f"{title}: {detail}"))
            continue

        if extract:
            result.sources.append({
                "url": page_url,
                "title": title,
                "text": extract[:800],
                "provider": "wikipedia",
                "provenance": "live_fetch",
            })

    # The search call itself succeeded, so the provider is reachable even if
    # individual page fetches failed or the topic genuinely has no article.
    result.providers_succeeded.append("wikipedia")
    return result


def duckduckgo_search(query: str, max_results: int = 4) -> RetrievalResult:
    result = RetrievalResult(providers_attempted=["duckduckgo"])

    try:
        from ddgs import DDGS
    except ImportError:
        result.errors.append(RetrievalError(
            "duckduckgo", "dependency_missing",
            "ddgs not installed; falling back to Instant Answer API",
        ))
    else:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    text = (r.get("body") or r.get("snippet") or "")[:600]
                    url = r.get("href") or r.get("link") or ""
                    if text and url:
                        result.sources.append({
                            "url": url,
                            "title": r.get("title") or "",
                            "text": text,
                            "provider": "duckduckgo",
                            "provenance": "live_fetch",
                        })
            result.providers_succeeded.append("duckduckgo")
            return result
        except Exception as exc:  # noqa: BLE001
            etype, detail = _classify(exc)
            result.errors.append(RetrievalError("duckduckgo", etype, detail))

    # Fallback: keyless Instant Answer endpoint.
    try:
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({
            "q": query, "format": "json", "no_html": 1,
        })
        data = _get_json(url)
    except Exception as exc:  # noqa: BLE001
        etype, detail = _classify(exc)
        result.errors.append(RetrievalError("duckduckgo_ia", etype, detail))
        return result

    abstract = data.get("Abstract")
    if abstract:
        result.sources.append({
            "url": data.get("AbstractURL") or "https://duckduckgo.com",
            "title": data.get("Heading") or query,
            "text": abstract[:600],
            "provider": "duckduckgo_ia",
            "provenance": "live_fetch",
        })
    result.providers_succeeded.append("duckduckgo_ia")
    return result


class ZeroKeyRetriever:
    """Retriever facade over the keyless providers."""

    name = "zero_key"

    def retrieve(self, query: str, max_results: int = 5) -> RetrievalResult:
        merged = RetrievalResult()
        seen = set()

        for sub in (wikipedia_summary(query, limit=2),
                    duckduckgo_search(query, max_results=max_results)):
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


def free_retrieve(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Backwards-compatible entry point returning bare source dicts.

    Prefer ZeroKeyRetriever.retrieve() — this helper discards the error
    channel, which is exactly the information the pipeline needs.
    """
    return ZeroKeyRetriever().retrieve(query, max_results=max_results).sources


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
