"""Lexical NLI-gated synthesis — entailed claims only, never invented ones.

The served product still ships extractive claims (title + excerpt). This
module adds an optional second pass: a statement composed across two or
more sources, published only when every content token of the statement
appears in the cited excerpts.

That is lexical entailment, not a language model. It does not justify a
"commercial-grade research" claim. It exists so a buyer who paid for
research gets something more than a list of snippets *when the sources
actually overlap*, and so an unentailed sentence can never leave the
pipeline.

Rules:

* Extractive claims stay. Synthesis is additive.
* A synthesized claim cites ``support_hashes`` (every excerpt it used)
  and sets ``evidence_hash`` to the first of those so the existing
  contract (every claim names a hash present in the response) holds.
* ``kind`` is ``synthesized``. Unentailed candidates are dropped, not
  softened.
* No price, no model, no network.
"""

from __future__ import annotations

import re
from typing import Any

CLAIM_KIND_EXTRACTIVE = "extractive"
CLAIM_KIND_SYNTHESIZED = "synthesized"

# Function words that cannot carry an entailment on their own. Kept small
# and ASCII: excerpts are English-dominant today and a larger list would
# be a second, untested language-detection problem.
_STOP = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "that",
    "this", "these", "those", "to", "of", "in", "on", "for", "with",
    "from", "by", "as", "at", "is", "are", "was", "were", "be", "been",
    "being", "it", "its", "into", "about", "over", "after", "before",
    "not", "no", "nor", "so", "such", "can", "may", "will", "just",
    "also", "via", "per", "using",
})

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)

#: Shared n-grams shorter than this are coincidence, not a claim.
_MIN_NGRAM = 4
_MAX_NGRAM = 12
_MAX_SYNTHESIZED = 3


def content_tokens(text: str) -> list[str]:
    """Content tokens of ``text``: lowercase, stopwords and 1–2-letter dropped."""
    return [
        tok for tok in _TOKEN.findall(text.lower())
        if tok not in _STOP and len(tok) > 2
    ]


def lexical_entails(premise: str, hypothesis: str) -> bool:
    """True when every content token of ``hypothesis`` appears in ``premise``.

    An empty hypothesis does not entail: there is nothing to check, and
    publishing an empty statement would be a claim with no content.
    """
    hyp = content_tokens(hypothesis)
    if not hyp:
        return False
    prem = set(content_tokens(premise))
    return all(token in prem for token in hyp)


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if n <= 0 or len(tokens) < n:
        return []
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _span_text(tokens: tuple[str, ...]) -> str:
    return " ".join(tokens)


def synthesize_claims(
    query: str,
    evidence: list[dict[str, Any]],
    *,
    start_index: int = 1,
) -> list[dict[str, Any]]:
    """Propose cross-source claims; keep only those entailed by cited excerpts.

    ``start_index`` is the next claim id number (``cN``). Returns at most
    ``_MAX_SYNTHESIZED`` claims, longest shared spans first. Never invents
    tokens that do not appear in the cited evidence.
    """
    usable = [
        ev for ev in evidence
        if isinstance(ev.get("excerpt"), str) and ev.get("content_hash")
        and content_tokens(ev["excerpt"])
    ]
    if len(usable) < 2:
        return []

    tokenised = [(ev, content_tokens(ev["excerpt"])) for ev in usable]
    # Count which n-grams appear in at least two excerpts.
    owners: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for ev, tokens in tokenised:
        seen_here: set[tuple[str, ...]] = set()
        for n in range(_MAX_NGRAM, _MIN_NGRAM - 1, -1):
            for gram in _ngrams(tokens, n):
                if gram in seen_here:
                    continue
                seen_here.add(gram)
                owners.setdefault(gram, []).append(ev)

    shared = [
        (gram, sources) for gram, sources in owners.items() if len(sources) >= 2
    ]
    # Prefer longer spans; drop a span that is a subspan of one we already took
    # from the same source set so we do not emit three nestings of one fact.
    shared.sort(key=lambda item: (-len(item[0]), -len(item[1])))

    claims: list[dict[str, Any]] = []
    used_spans: list[tuple[str, ...]] = []
    query_tokens = set(content_tokens(query))

    for gram, sources in shared:
        if len(claims) >= _MAX_SYNTHESIZED:
            break
        if any(_is_subspan(gram, taken) for taken in used_spans):
            continue
        # A synthesis that shares nothing with the query is off-topic noise
        # wearing a "sources agree" prefix. Require at least one query token
        # in the span *or* an empty query (tests that synthesise on a corpus
        # already filtered by the relevance gate).
        if query_tokens and not (query_tokens & set(gram)):
            continue
        span = _span_text(gram)
        statement = span[0].upper() + span[1:] + "."
        hashes = []
        seen_hash: set[str] = set()
        for ev in sources:
            digest = ev["content_hash"]
            if digest in seen_hash:
                continue
            seen_hash.add(digest)
            hashes.append(digest)
        premise = " ".join(ev["excerpt"] for ev in sources)
        if not lexical_entails(premise, statement):
            continue
        primary = sources[0]
        claim_id = f"c{start_index + len(claims)}"
        claims.append({
            "id": claim_id,
            "statement": statement,
            "evidence_hash": hashes[0],
            "source_url": primary.get("url"),
            "provenance": primary.get("provenance"),
            "relevance": primary.get("relevance"),
            "kind": CLAIM_KIND_SYNTHESIZED,
            "support_hashes": hashes,
        })
        used_spans.append(gram)
    return claims


def _is_subspan(inner: tuple[str, ...], outer: tuple[str, ...]) -> bool:
    if len(inner) > len(outer):
        return False
    if inner == outer:
        return True
    needle = _span_text(inner)
    hay = _span_text(outer)
    return needle in hay
