"""Keyed retrieval providers (roadmap 1.2).

Serper (google.serper.dev) is implemented here; Exa and Brave should follow
the same shape when added. Keyed providers are registered ahead of the
zero-key tier by `default_retriever`, and a provider outage degrades to the
next tier with the error preserved — never silently.

Key handling policy (tested in `tests/test_providers.py`):

- The API key is configuration, read from the environment
  (`VERITAS_SERPER_API_KEY`, or the conventional `SERPER_API_KEY`).
- It travels only as a request header to the provider over TLS. It is never
  placed in URLs, and never serialised into sources, errors, custody events,
  receipts, responses, or logs.
- Error details are scrubbed defensively: even if a provider echoed the key
  back in a failure, `_safe_detail` redacts it before the error is recorded.

A missing key is a configuration state, not an outage: `default_retriever`
simply does not register the provider, so the free tier serves unchanged. A
directly-constructed `SerperRetriever` without a key reports a
`not_configured` error rather than pretending it searched.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from veritas import __version__

from .retrieval import RetrievalError, RetrievalResult, classify_transport_error
from .safeurl import require_http_url

SERPER_ENDPOINT = "https://google.serper.dev/search"
TIMEOUT_SECONDS = 8
USER_AGENT = f"VeritasAgent/{__version__} (+https://github.com/eternal-roman/veritas)"


def serper_api_key() -> str:
    """The configured Serper key, or empty string. Never raises."""
    return (os.getenv("VERITAS_SERPER_API_KEY") or os.getenv("SERPER_API_KEY") or "").strip()


class SerperRetriever:
    """Google search via the serper.dev API.

    Follows the retriever contract: returns a RetrievalResult carrying both
    sources and classified errors, and never raises. The pipeline still treats
    it as untrusted (exception conversion and the `max_results` cap are
    re-applied there).
    """

    name = "serper"

    def __init__(self, api_key: str | None = None, endpoint: str = SERPER_ENDPOINT):
        self.api_key = api_key if api_key is not None else serper_api_key()
        self.endpoint = endpoint

    def _safe_detail(self, detail: str) -> str:
        """Redact the key from any text that will leave this module."""
        if self.api_key and self.api_key in detail:
            detail = detail.replace(self.api_key, "[redacted]")
        return detail

    def _search(self, query: str, max_results: int) -> dict[str, Any]:
        payload = json.dumps({"q": query, "num": max_results}).encode("utf-8")
        req = urllib.request.Request(
            require_http_url(self.endpoint),
            data=payload,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(  # nosec B310 - scheme checked by require_http_url
            req, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode())

    def retrieve(self, query: str, max_results: int = 5) -> RetrievalResult:
        result = RetrievalResult(providers_attempted=[self.name])

        if not self.api_key:
            result.errors.append(RetrievalError(
                self.name, "not_configured",
                "no API key set (VERITAS_SERPER_API_KEY or SERPER_API_KEY)",
            ))
            return result

        try:
            data = self._search(query, max_results)
        except Exception as exc:  # noqa: BLE001 - classified and surfaced below
            etype, detail = classify_transport_error(exc, TIMEOUT_SECONDS)
            result.errors.append(RetrievalError(self.name, etype, self._safe_detail(detail)))
            return result

        organic = data.get("organic")
        if not isinstance(organic, list):
            result.errors.append(RetrievalError(
                self.name, "malformed_response", "missing 'organic' result list",
            ))
            return result

        for item in organic[:max_results]:
            if not isinstance(item, dict):
                continue
            text = (item.get("snippet") or "").strip()
            url = item.get("link") or ""
            if text and url:
                result.sources.append({
                    "url": url,
                    "title": item.get("title") or "",
                    "text": text,
                    "provider": self.name,
                    "provenance": "live_fetch",
                })

        result.providers_succeeded.append(self.name)
        return result
