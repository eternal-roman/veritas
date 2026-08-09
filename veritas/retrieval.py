"""Retrieval abstraction with explicit failure semantics.

The central contract: a retriever must never conflate "I found no evidence"
with "I could not reach my sources". Veritas sells epistemic assurance, so
reporting `no_evidence` when the real cause was a network failure is a
correctness bug, not a cosmetic one — it tells a paying agent that a claim is
unsupported when the truth is that we never looked.

Every retriever therefore returns a RetrievalResult carrying both the sources
it found and the errors it hit, and the pipeline decides what that combination
means.
"""

from __future__ import annotations

import json
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Protocol

from veritas import __version__

#: Shared identity for the retrieval tiers. Load-bearing (AGENTS.md field
#: note 1): Cloudflare-fronted providers 403 the default Python-urllib agent,
#: so every outbound retrieval client sends a versioned UA — defined once here
#: so the tiers cannot fork it.
USER_AGENT = f"VeritasAgent/{__version__} (+https://github.com/eternal-roman/veritas)"

# Tokens that carry no retrieval signal; matching on these made the previous
# relevance filter accept essentially any query against any document.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "how", "in", "is", "it", "of", "on", "or", "that", "the", "to",
    "was", "what", "when", "where", "which", "who", "why", "with", "will",
})

# A query must overlap a document by at least this fraction of its meaningful
# tokens before the document counts as relevant evidence.
MIN_RELEVANCE = 0.34

# What we say about a source whose licence we have not established. Silence
# would let a buyer assume reuse is safe; "unknown" makes the gap explicit.
UNKNOWN_LICENSE: dict[str, object] = {
    "id": "unknown",
    "url": None,
    "note": "licence not established; check the source before redistributing",
}


def meaningful_tokens(text: str) -> list[str]:
    """Lowercased content tokens with stopwords and 1-char noise removed."""
    tokens = []
    for raw in text.lower().replace("?", " ").replace(",", " ").split():
        token = raw.strip(".!\"'()[]:;")
        if len(token) > 1 and token not in _STOPWORDS:
            tokens.append(token)
    return tokens


def relevance_score(query: str, document: str) -> float:
    """Fraction of the query's meaningful tokens present in the document."""
    q_tokens = meaningful_tokens(query)
    if not q_tokens:
        return 0.0
    doc_tokens = set(meaningful_tokens(document))
    hits = sum(1 for t in set(q_tokens) if t in doc_tokens)
    return hits / len(set(q_tokens))


@dataclass
class RetrievalError:
    """A provider-level failure, surfaced rather than swallowed."""
    provider: str
    error_type: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "error_type": self.error_type, "detail": self.detail}


def classify_transport_error(exc: Exception, timeout_seconds: int) -> tuple[str, str]:
    """Map a transport exception onto a stable (error_type, detail) pair.

    Shared by every network-backed retriever so the pipeline and buyers see
    one error vocabulary regardless of provider.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return "http_error", f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "network_unreachable", str(exc.reason)[:200]
    if isinstance(exc, TimeoutError):
        return "timeout", f"exceeded {timeout_seconds}s"
    if isinstance(exc, json.JSONDecodeError):
        return "malformed_response", str(exc)[:200]
    return type(exc).__name__, str(exc)[:200]


@dataclass
class RetrievalResult:
    sources: list[dict[str, Any]] = field(default_factory=list)
    errors: list[RetrievalError] = field(default_factory=list)
    providers_attempted: list[str] = field(default_factory=list)
    providers_succeeded: list[str] = field(default_factory=list)

    @property
    def degraded(self) -> bool:
        """True when at least one provider failed, even if others returned data."""
        return bool(self.errors)

    @property
    def unavailable(self) -> bool:
        """True when we found nothing AND every provider we tried errored.

        This is the case that must never be reported as `no_evidence`: we did
        not observe an absence of evidence, we failed to observe at all.
        """
        return not self.sources and bool(self.providers_attempted) and not self.providers_succeeded

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_sources": len(self.sources),
            "providers_attempted": self.providers_attempted,
            "providers_succeeded": self.providers_succeeded,
            "degraded": self.degraded,
            "unavailable": self.unavailable,
            "errors": [e.to_dict() for e in self.errors],
        }


class Retriever(Protocol):
    """Any evidence source the pipeline can run against."""

    name: str

    def retrieve(self, query: str, max_results: int = 5) -> RetrievalResult:
        ...


class StaticCorpusRetriever:
    """A small offline corpus, used as an explicitly-labelled fallback.

    This exists so the engine is demonstrable without network access. It is
    never presented as live retrieval: sources are tagged `offline_corpus` so a
    buying agent can tell fixture text from a real fetch, and documents must
    clear the same relevance bar as any other source (the previous version
    matched on stopwords and then fell back unconditionally, which is why the
    service could never refuse anything).
    """

    name = "static_corpus"

    DEFAULT_CORPUS: list[dict[str, str]] = [
        {
            "url": "veritas://fixture/x402",
            "title": "x402 Protocol",
            "text": (
                "x402 is an open standard for internet-native payments over HTTP. "
                "It enables AI agents to pay for APIs and services using stablecoins "
                "by returning HTTP 402 Payment Required. The protocol is now under "
                "the Linux Foundation."
            ),
        },
        {
            "url": "veritas://fixture/bazaar",
            "title": "CDP x402 Bazaar",
            "text": (
                "The CDP x402 Bazaar is a discovery layer that indexes paid resources. "
                "Agents can search by intent and automatically handle payment. "
                "Quality metrics are recomputed on a schedule."
            ),
        },
        {
            "url": "veritas://fixture/mcp",
            "title": "Model Context Protocol",
            "text": (
                "MCP is an open protocol for connecting LLM applications to external "
                "tools and data sources. It supports tool discovery and is commonly "
                "used with x402 for paid agent tools."
            ),
        },
    ]

    def __init__(self, corpus: list[dict[str, str]] | None = None):
        self.corpus = corpus if corpus is not None else self.DEFAULT_CORPUS

    def retrieve(self, query: str, max_results: int = 5) -> RetrievalResult:
        scored = []
        for item in self.corpus:
            score = relevance_score(query, f"{item['title']} {item['text']}")
            if score >= MIN_RELEVANCE:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        sources = [
            {
                "url": item["url"],
                "title": item["title"],
                "text": item["text"],
                "provider": "offline_corpus",
                "provenance": "offline_corpus",
                "relevance": round(score, 3),
                "license": dict(UNKNOWN_LICENSE),
                "attribution": {"required": False, "text": "Veritas offline fixture"},
            }
            for score, item in scored[:max_results]
        ]
        # A corpus lookup cannot fail at the transport level: an empty result
        # here is a genuine absence of evidence, so no error is recorded.
        return RetrievalResult(
            sources=sources,
            providers_attempted=[self.name],
            providers_succeeded=[self.name],
        )


class CompositeRetriever:
    """Runs retrievers in order, merging sources and preserving every error.

    There is deliberately no fallback seam here: substituting offline fixture
    text when live retrieval errors would convert an honest "I could not
    reach my sources" into a confident answer built from canned paragraphs.
    Offline operation is reached by choosing the corpus explicitly
    (`default_retriever(allow_network=False)`), not by failing into it.
    """

    name = "composite"

    def __init__(self, retrievers: list[Retriever]):
        self.retrievers = retrievers

    def retrieve(self, query: str, max_results: int = 5) -> RetrievalResult:
        merged = RetrievalResult()
        seen_urls = set()

        for retriever in self.retrievers:
            result = retriever.retrieve(query, max_results=max_results)
            merged.providers_attempted.extend(result.providers_attempted)
            merged.providers_succeeded.extend(result.providers_succeeded)
            merged.errors.extend(result.errors)
            for src in result.sources:
                url = src.get("url") or ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    merged.sources.append(src)

        merged.sources = merged.sources[:max_results]
        return merged


def default_retriever(allow_network: bool = True) -> Retriever:
    """The retriever the service uses unless a caller injects its own."""
    corpus = StaticCorpusRetriever()
    if not allow_network:
        return corpus
    # Imported lazily so importing the core engine never pulls in the
    # network stack unless live retrieval is actually wanted.
    from .autonomous.zero_key_retrieval import ZeroKeyRetriever
    from .providers import SerperRetriever, serper_api_key

    retrievers: list[Retriever] = []
    # Keyed providers rank ahead of the zero-key tier (roadmap 1.2). A missing
    # key is a configuration state, not an outage: the provider is simply not
    # registered and the free tier serves unchanged. A registered provider's
    # outage degrades to the next retriever with the error preserved.
    if serper_api_key():
        retrievers.append(SerperRetriever())
    retrievers.append(ZeroKeyRetriever())
    # No offline-corpus fallback on the live path. The corpus is repo-authored
    # fixture text; serving it to a live caller was fabricated attribution
    # (it used to carry real third-party URLs). Offline mode still returns it,
    # explicitly labelled, via allow_network=False above.
    return CompositeRetriever(retrievers)
