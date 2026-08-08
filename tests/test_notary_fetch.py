"""SSRF-safe notary fetch: refuse private destinations; fetch only offline TLS.

No live egress is required. Success-path coverage uses a local TLS origin
fixture and injectable resolver/opener seams — production code has no
private-destination bypass flag.
"""

from __future__ import annotations

import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from veritas.notary.fetch import (
    MAX_BODY_BYTES,
    FetchError,
    FetchResult,
    fetch,
)
from veritas.safeurl import UnsafeUrlError

# ---------------------------------------------------------------------------
# Local TLS origin fixture (N0-I). Ephemeral self-signed cert; no network
# outside this process. Production fetch never learns about this helper.
# ---------------------------------------------------------------------------


def _issue_self_signed(tmp_path: Path, common_name: str) -> tuple[Path, Path]:
    """Write a short-lived self-signed cert+key for the fixture hostname."""
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "fixture.pem"
    key_path = tmp_path / "fixture-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class _FixtureHandler(BaseHTTPRequestHandler):
    body = b"notary-fixture-body-v1"
    content_type = "text/plain; charset=utf-8"

    def do_GET(self):  # noqa: N802 - http.server API
        if self.path.rstrip("/") == "/hello":
            payload = self.body
            self.send_response(200)
            self.send_header("Content-Type", self.content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.rstrip("/") == "/big":
            payload = b"x" * (MAX_BODY_BYTES + 64)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003 - silence test server
        return


@pytest.fixture
def local_tls_origin(tmp_path):
    """HTTPS origin on loopback with a public-looking hostname in the URL.

    The notary fetch guard requires a public resolved address, so tests inject
    a resolver that returns a public IP and an opener that connects to the
    real loopback listener. That split is deliberate: production code never
    gets a ``allow_private`` switch.
    """
    host_name = "notary-fixture.test"
    cert_path, key_path = _issue_self_signed(tmp_path, host_name)

    server = HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    # Pin minimum TLS 1.2+ — bare PROTOCOL_TLS_* still admits legacy versions
    # under some OpenSSL builds (CodeQL: insecure SSL/TLS version).
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client_ctx = ssl.create_default_context()
    client_ctx.load_verify_locations(cafile=str(cert_path))
    # Connect by loopback IP while presenting the fixture hostname for SNI
    # and cert verification (cert SAN is DNS:notary-fixture.test, not 127.0.0.1).
    client_ctx.check_hostname = True

    def public_resolver(host, _port):
        if host != host_name:
            raise OSError(f"unexpected host {host!r}")
        # Example's documented public A record shape — not contacted.
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    def open_local(request, *, timeout, context=None):
        """TLS to loopback with server_hostname pinned to the fixture DNS name."""
        import http.client
        import socket

        parts = urlsplit(request.full_url)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        headers = {k: v for k, v in request.header_items()}
        headers["Host"] = host_name

        ctx = context or client_ctx
        conn = http.client.HTTPSConnection(
            "127.0.0.1",
            port=port,
            timeout=timeout,
            context=ctx,
        )

        def connect_with_sni() -> None:
            # SNI + cert check use the fixture DNS name; TCP is loopback only.
            sock = socket.create_connection((conn.host, conn.port), conn.timeout)
            conn.sock = ctx.wrap_socket(sock, server_hostname=host_name)

        conn.connect = connect_with_sni  # type: ignore[method-assign]
        try:
            conn.request(
                request.get_method(),
                path,
                body=request.data,
                headers=headers,
            )
            resp = conn.getresponse()
        except Exception:
            conn.close()
            raise

        # Adapt http.client response to the urlopen-shaped object fetch expects.
        class _CompatResponse:
            def __init__(self, raw: http.client.HTTPResponse, final: str) -> None:
                self._raw = raw
                self._final = final
                self.status = raw.status
                self.headers = raw.headers
                self._body = raw.read()
                self._pos = 0

            def getcode(self) -> int:
                return int(self.status)

            def geturl(self) -> str:
                return self._final

            def read(self, n: int = -1) -> bytes:
                if n is None or n < 0:
                    chunk = self._body[self._pos :]
                    self._pos = len(self._body)
                    return chunk
                chunk = self._body[self._pos : self._pos + n]
                self._pos += len(chunk)
                return chunk

            def close(self) -> None:
                self._raw.close()
                conn.close()

            def __enter__(self) -> _CompatResponse:
                return self

            def __exit__(self, *args: object) -> None:
                self.close()

        return _CompatResponse(resp, request.full_url)

    origin = {
        "host_name": host_name,
        "port": port,
        "base_url": f"https://{host_name}:{port}",
        "url": f"https://{host_name}/hello",
        "resolver": public_resolver,
        "open_url": open_local,
        "ssl_context": client_ctx,
        "body": _FixtureHandler.body,
    }
    try:
        yield origin
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _spy_opener():
    """Opener that fails the test if a socket would have been opened."""

    def open_url(request, *, timeout, context=None):
        raise AssertionError(
            f"opener must not run after guard refusal; got {request.full_url!r}"
        )

    return open_url


# ---------------------------------------------------------------------------
# Scheme + SSRF refusal (no socket)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.org/x",
        "gopher://example.org/",
        "jar:file:///tmp/x!/y",
        "/etc/passwd",
        "http:///no-host",
    ],
)
def test_non_http_schemes_and_hostless_urls_are_refused_before_open(url):
    with pytest.raises(UnsafeUrlError):
        fetch(url, open_url=_spy_opener())


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",  # loopback
        "::1",  # loopback v6
        "169.254.169.254",  # cloud metadata link-local
        "10.0.0.5",  # private
        "192.168.1.1",  # private
        "172.16.0.1",  # private
        "0.0.0.0",  # unspecified
    ],
)
def test_private_loopback_and_metadata_destinations_are_refused(address):
    def resolver(host, port):
        return [(2, 1, 6, "", (address, 0))]

    with pytest.raises(UnsafeUrlError):
        fetch(
            "https://evil.example.org/secret",
            resolver=resolver,
            open_url=_spy_opener(),
        )


def test_metadata_hostname_is_refused_when_it_resolves_link_local():
    def resolver(host, port):
        assert host == "metadata.google.internal"
        return [(2, 1, 6, "", ("169.254.169.254", 0))]

    with pytest.raises(UnsafeUrlError):
        fetch(
            "http://metadata.google.internal/computeMetadata/v1/",
            resolver=resolver,
            open_url=_spy_opener(),
        )


def test_split_horizon_answer_with_any_private_record_is_refused():
    def resolver(host, port):
        return [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("10.1.2.3", 0)),
        ]

    with pytest.raises(UnsafeUrlError):
        fetch(
            "https://split.example.org/x",
            resolver=resolver,
            open_url=_spy_opener(),
        )


# ---------------------------------------------------------------------------
# Local TLS success path (offline)
# ---------------------------------------------------------------------------


def test_fetch_returns_body_from_local_tls_origin(local_tls_origin):
    result = fetch(
        local_tls_origin["url"],
        resolver=local_tls_origin["resolver"],
        open_url=local_tls_origin["open_url"],
        ssl_context=local_tls_origin["ssl_context"],
    )
    assert isinstance(result, FetchResult)
    assert result.status == 200
    assert result.body == local_tls_origin["body"]
    assert result.truncated is False
    assert result.request_url == local_tls_origin["url"]
    assert "text/plain" in result.headers.get("content-type", "")


def test_fetch_truncates_oversized_body(local_tls_origin):
    result = fetch(
        f"https://{local_tls_origin['host_name']}/big",
        resolver=local_tls_origin["resolver"],
        open_url=local_tls_origin["open_url"],
        ssl_context=local_tls_origin["ssl_context"],
        max_bytes=1024,
    )
    assert result.truncated is True
    assert len(result.body) == 1024


def test_fetch_error_when_opener_fails_after_guards(local_tls_origin):
    def boom(request, *, timeout, context=None):
        raise OSError("connection reset")

    with pytest.raises(FetchError) as excinfo:
        fetch(
            local_tls_origin["url"],
            resolver=local_tls_origin["resolver"],
            open_url=boom,
        )
    assert local_tls_origin["url"] in str(excinfo.value) or excinfo.value.url == (
        local_tls_origin["url"]
    )


def test_guards_run_before_opener_on_success_path(local_tls_origin):
    """Ordering pin: public-destination check precedes any open_url call."""
    order: list[str] = []

    def resolver(host, port):
        order.append("resolve")
        return local_tls_origin["resolver"](host, port)

    def open_url(request, *, timeout, context=None):
        order.append("open")
        return local_tls_origin["open_url"](
            request, timeout=timeout, context=context
        )

    fetch(
        local_tls_origin["url"],
        resolver=resolver,
        open_url=open_url,
        ssl_context=local_tls_origin["ssl_context"],
    )
    assert order[0] == "resolve"
    assert order[-1] == "open"
    assert "resolve" in order and "open" in order
