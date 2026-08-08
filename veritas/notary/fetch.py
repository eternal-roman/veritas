"""HTTP(S) body fetch for the notary, after scheme and SSRF guards.

Caller-influenced URLs pass ``require_http_url`` and
``assert_public_destination`` (via :func:`veritas.safeurl.assert_public_destination`)
before any socket is opened. There is no production bypass for private,
loopback, or metadata destinations — tests inject a resolver and opener so a
local TLS origin can be exercised offline without live egress (N0-C, N0-I).

Redirect targets are re-checked through the same public-destination guard so a
302 cannot steer the client into a private network after the initial URL was
admitted.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from veritas import __version__
from veritas.safeurl import UnsafeUrlError, assert_public_destination

DEFAULT_TIMEOUT_SECONDS = 15.0
#: Cap on retained body bytes. One past this is read so truncation is explicit.
MAX_BODY_BYTES = 2_097_152
USER_AGENT = f"veritas-notary/{__version__}"

Resolver = Callable[..., list]
OpenUrl = Callable[..., Any]


@dataclass(frozen=True)
class FetchResult:
    """What the notary received from an origin after the guards admitted it."""

    request_url: str
    final_url: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    truncated: bool


class FetchError(Exception):
    """Network or transport failure after the URL was admitted by the guards."""

    def __init__(
        self,
        message: str,
        *,
        url: str,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.cause = cause


class _GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-run the SSRF guard on every redirect hop before following it."""

    def __init__(self, resolver: Resolver | None) -> None:
        super().__init__()
        self._resolver = resolver

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        kwargs = {"resolver": self._resolver} if self._resolver is not None else {}
        assert_public_destination(newurl, **kwargs)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_open(
    request: urllib.request.Request,
    *,
    timeout: float,
    context: Any = None,
    resolver: Resolver | None = None,
) -> Any:
    handlers: list[Any] = [_GuardedRedirectHandler(resolver)]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    return opener.open(request, timeout=timeout)


def _normalize_headers(response: Any) -> dict[str, str]:
    raw = getattr(response, "headers", None)
    if raw is None:
        return {}
    return {str(k).lower(): str(v) for k, v in raw.items()}


def _read_body(response: Any, max_bytes: int) -> tuple[bytes, bool]:
    # One byte over the cap so an oversized body is detected, not silently cut
    # into something that looks complete.
    blob = response.read(max_bytes + 1)
    if len(blob) > max_bytes:
        return blob[:max_bytes], True
    return blob, False


def _result_from_response(
    *,
    request_url: str,
    response: Any,
    max_bytes: int,
    resolver: Resolver | None,
) -> FetchResult:
    status = int(getattr(response, "status", None) or response.getcode() or 0)
    final_url = str(response.geturl() or request_url)
    if final_url and final_url != request_url:
        kwargs = {"resolver": resolver} if resolver is not None else {}
        assert_public_destination(final_url, **kwargs)
    body, truncated = _read_body(response, max_bytes)
    return FetchResult(
        request_url=request_url,
        final_url=final_url,
        status=status,
        headers=_normalize_headers(response),
        body=body,
        truncated=truncated,
    )


def fetch(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_BODY_BYTES,
    resolver: Resolver | None = None,
    open_url: OpenUrl | None = None,
    ssl_context: Any = None,
    headers: Mapping[str, str] | None = None,
) -> FetchResult:
    """Fetch ``url`` only after scheme + public-destination guards pass.

    Raises:
        UnsafeUrlError: scheme or destination refused; no socket is opened.
        FetchError: the URL was admitted but the transport failed.
    """
    resolve_kwargs: dict[str, Any] = {}
    if resolver is not None:
        resolve_kwargs["resolver"] = resolver
    # Load-bearing: scheme allowlist + public resolution before any open.
    assert_public_destination(url, **resolve_kwargs)

    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
    }
    if headers:
        req_headers.update(dict(headers))

    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url,
        headers=req_headers,
        method="GET",
    )

    opener = open_url
    try:
        if opener is None:
            response_cm = _default_open(
                request,
                timeout=timeout,
                context=ssl_context,
                resolver=resolver,
            )
        else:
            response_cm = opener(
                request, timeout=timeout, context=ssl_context
            )
    except UnsafeUrlError:
        raise
    except urllib.error.HTTPError as exc:
        # HTTPError is a response carrying status + body — still evidence of
        # what the origin returned, so surface it as a FetchResult.
        try:
            return _result_from_response(
                request_url=url,
                response=exc,
                max_bytes=max_bytes,
                resolver=resolver,
            )
        finally:
            exc.close()
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        raise FetchError(
            f"could not fetch {url!r}: {type(exc).__name__}: {exc}",
            url=url,
            cause=exc,
        ) from exc

    try:
        with response_cm as response:
            return _result_from_response(
                request_url=url,
                response=response,
                max_bytes=max_bytes,
                resolver=resolver,
            )
    except UnsafeUrlError:
        raise
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        raise FetchError(
            f"could not fetch {url!r}: {type(exc).__name__}: {exc}",
            url=url,
            cause=exc,
        ) from exc
