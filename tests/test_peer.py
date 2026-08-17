"""Self-host A2A peer card and local unpublished peer book."""

from __future__ import annotations

import importlib
import json
from urllib.error import HTTPError
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from veritas.agent_cli import main
from veritas.hashing import compute_content_hash
from veritas.peer import (
    SCHEMA,
    connect,
    find_peer,
    load_peers,
    pull_signals,
)
from veritas.signals import SignalStore

PEER_CARD = {
    "schema": SCHEMA,
    "identity_hash": "sha256:peer-identity",
    "signals": "/v1/signals",
    "signals_history": "/v1/signals/history",
    "escrow": "/v1/escrow",
    "discovery": "/.well-known/x402",
    "adopt": "/adopt.json",
    "central_network": False,
}

SIGNAL = {
    "venue": "polymarket",
    "market_id": "m-peer",
    "question": "Will two self-hosted agents exchange a snapshot?",
    "outcomes": [{"name": "Yes", "price": 0.5}, {"name": "No", "price": 0.5}],
    "status": "open",
    "observed_at": "2026-08-16T00:00:00Z",
    "source_url": "https://gamma-api.polymarket.com/markets/m-peer",
    "method": "veritas.signals.v1",
    "note": "market-implied prices, not a verdict",
}


def _public_resolver(host, port):
    return [(2, 1, 6, "", ("93.184.216.34", 0))]


def _fetcher(pages):
    def fetch(url: str, *args, **kwargs) -> bytes:
        page = pages.get(url)
        if page is None:
            raise OSError(f"missing {url}")
        if isinstance(page, Exception):
            raise page
        if isinstance(page, (bytes, str)):
            return page.encode() if isinstance(page, str) else page
        return json.dumps(page).encode()

    return fetch


def _client_fetcher(client):
    """Map a peer URL onto Agent A's TestClient. No real sockets."""

    def fetch(url: str, *args, **kwargs) -> bytes:
        parts = urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        response = client.get(path)
        if response.status_code == 404:
            raise HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
        if response.status_code >= 400:
            raise OSError(f"agent-a HTTP {response.status_code} for {path}")
        return response.content

    return fetch


def test_connect_with_injected_fetcher_stores_a_peer(tmp_path):
    base = "https://peer.example"
    result = connect(
        base,
        fetcher=_fetcher({f"{base}/v1/peer": PEER_CARD}),
        base_dir=tmp_path,
        resolver=_public_resolver,
    )
    assert result["ok"] is True
    assert result["peer_id"] == PEER_CARD["identity_hash"]
    assert result["source"] == "peer"
    assert result["central_network"] is False
    stored = load_peers(tmp_path)
    assert len(stored) == 1
    assert stored[0]["peer_id"] == PEER_CARD["identity_hash"]
    assert stored[0]["base_url"] == base
    assert stored[0]["card"]["schema"] == SCHEMA
    assert find_peer(PEER_CARD["identity_hash"], tmp_path) is not None


def test_connect_refuses_metadata_even_with_allow_local(tmp_path):
    result = connect(
        "http://169.254.169.254/",
        allow_local=True,
        fetcher=_fetcher({}),
        base_dir=tmp_path,
    )
    assert result["ok"] is False
    assert result["code"] == "refused"
    assert load_peers(tmp_path) == []


def test_connect_loopback_requires_allow_local(tmp_path):
    card_url = "http://127.0.0.1:8765/v1/peer"
    fetch = _fetcher({card_url: PEER_CARD})

    refused = connect(
        "http://127.0.0.1:8765",
        allow_local=False,
        fetcher=fetch,
        base_dir=tmp_path,
    )
    assert refused["ok"] is False
    assert refused["code"] == "refused"
    assert load_peers(tmp_path) == []

    accepted = connect(
        "http://127.0.0.1:8765",
        allow_local=True,
        fetcher=fetch,
        base_dir=tmp_path,
    )
    assert accepted["ok"] is True
    assert accepted["base_url"] == "http://127.0.0.1:8765"
    assert load_peers(tmp_path)[0]["peer_id"] == PEER_CARD["identity_hash"]


def test_pull_signals_stores_via_signal_store(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    base = "https://peer.example"
    connect(
        base,
        fetcher=_fetcher({f"{base}/v1/peer": PEER_CARD}),
        base_dir=tmp_path,
        resolver=_public_resolver,
    )
    store = SignalStore(tmp_path / "runtime")
    result = pull_signals(
        PEER_CARD["identity_hash"],
        fetcher=_fetcher({
            f"{base}/v1/signals": {"signals": [SIGNAL], "count": 1},
        }),
        base_dir=tmp_path,
        store=store,
        resolver=_public_resolver,
    )
    assert result["ok"] is True
    assert result["stored"] == 1
    assert result["skipped"] == 0
    listed = store.list()
    assert len(listed) == 1
    assert listed[0]["market_id"] == "m-peer"
    assert listed[0]["question"] == SIGNAL["question"]
    assert store.get(listed[0]["content_hash"]) is not None


def test_connect_refuses_redirect_to_metadata(tmp_path):
    """urlopen follows 3xx; a peer that 302s at the metadata IP must not pass."""
    from veritas.peer import _GuardedRedirectHandler
    from veritas.safeurl import UnsafeUrlError

    handler = _GuardedRedirectHandler(allow_local=True, resolver=None)
    req = type("Req", (), {})()
    try:
        handler.redirect_request(
            req, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data"
        )
    except (UnsafeUrlError, Exception) as exc:
        # urllib wraps or we raise UnsafeUrlError directly
        assert "169.254" in str(exc) or isinstance(exc, UnsafeUrlError) or "disallowed" in str(exc).lower() or "refusing" in str(exc).lower()
    else:
        raise AssertionError("redirect to metadata must be refused")


def test_get_v1_peer_returns_schema_and_no_central_network(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app)
    body = client.get("/v1/peer").json()
    assert body["schema"] == SCHEMA
    assert body["central_network"] is False
    assert body["signals"] == "/v1/signals"
    assert "identity_hash" in body
    links = client.get("/.well-known/x402").json()["links"]
    assert links["peer"] == "/v1/peer"
    assert client.get(links["peer"]).status_code == 200
    # The book is never published.
    assert client.get("/v1/peers").status_code == 404


def test_connect_falls_back_when_peer_card_is_404(tmp_path):
    base = "https://old.example"
    not_found = HTTPError(f"{base}/v1/peer", 404, "Not Found", hdrs=None, fp=None)
    result = connect(
        base,
        fetcher=_fetcher({
            f"{base}/v1/peer": not_found,
            f"{base}/.well-known/x402": {"links": {"signals": "/v1/signals"}},
        }),
        base_dir=tmp_path,
        resolver=_public_resolver,
    )
    assert result["ok"] is True
    assert result["source"] == "discovery"
    assert result["peer_id"] == compute_content_hash(base)


def test_cli_connect_peers_and_pull(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    pages = {
        "http://127.0.0.1:8765/v1/peer": PEER_CARD,
        "http://127.0.0.1:8765/v1/signals": {"signals": [SIGNAL], "count": 1},
    }
    monkeypatch.setattr("veritas.peer._default_fetch", _fetcher(pages))

    assert main([
        "--base-dir", str(tmp_path),
        "connect", "http://127.0.0.1:8765", "--allow-local",
    ]) == 0
    connected = json.loads(capsys.readouterr().out)
    assert connected["ok"] is True

    assert main(["--base-dir", str(tmp_path), "peers"]) == 0
    book = json.loads(capsys.readouterr().out)
    assert book["count"] == 1
    assert book["peers"][0]["peer_id"] == PEER_CARD["identity_hash"]

    assert main([
        "--base-dir", str(tmp_path),
        "pull-signals", PEER_CARD["identity_hash"], "--allow-local",
    ]) == 0
    pulled = json.loads(capsys.readouterr().out)
    assert pulled["ok"] is True
    assert pulled["stored"] == 1

    assert main([
        "--base-dir", str(tmp_path),
        "connect", "http://127.0.0.1:8765",
    ]) == 1
    assert main([
        "--base-dir", str(tmp_path),
        "connect", "http://169.254.169.254/", "--allow-local",
    ]) == 1


def test_list_peers_is_local_only():
    # Structural: the public handler is the card, not the book.
    from veritas.hooks import http_paths

    assert "/v1/peer" in http_paths()
    assert "/v1/peers" not in http_paths()


def test_pull_signals_accepts_wrapped_object_and_raw_list(tmp_path):
    """GET /v1/signals serves `{signals: [...]}`; a raw list must also store."""
    wrapped_store = SignalStore(tmp_path / "wrapped")
    wrapped = pull_signals(
        "https://peer.example",
        fetcher=_fetcher({
            "https://peer.example/v1/signals": {"signals": [SIGNAL], "count": 1},
        }),
        store=wrapped_store,
        resolver=_public_resolver,
    )
    assert wrapped["ok"] is True
    assert wrapped["stored"] == 1
    assert wrapped["skipped"] == 0
    assert wrapped_store.list()[0]["market_id"] == SIGNAL["market_id"]

    listed_store = SignalStore(tmp_path / "listed")
    listed = pull_signals(
        "https://peer.example",
        fetcher=_fetcher({
            "https://peer.example/v1/signals": [SIGNAL],
        }),
        store=listed_store,
        resolver=_public_resolver,
    )
    assert listed["ok"] is True
    assert listed["stored"] == 1
    assert listed["skipped"] == 0
    assert listed_store.list()[0]["market_id"] == SIGNAL["market_id"]


def test_two_agent_handshake_without_a_central_host(tmp_path, monkeypatch):
    """Agent A serves; Agent B connect+pull via A's TestClient. No central host.

    Peer connect / self-host only. Not the program Mesh Runner, not a
    public seller, and not stranger discovery (VERITAS_PUBLIC_URL unset).
    """
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "agent-a-runtime"))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    import veritas.server as server

    importlib.reload(server)
    written = server.signal_snapshots.put(SIGNAL)
    assert written

    agent_a = TestClient(server.app)
    card = agent_a.get("/v1/peer").json()
    assert card["schema"] == SCHEMA
    assert card["central_network"] is False
    assert agent_a.get("/v1/peers").status_code == 404
    served = agent_a.get("/v1/signals").json()
    assert isinstance(served.get("signals"), list)
    assert any(item.get("market_id") == SIGNAL["market_id"] for item in served["signals"])
    assert agent_a.get("/v1/identity").json()["base_url_configured"] is False

    b_home = tmp_path / "agent-b-home"
    fetch = _client_fetcher(agent_a)
    linked = connect(
        "https://agent-a.example",
        fetcher=fetch,
        base_dir=b_home,
        resolver=_public_resolver,
    )
    assert linked["ok"] is True
    assert linked["source"] == "peer"
    assert linked["card"]["schema"] == SCHEMA
    assert linked["card"]["central_network"] is False
    assert linked["peer_id"] == card["identity_hash"]

    b_store = SignalStore(tmp_path / "agent-b-runtime")
    pulled = pull_signals(
        linked["peer_id"],
        fetcher=fetch,
        base_dir=b_home,
        store=b_store,
        resolver=_public_resolver,
    )
    assert pulled["ok"] is True
    assert pulled["stored"] >= 1
    copied = b_store.list()
    assert any(item.get("market_id") == SIGNAL["market_id"] for item in copied)
    assert find_peer(linked["peer_id"], b_home) is not None
    # A's store still holds the original snapshot; no central host in between.
    assert any(
        item.get("market_id") == SIGNAL["market_id"]
        for item in server.signal_snapshots.list()
    )
