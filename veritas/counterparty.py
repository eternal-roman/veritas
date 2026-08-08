"""Fetch a seller's published surfaces and judge them, in one call.

:mod:`veritas.diligence` deliberately does no I/O: it evaluates documents the
caller already holds. That keeps the evaluator pure, but it left a human in the
loop anyway — somebody still had to write the fetching. This module closes
that, so a buyer agent goes from a seller's URL to a verdict without one.

Two properties are load-bearing here, and both are about not lying to
ourselves once a network is involved:

**A document we could not fetch is one we did not observe.** Every fetch
failure becomes a recorded error and leaves the document ``None``, which the
evaluator reads as UNVERIFIABLE. A seller cannot earn a clean verdict by being
unreachable, and an outage on the buyer's own network is never reported as the
seller's misconduct.

**The seller's own document steers our fetcher, so it is treated as hostile
input.** Discovery is self-traversing by design and we follow its ``links``
rather than guessing paths — but every URL that comes back is put through the
same SSRF guard as the base URL. A seller that advertises
``http://127.0.0.1:8000/admin`` as its constitution gets a fetch error, not a
request into the buyer's private network.

Responses are size-capped: a counterparty must not be able to make a buyer
read gigabytes to decide whether to send it a cent.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from . import __version__
from .diligence import DiligencePolicy, DiligenceReport, Verdict, assess
from .safeurl import UnsafeUrlError, assert_public_destination

#: Enough for a large constitution, far short of a denial-of-service.
MAX_DOCUMENT_BYTES = 1_048_576

DISCOVERY_PATH = "/.well-known/x402"
DEFAULT_TIMEOUT_SECONDS = 10

#: Fallbacks used only when a seller's discovery document names no link. The
#: repository's own discovery is self-traversing, so these should rarely fire.
FALLBACK_PATHS = {"constitution": "/v1/constitution", "trust": "/v1/trust"}

USER_AGENT = f"veritas-diligence/{__version__}"

Fetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class SellerDocuments:
    """What a seller published, and what we failed to read.

    ``errors`` is not decoration. It is the difference between "this seller
    declares no gaps" and "we never saw this seller's gap register", and those
    two must never collapse into the same verdict.
    """

    base_url: str
    discovery: dict[str, Any] | None = None
    constitution: dict[str, Any] | None = None
    trust: dict[str, Any] | None = None
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "fetched": [name for name, doc in (
                ("discovery", self.discovery),
                ("constitution", self.constitution),
                ("trust", self.trust),
            ) if doc is not None],
            "errors": list(self.errors),
        }


def _default_fetch(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bytes:
    """Fetch one URL. The scheme guard runs immediately before opening it."""
    request = urllib.request.Request(  # noqa: S310 - scheme checked below
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(  # nosec B310 - scheme checked by assert_public_destination
        request, timeout=timeout
    ) as response:
        # One byte over the cap so an oversized body is detected rather than
        # silently truncated into something that might still parse.
        return response.read(MAX_DOCUMENT_BYTES + 1)


def _load(
    url: str,
    label: str,
    fetch: Fetcher,
    resolver,
    errors: list[str],
) -> dict[str, Any] | None:
    """Fetch and parse one document, recording why not rather than raising."""
    try:
        assert_public_destination(url, resolver=resolver)
    except UnsafeUrlError as exc:
        errors.append(f"{label}: refused unsafe URL {url}: {exc}")
        return None

    try:
        raw = fetch(url)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        errors.append(f"{label}: could not fetch {url}: {type(exc).__name__}")
        return None
    except Exception as exc:  # noqa: BLE001 - a hostile seller must not raise through
        errors.append(f"{label}: could not fetch {url}: {type(exc).__name__}")
        return None

    if len(raw) > MAX_DOCUMENT_BYTES:
        errors.append(f"{label}: document too large (over {MAX_DOCUMENT_BYTES} bytes)")
        return None

    try:
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        errors.append(f"{label}: could not parse {url} as JSON")
        return None

    if not isinstance(document, dict):
        errors.append(f"{label}: {url} is not a JSON object")
        return None
    return document


def _linked(discovery: dict[str, Any] | None, name: str, base_url: str) -> str:
    """Resolve a surface's URL from discovery's links, or fall back to a path.

    Relative links resolve against the base URL; absolute ones are honoured so
    a seller may serve its constitution from another host. Either way the
    result goes through the SSRF guard before it is opened.
    """
    links = discovery.get("links") if isinstance(discovery, dict) else None
    target = links.get(name) if isinstance(links, dict) else None
    if not isinstance(target, str) or not target.strip():
        target = FALLBACK_PATHS[name]
    return urljoin(base_url.rstrip("/") + "/", target)


def fetch_seller(
    base_url: str,
    *,
    fetch: Fetcher | None = None,
    resolver=None,
) -> SellerDocuments:
    """Fetch a seller's discovery document and everything it links to.

    Raises :class:`~veritas.safeurl.UnsafeUrlError` only for the *base* URL,
    which is the buyer's own input and so a programming error worth surfacing
    loudly. Everything reached from the seller's own document is hostile input
    and is recorded as an error instead.
    """
    fetch = fetch or _default_fetch
    resolve_kwargs = {"resolver": resolver} if resolver is not None else {}
    assert_public_destination(base_url, **resolve_kwargs)

    errors: list[str] = []
    discovery_url = urljoin(base_url.rstrip("/") + "/", DISCOVERY_PATH.lstrip("/"))
    discovery = _load(discovery_url, "discovery", fetch, resolver, errors)
    constitution = _load(_linked(discovery, "constitution", base_url),
                         "constitution", fetch, resolver, errors)
    trust = _load(_linked(discovery, "trust", base_url), "trust", fetch, resolver, errors)

    return SellerDocuments(
        base_url=base_url,
        discovery=discovery,
        constitution=constitution,
        trust=trust,
        errors=tuple(errors),
    )


def evaluate_seller(
    base_url: str,
    *,
    challenge: object = None,
    policy: DiligencePolicy | None = None,
    fetch: Fetcher | None = None,
    resolver=None,
) -> DiligenceReport:
    """Fetch a seller's surfaces and return a verdict on them.

    `challenge` is the 402 the buyer actually received, which cannot be
    fetched — it is minted per request. Omitting it leaves the strongest check
    unverifiable rather than passed.

    Fetch errors are appended to the report's checks so a buyer can see *why*
    a verdict was unverifiable, not merely that it was.
    """
    documents = fetch_seller(base_url, fetch=fetch, resolver=resolver)
    report = assess(
        challenge=challenge,
        discovery=documents.discovery,
        constitution=documents.constitution,
        trust=documents.trust,
        policy=policy,
    )
    if not documents.errors:
        return report

    from .diligence import CheckResult

    retrieval = CheckResult(
        "document_retrieval",
        Verdict.UNVERIFIABLE,
        "could not read every published surface: " + "; ".join(documents.errors),
    )
    checks = report.checks + (retrieval,)
    # A retrieval problem can only weaken a PASS to UNVERIFIABLE. It must not
    # soften a FAIL: a contradiction we did observe stands whatever else we
    # failed to read.
    verdict = report.verdict if report.verdict == Verdict.FAIL else Verdict.UNVERIFIABLE
    return DiligenceReport(verdict, checks)
