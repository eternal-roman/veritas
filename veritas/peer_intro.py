"""Signed public-URL peer introductions — WAN mesh without a registry.

You only learn peers from a peer you already connected to (SSB / BitTorrent
PEX, not a DHT). This module builds and checks introduction cards. It does
not serve HTTP, gossip, or push. ``GET /v1/peer/introductions`` is mounted
elsewhere; this library only produces the public-URL-only cards.

Each card is EIP-191 ``personal_sign`` over the canonical fields, using this
node's commerce key (injected as ``sign_text``). Loopback, RFC1918,
link-local, and cloud-metadata destinations are never listed. Missing
``eth_account`` fails closed for both sign and verify — no unsigned cards,
no "signature skipped" accept.

This is **not** the program Mesh Runner.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from veritas.peer import assert_connect_destination, normalize_base_url, peer_id_for
from veritas.safeurl import UnsafeUrlError

SCHEMA = "veritas.intro.v1"
INTRODUCTIONS_PATH = "/v1/peer/introductions"
DEFAULT_LIMIT = 32
BIND_KEYS = (
    "schema",
    "base_url",
    "peer_id",
    "identity_hash",
    "introduced_at",
    "introducer",
)
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

SignText = Callable[[str], str]
ConnectFn = Callable[[str], Any]


class PeerIntroError(ValueError):
    """Introduction could not be signed, verified, or accepted."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_address(address: str) -> str:
    if not isinstance(address, str) or not _ADDRESS_RE.match(address):
        raise PeerIntroError("introducer must be 0x-prefixed 20-byte hex")
    return address.lower()


def _identity_hash(peer_row: Mapping[str, Any]) -> str | None:
    value = peer_row.get("identity_hash")
    if isinstance(value, str) and value.strip():
        return value.strip()
    card = peer_row.get("card")
    if isinstance(card, Mapping):
        digest = card.get("identity_hash")
        if isinstance(digest, str) and digest.strip():
            return digest.strip()
    return None


def _eth_account_modules() -> tuple[Any, Any] | None:
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        return None
    return Account, encode_defunct


def canonical_introduction_message(record: Mapping[str, Any]) -> str:
    """EIP-191 text: compact JSON of the bound fields, keys sorted."""
    bound = {key: record[key] for key in BIND_KEYS}
    return json.dumps(bound, sort_keys=True, separators=(",", ":"))


def introduction_record(
    peer_row: Mapping[str, Any],
    *,
    sign_text: SignText | None = None,
    introducer_address: str | None = None,
) -> dict[str, Any]:
    """Sign one accepted peer as a public introduction card.

    Fails closed: no ``sign_text``, no introducer, or an unverifiable
    signature raises. Never returns an unsigned card.
    """
    if sign_text is None or introducer_address is None:
        raise PeerIntroError("signer required; refusing unsigned introduction")
    if not isinstance(peer_row, Mapping):
        raise PeerIntroError("peer row must be an object")
    raw_url = peer_row.get("base_url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise PeerIntroError("peer row has no base_url")
    base = normalize_base_url(raw_url)
    identity_hash = _identity_hash(peer_row)
    raw_id = peer_row.get("peer_id")
    if isinstance(raw_id, str) and raw_id.strip():
        peer_id = raw_id.strip()
    else:
        peer_id = peer_id_for(base, identity_hash)
    introducer = _normalize_address(introducer_address)
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "base_url": base,
        "peer_id": peer_id,
        "identity_hash": identity_hash,
        "introduced_at": _now(),
        "introducer": introducer,
    }
    message = canonical_introduction_message(record)
    try:
        signature = sign_text(message)
    except PeerIntroError:
        raise
    except Exception as exc:
        raise PeerIntroError(f"signing failed: {type(exc).__name__}") from exc
    if not isinstance(signature, str) or not signature.startswith("0x"):
        raise PeerIntroError("signer returned unusable signature")
    record["signature"] = signature
    ok, reason = verify_introduction(record)
    if not ok:
        raise PeerIntroError(f"signed introduction failed verify: {reason}")
    return record


def _public_base_url(url: Any, *, resolver=None) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    base = normalize_base_url(url)
    try:
        assert_connect_destination(base, allow_local=False, resolver=resolver)
    except (UnsafeUrlError, ValueError):
        return None
    return base


def public_introductions(
    peers: Iterable[Mapping[str, Any]] | None,
    *,
    limit: int = DEFAULT_LIMIT,
    sign_text: SignText | None = None,
    introducer_address: str | None = None,
    resolver=None,
) -> list[dict[str, Any]]:
    """Signed cards for accepted peers whose ``base_url`` is a public destination.

    Same refusal rules as ``assert_connect_destination(allow_local=False)`` /
    ``assert_public_destination``: loopback, RFC1918, link-local, and
    metadata IPs are skipped. Unusable URLs are skipped. Cap defaults to 32.
    Without a signer this returns ``[]`` rather than unsigned cards.
    """
    if sign_text is None or introducer_address is None:
        return []
    if not peers:
        return []
    try:
        cap = int(limit)
    except (TypeError, ValueError):
        cap = DEFAULT_LIMIT
    if cap <= 0:
        return []

    out: list[dict[str, Any]] = []
    for row in peers:
        if len(out) >= cap:
            break
        if not isinstance(row, Mapping):
            continue
        base = _public_base_url(row.get("base_url"), resolver=resolver)
        if base is None:
            continue
        try:
            card = introduction_record(
                {**dict(row), "base_url": base},
                sign_text=sign_text,
                introducer_address=introducer_address,
            )
        except PeerIntroError:
            continue
        out.append(card)
    return out


def verify_introduction(
    record: Mapping[str, Any] | None,
    *,
    expected_introducer: str | None = None,
) -> tuple[bool, str]:
    """Recover the EIP-191 signer. Fails closed without ``eth_account``."""
    modules = _eth_account_modules()
    if modules is None:
        return False, "eth_account required"
    Account, encode_defunct = modules

    if not isinstance(record, Mapping) or record.get("schema") != SCHEMA:
        return False, "unrecognized schema"
    try:
        message = canonical_introduction_message(record)
    except KeyError as exc:
        return False, f"missing field: {exc}"
    signature = record.get("signature")
    if not isinstance(signature, str) or not signature.startswith("0x"):
        return False, "signature missing"
    try:
        claimed = _normalize_address(str(record.get("introducer") or ""))
    except PeerIntroError:
        return False, "introducer malformed"
    try:
        recovered = Account.recover_message(
            encode_defunct(text=message), signature=signature
        )
    except Exception as exc:  # eth_account raises varied types
        return False, f"recovery failed: {type(exc).__name__}"
    recovered_addr = str(recovered).lower()
    if recovered_addr != claimed:
        return False, f"signer {recovered_addr} != {claimed}"
    if expected_introducer is not None:
        try:
            want = _normalize_address(expected_introducer)
        except PeerIntroError:
            return False, "expected introducer malformed"
        if recovered_addr != want:
            return False, f"signer {recovered_addr} != {want}"
    return True, "ok"


def accept_introduction(
    record: Mapping[str, Any] | None,
    *,
    connect_fn: ConnectFn | None = None,
    allow_local: bool = False,
    resolver=None,
) -> Any:
    """Verify the signature, refuse LAN/metadata, then optionally connect.

    Does not fetch unless ``connect_fn`` is provided. Without it, returns
    the verified record for the caller to connect. Failures are structured
    ``{ok: False, ...}`` — never a silent accept.
    """
    if not isinstance(record, Mapping):
        return {"ok": False, "code": "invalid", "error": "record is not an object"}
    ok, reason = verify_introduction(record)
    if not ok:
        return {"ok": False, "code": "invalid", "error": reason}
    base = record.get("base_url")
    if not isinstance(base, str) or not base.strip():
        return {"ok": False, "code": "invalid", "error": "base_url missing"}
    try:
        assert_connect_destination(
            normalize_base_url(base),
            allow_local=allow_local,
            resolver=resolver,
        )
    except UnsafeUrlError as exc:
        return {"ok": False, "code": "refused", "error": str(exc)}
    if connect_fn is not None:
        return connect_fn(normalize_base_url(base))
    return dict(record)


__all__ = [
    "BIND_KEYS",
    "DEFAULT_LIMIT",
    "INTRODUCTIONS_PATH",
    "SCHEMA",
    "PeerIntroError",
    "accept_introduction",
    "canonical_introduction_message",
    "introduction_record",
    "public_introductions",
    "verify_introduction",
]
