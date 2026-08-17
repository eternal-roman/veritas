"""Self-host A2A peer card and a local, unpublished peer book.

An agent already serves (`veritas-agent serve`). This module lets it
fetch another agent's card and pull that agent's prediction-market
snapshots through the existing SignalStore. There is no central
network, no DHT, no gossip, no relay, and no push.

The card at ``GET /v1/peer`` advertises *this* node. The address book
lives only on disk (``peers.json``) and is never served over HTTP —
LAN URLs must not leak.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from veritas import __version__
from veritas.hashing import compute_content_hash
from veritas.identity import build_identity
from veritas.runtime import resolve_runtime_dir
from veritas.safeurl import UnsafeUrlError, require_http_url
from veritas.signals import SignalStore

SCHEMA = "veritas.peer.v1"
PEER_PATH = "/v1/peer"
DISCOVERY_PATH = "/.well-known/x402"
ADOPT_PATH = "/adopt.json"
SIGNALS_PATH = "/v1/signals"
MAX_DOCUMENT_BYTES = 1_048_576
DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = f"veritas-peer/{__version__}"
PEERS_FILENAME = "peers.json"

#: Cloud metadata endpoints. Refused even when the caller opted into LAN.
_METADATA_IPS = frozenset({
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
})

Fetcher = Callable[[str], bytes]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def peer_id_for(base_url: str, identity_hash: str | None = None) -> str:
    if isinstance(identity_hash, str) and identity_hash.strip():
        return identity_hash.strip()
    return compute_content_hash(normalize_base_url(base_url))


def peers_path(base_dir: Path | str | None = None) -> Path:
    """Local book path. CLI passes ``--base-dir``; library uses runtime dir."""
    if base_dir is not None:
        return Path(base_dir).expanduser().resolve() / PEERS_FILENAME
    return resolve_runtime_dir() / PEERS_FILENAME


def build_peer_card() -> dict[str, Any]:
    """This node's card. Not an address book. ``central_network`` is false."""
    card: dict[str, Any] = {"schema": SCHEMA}
    try:
        identity = build_identity()
        digest = identity.get("content_hash")
        if isinstance(digest, str) and digest:
            card["identity_hash"] = digest
    except Exception:  # noqa: BLE001 - card stays useful without identity
        pass
    card.update({
        "signals": SIGNALS_PATH,
        "signals_history": "/v1/signals/history",
        "escrow": "/v1/escrow",
        "discovery": DISCOVERY_PATH,
        "adopt": ADOPT_PATH,
        "central_network": False,
    })
    return card


def _is_metadata_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip in _METADATA_IPS or ip.is_link_local


def _address_allowed(address: str, *, allow_local: bool) -> bool:
    ip = ipaddress.ip_address(address)
    if _is_metadata_ip(ip) or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    if ip.is_loopback or ip.is_private:
        return allow_local
    return True


def assert_connect_destination(
    url: str,
    *,
    allow_local: bool = False,
    resolver=socket.getaddrinfo,
) -> str:
    """SSRF guard. ``allow_local`` opts into loopback/RFC1918 only.

    Cloud metadata (169.254.169.254 and other link-local) is refused
    even with ``allow_local``. ``file:`` and non-http(s) schemes never pass.
    """
    require_http_url(url)
    host = urlsplit(url).hostname or ""
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
        if not _address_allowed(address, allow_local=allow_local):
            raise UnsafeUrlError(
                f"refusing to fetch {host!r}: resolves to disallowed address {address}"
            )
    return url


def _default_fetch(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bytes:
    require_http_url(url)
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(  # nosec B310 - scheme checked by assert_connect_destination
        request, timeout=timeout
    ) as response:
        return response.read(MAX_DOCUMENT_BYTES + 1)


def _http_status(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else None


def _load_object(
    url: str,
    fetch: Fetcher,
    label: str,
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    try:
        raw = fetch(url)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return None, _http_status(exc), f"{label}: could not fetch {url}: {type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001 - a hostile peer must not raise through
        return None, _http_status(exc), f"{label}: could not fetch {url}: {type(exc).__name__}"

    if len(raw) > MAX_DOCUMENT_BYTES:
        return None, 200, f"{label}: document too large (over {MAX_DOCUMENT_BYTES} bytes)"
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, 200, f"{label}: could not parse {url} as JSON"
    if not isinstance(document, dict):
        return None, 200, f"{label}: {url} is not a JSON object"
    return document, 200, None


def _load_signals_payload(
    url: str,
    fetch: Fetcher,
) -> tuple[Any | None, str | None]:
    try:
        raw = fetch(url)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return None, f"signals: could not fetch {url}: {type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001
        return None, f"signals: could not fetch {url}: {type(exc).__name__}"
    if len(raw) > MAX_DOCUMENT_BYTES:
        return None, f"signals: document too large (over {MAX_DOCUMENT_BYTES} bytes)"
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, f"signals: could not parse {url} as JSON"
    return document, None


def load_peers(base_dir: Path | str | None = None) -> list[dict[str, Any]]:
    path = peers_path(base_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict) and isinstance(data.get("peers"), list):
        rows = data["peers"]
    elif isinstance(data, list):
        rows = data
    else:
        return []
    return [row for row in rows if isinstance(row, dict)]


def save_peers(
    peers: list[dict[str, Any]],
    base_dir: Path | str | None = None,
) -> None:
    path = peers_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"peers": peers}, indent=2) + "\n",
        encoding="utf-8",
    )


def list_peers(base_dir: Path | str | None = None) -> dict[str, Any]:
    peers = load_peers(base_dir)
    return {
        "peers": peers,
        "count": len(peers),
        "note": "local peer book; never published over HTTP",
    }


def _same_url(left: Any, right: Any) -> bool:
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return normalize_base_url(left) == normalize_base_url(right)


def _upsert_peer(record: dict[str, Any], base_dir: Path | str | None) -> None:
    peers = load_peers(base_dir)
    replaced = False
    for index, existing in enumerate(peers):
        if (
            existing.get("peer_id") == record["peer_id"]
            or _same_url(existing.get("base_url"), record.get("base_url"))
        ):
            peers[index] = record
            replaced = True
            break
    if not replaced:
        peers.append(record)
    save_peers(peers, base_dir)


def find_peer(
    peer_id_or_url: str,
    base_dir: Path | str | None = None,
) -> dict[str, Any] | None:
    wanted = (peer_id_or_url or "").strip()
    if not wanted:
        return None
    for row in load_peers(base_dir):
        if row.get("peer_id") == wanted:
            return row
        if _same_url(row.get("base_url"), wanted):
            return row
    return None


def _fail(code: str, error: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": False, "code": code, "error": error}
    body.update(extra)
    return body


def _joined(base: str, path: str) -> str:
    return urljoin(normalize_base_url(base) + "/", path.lstrip("/"))


def connect(
    base_url: str,
    *,
    allow_local: bool = False,
    fetcher: Fetcher | None = None,
    base_dir: Path | str | None = None,
    resolver=None,
) -> dict[str, Any]:
    """Fetch another agent's card and persist it in the local book.

    Returns a structured result. Does not raise into a caller path.
    Does not require ``VERITAS_PUBLIC_URL``.
    """
    fetch = fetcher or _default_fetch
    raw_url = (base_url or "").strip()
    if not raw_url:
        return _fail("refused", "empty url")
    try:
        require_http_url(raw_url)
        assert_connect_destination(
            raw_url, allow_local=allow_local, resolver=resolver
        )
    except UnsafeUrlError as exc:
        return _fail("refused", str(exc), base_url=raw_url)

    base = normalize_base_url(raw_url)
    peer_url = _joined(base, PEER_PATH)
    card, status, error = _load_object(peer_url, fetch, "peer")
    source = "peer"
    if card is None and status == 404:
        card, status, error = _load_object(
            _joined(base, DISCOVERY_PATH), fetch, "discovery"
        )
        source = "discovery"
        if card is None:
            card, status, error = _load_object(
                _joined(base, ADOPT_PATH), fetch, "adopt"
            )
            source = "adopt"

    if card is None:
        code = "unreachable" if status != 200 else "unparseable"
        return _fail(code, error or "could not read a peer card", base_url=base)

    identity_hash = card.get("identity_hash")
    if not isinstance(identity_hash, str) or not identity_hash.strip():
        identity_hash = None
    peer_id = peer_id_for(base, identity_hash)
    record: dict[str, Any] = {
        "peer_id": peer_id,
        "base_url": base,
        "connected_at": _now(),
        "card": card,
    }
    if identity_hash:
        record["identity_hash"] = identity_hash
    try:
        _upsert_peer(record, base_dir)
    except OSError as exc:
        return _fail(
            "unreachable",
            f"could not persist peer book: {type(exc).__name__}",
            base_url=base,
            peer_id=peer_id,
        )
    return {
        "ok": True,
        "peer_id": peer_id,
        "base_url": base,
        "identity_hash": identity_hash,
        "card": card,
        "source": source,
        "central_network": False,
        "note": "stored in the local peer book; the book is not published",
    }


def _signals_url(base: str, query: str | None) -> str:
    url = _joined(base, SIGNALS_PATH)
    text = (query or "").strip()
    if not text:
        return url
    if text.startswith("?"):
        return url + text
    return url + "?" + text


def _extract_signals(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    items = payload.get("signals")
    if isinstance(items, list):
        return items
    if any(key in payload for key in ("venue", "market_id", "content_hash")):
        return [payload]
    return []


def _record_last_error(
    peer_id_or_url: str,
    error: str | None,
    base_dir: Path | str | None,
) -> None:
    row = find_peer(peer_id_or_url, base_dir)
    if row is None:
        return
    if error:
        row["last_error"] = error
    else:
        row.pop("last_error", None)
    try:
        _upsert_peer(row, base_dir)
    except OSError:
        return


def pull_signals(
    peer_id_or_url: str,
    *,
    query: str | None = None,
    fetcher: Fetcher | None = None,
    allow_local: bool = False,
    base_dir: Path | str | None = None,
    store: SignalStore | None = None,
    resolver=None,
) -> dict[str, Any]:
    """GET another agent's ``/v1/signals`` and store snapshots via SignalStore.

    Prices are not interpreted as truth. Failures record ``last_error``
    on the local book entry when one exists.
    """
    fetch = fetcher or _default_fetch
    wanted = (peer_id_or_url or "").strip()
    if not wanted:
        return _fail("refused", "empty peer id or url")

    known = find_peer(wanted, base_dir)
    if known is not None:
        base = normalize_base_url(str(known.get("base_url") or ""))
        peer_id = str(known.get("peer_id") or "")
    elif "://" in wanted:
        base = normalize_base_url(wanted)
        peer_id = peer_id_for(base)
    else:
        return _fail("refused", f"unknown peer: {wanted}")

    if not base:
        return _fail("refused", "peer has no base_url", peer_id=peer_id)

    try:
        require_http_url(base)
        assert_connect_destination(base, allow_local=allow_local, resolver=resolver)
    except UnsafeUrlError as exc:
        _record_last_error(peer_id or base, str(exc), base_dir)
        return _fail("refused", str(exc), base_url=base, peer_id=peer_id)

    url = _signals_url(base, query)
    payload, error = _load_signals_payload(url, fetch)
    if error or payload is None:
        message = error or "signals: empty response"
        _record_last_error(peer_id or base, message, base_dir)
        return _fail("unreachable", message, base_url=base, peer_id=peer_id)

    items = _extract_signals(payload)
    # SignalStore lives under the runtime dir (evidence + signals.sqlite3),
    # not the agent home. Tests inject ``store`` or set VERITAS_RUNTIME_DIR.
    snapshots = store or SignalStore()
    stored = 0
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        digest = snapshots.put(item)
        if digest:
            stored += 1
        else:
            skipped += 1
    _record_last_error(peer_id or base, None, base_dir)
    return {
        "ok": True,
        "peer_id": peer_id,
        "base_url": base,
        "stored": stored,
        "skipped": skipped,
        "count": stored + skipped,
        "note": "snapshots stored via SignalStore; prices are not verdicts",
    }
