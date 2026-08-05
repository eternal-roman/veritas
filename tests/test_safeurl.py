"""Outbound fetches are scheme-limited, and caller-influenced ones are SSRF-guarded."""

from __future__ import annotations

import pytest

from veritas.safeurl import (
    UnsafeUrlError,
    assert_public_destination,
    require_http_url,
)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.org/x",
    "gopher://example.org/",
    "jar:file:///tmp/x!/y",
    "/etc/passwd",
])
def test_non_http_schemes_are_refused(url):
    with pytest.raises(UnsafeUrlError):
        require_http_url(url)


@pytest.mark.parametrize("url", ["http://example.org/a", "https://example.org/a"])
def test_http_schemes_are_allowed(url):
    assert require_http_url(url) == url


def test_url_without_a_host_is_refused():
    with pytest.raises(UnsafeUrlError):
        require_http_url("http:///no-host")


@pytest.mark.parametrize("address", [
    "127.0.0.1",        # loopback
    "169.254.169.254",  # cloud metadata
    "10.0.0.5",         # private
    "192.168.1.1",      # private
    "172.16.0.1",       # private
    "0.0.0.0",          # unspecified
])
def test_non_public_destinations_are_refused(address):
    def resolver(host, port):
        return [(2, 1, 6, "", (address, 0))]

    with pytest.raises(UnsafeUrlError):
        assert_public_destination("https://evil.example.org/x", resolver=resolver)


def test_public_destination_is_allowed():
    def resolver(host, port):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    url = "https://example.org/x"
    assert assert_public_destination(url, resolver=resolver) == url


def test_a_host_with_any_private_record_is_refused():
    """A split-horizon answer must not be admitted on the strength of one
    public record; we cannot choose which address the connection uses."""
    def resolver(host, port):
        return [(2, 1, 6, "", ("93.184.216.34", 0)), (2, 1, 6, "", ("10.1.2.3", 0))]

    with pytest.raises(UnsafeUrlError):
        assert_public_destination("https://split.example.org/x", resolver=resolver)


def test_unresolvable_host_is_refused():
    def resolver(host, port):
        raise OSError("nxdomain")

    with pytest.raises(UnsafeUrlError):
        assert_public_destination("https://nope.example.org/x", resolver=resolver)
