"""Scheme and destination guards for outbound URL fetching.

`urllib.request.urlopen` honours `file:`, `ftp:` and custom schemes, so any code
path that opens a URL derived from configuration — let alone from a caller — can
be steered at the local filesystem or at internal network addresses. Bandit flags
this class as B310; the guard here is the answer to it rather than a suppression.

Two separate checks, because they defend different things:

* `require_http_url` — scheme allowlist. Used everywhere we open a URL.
* `assert_public_destination` — resolves the host and refuses loopback, private,
  link-local and other non-public addresses. Used where the URL can be influenced
  by a caller, which is the SSRF case.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeUrlError(ValueError):
    """Raised when a URL may not be fetched."""


def require_http_url(url: str) -> str:
    """Return `url` if it is http(s), else raise.

    Call this immediately before opening any URL.
    """
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(
            f"refusing to fetch non-http(s) URL scheme: {parts.scheme or '(none)'!r}"
        )
    if not parts.hostname:
        raise UnsafeUrlError("refusing to fetch a URL with no host")
    return url


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_public_destination(url: str, resolver=socket.getaddrinfo) -> str:
    """Refuse URLs whose host resolves to a non-public address.

    This is the SSRF guard: it stops a caller-supplied URL from reaching cloud
    metadata endpoints (169.254.169.254), loopback services, or anything inside
    a private network. Every resolved address must be public — a host with one
    public and one private record is refused, since we cannot control which the
    connection would use.
    """
    require_http_url(url)
    host = urlsplit(url).hostname or ""
    # None means "use the default resolver". Callers that thread an optional
    # resolver through (diligence, buyer journey) pass None when the caller
    # did not inject one; treating that as an override crashed both installed
    # buyer CLIs on every un-injected invocation — with exit code 1, which
    # reads as a seller-failed verdict. Found in review 2026-08-09.
    if resolver is None:
        resolver = socket.getaddrinfo
    try:
        infos = resolver(host, None)
    except OSError as exc:
        raise UnsafeUrlError(f"could not resolve host {host!r}") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UnsafeUrlError(f"host {host!r} resolved to no addresses")
    for address in addresses:
        if not _is_public(address):
            raise UnsafeUrlError(
                f"refusing to fetch {host!r}: resolves to non-public address {address}"
            )
    return url
