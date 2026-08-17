"""Sign-In With X (SIWx) — offline message build and signature verify (M7).

SIWx binds a buyer address to a short-lived **session** that can spend prepaid
credits. This module only does local EIP-191 recovery of a SIWE-shaped
message; it does not call an RPC, facilitator, or IdP.

The message format follows the SIWE (EIP-4361) surface that SIWx generalises:
domain, address, URI, version, chain id, nonce, issued-at, expiration.

Signing verification requires optional ``eth_account`` (same optional as the
buyer signing path). Server import stays free of that dependency until a
session is actually verified.

Session/challenge storage uses per-call SQLite connections (threadpool-safe,
same pattern as ``veritas.ledger.Ledger``).
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .runtime import resolve_runtime_dir

_DB_FILENAME = "siwx_sessions.sqlite3"
_DEFAULT_TTL_SECONDS = 3600
_CHALLENGE_TTL_SECONDS = 300

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS siwx_challenges (
    nonce        TEXT PRIMARY KEY,
    domain       TEXT NOT NULL,
    address      TEXT,
    uri          TEXT NOT NULL,
    chain_id     TEXT NOT NULL,
    issued_at    TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS siwx_sessions (
    token_hash   TEXT PRIMARY KEY,
    address      TEXT NOT NULL,
    chain_id     TEXT NOT NULL,
    domain       TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS siwx_sessions_by_address ON siwx_sessions(address);
"""


class SiwxError(Exception):
    """Base for SIWx refusals."""


class SiwxVerifyError(SiwxError):
    """Signature or message did not verify."""


class SiwxSessionError(SiwxError):
    """Session missing, expired, or unusable."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_address(address: str) -> str:
    if not _ADDRESS_RE.match(address or ""):
        raise SiwxError("address must be 0x-prefixed 20-byte hex")
    return address.lower()


def build_siwx_message(
    *,
    domain: str,
    address: str,
    uri: str,
    chain_id: str | int,
    nonce: str,
    issued_at: str,
    expiration_time: str,
    statement: str = "Sign in to Veritas to spend prepaid credits.",
    version: str = "1",
) -> str:
    """Build an EIP-4361-shaped message string (SIWx / SIWE)."""
    addr = normalize_address(address)
    if not domain or not uri or not nonce:
        raise SiwxError("domain, uri, and nonce are required")
    return (
        f"{domain} wants you to sign in with your Ethereum account:\n"
        f"{addr}\n"
        f"\n"
        f"{statement}\n"
        f"\n"
        f"URI: {uri}\n"
        f"Version: {version}\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued_at}\n"
        f"Expiration Time: {expiration_time}\n"
        f"Resources:\n"
        f"- veritas:credits"
    )


def parse_siwx_message(message: str) -> dict[str, str]:
    """Extract fields from a SIWx message we produced (strict, not general SIWE)."""
    if not isinstance(message, str) or not message.strip():
        raise SiwxError("message must be non-empty text")
    lines = message.split("\n")
    if len(lines) < 10:
        raise SiwxError("message too short")
    domain_line = lines[0]
    if not domain_line.endswith(" wants you to sign in with your Ethereum account:"):
        raise SiwxError("domain line malformed")
    domain = domain_line[: -len(" wants you to sign in with your Ethereum account:")]
    address = normalize_address(lines[1].strip())
    fields: dict[str, str] = {"domain": domain, "address": address}
    for line in lines[2:]:
        if line.startswith("URI: "):
            fields["uri"] = line[5:]
        elif line.startswith("Version: "):
            fields["version"] = line[9:]
        elif line.startswith("Chain ID: "):
            fields["chain_id"] = line[10:]
        elif line.startswith("Nonce: "):
            fields["nonce"] = line[7:]
        elif line.startswith("Issued At: "):
            fields["issued_at"] = line[11:]
        elif line.startswith("Expiration Time: "):
            fields["expiration_time"] = line[17:]
    for required in (
        "uri", "version", "chain_id", "nonce", "issued_at", "expiration_time",
    ):
        if required not in fields:
            raise SiwxError(f"missing field {required}")
    return fields


def recover_siwx_signer(message: str, signature: str) -> str:
    """Recover the signing address from an EIP-191 personal_sign signature."""
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError as exc:
        raise SiwxVerifyError(
            "eth_account is required to verify SIWx signatures; "
            "pip install 'veritas-research[signing]'"
        ) from exc
    if not isinstance(signature, str) or not signature.startswith("0x"):
        raise SiwxVerifyError("signature must be 0x-prefixed hex")
    try:
        signable = encode_defunct(text=message)
        recovered = Account.recover_message(signable, signature=signature)
    except Exception as exc:  # eth_account raises varied types
        raise SiwxVerifyError(f"signature recovery failed: {exc}") from exc
    return normalize_address(recovered)


def verify_siwx(
    message: str,
    signature: str,
    *,
    expected_domain: str,
    expected_uri: str | None = None,
    expected_chain_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, str]:
    """Parse, time-check, domain-check, and recover the signer."""
    fields = parse_siwx_message(message)
    if fields["domain"] != expected_domain:
        raise SiwxVerifyError("domain mismatch")
    if expected_uri is not None and fields["uri"] != expected_uri:
        raise SiwxVerifyError("uri mismatch")
    if expected_chain_id is not None and str(fields["chain_id"]) != str(expected_chain_id):
        raise SiwxVerifyError("chain_id mismatch")
    clock = now or _now()
    try:
        exp = _parse_iso(fields["expiration_time"])
    except ValueError as exc:
        raise SiwxVerifyError("expiration_time unparseable") from exc
    if clock >= exp:
        raise SiwxVerifyError("SIWx message expired")
    recovered = recover_siwx_signer(message, signature)
    if recovered != fields["address"]:
        raise SiwxVerifyError("recovered address does not match message address")
    fields["recovered"] = recovered
    return fields


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SiwxSession:
    address: str
    chain_id: str
    domain: str
    expires_at: str
    created_at: str


class SiwxSessionStore:
    """Challenge + session store for SIWx-authenticated credit spending."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = resolve_runtime_dir(base_dir)

    @property
    def path(self) -> Path:
        return self.base_dir / _DB_FILENAME

    def _connect(self) -> sqlite3.Connection:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript(_SCHEMA)
        return conn

    def close(self) -> None:
        """No persistent connection; kept for test teardown symmetry."""

    def create_challenge(
        self,
        *,
        domain: str,
        uri: str,
        chain_id: str | int,
        address: str | None = None,
        ttl_seconds: int = _CHALLENGE_TTL_SECONDS,
    ) -> dict[str, Any]:
        nonce = secrets.token_hex(16)
        now = _now()
        exp = now + timedelta(seconds=ttl_seconds)
        addr = normalize_address(address) if address else None
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO siwx_challenges "
                "(nonce, domain, address, uri, chain_id, issued_at, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    nonce, domain, addr, uri, str(chain_id),
                    _iso(now), _iso(exp), _iso(now),
                ),
            )
        message: str | None = None
        if addr is not None:
            message = build_siwx_message(
                domain=domain,
                address=addr,
                uri=uri,
                chain_id=chain_id,
                nonce=nonce,
                issued_at=_iso(now),
                expiration_time=_iso(exp),
            )
        return {
            "nonce": nonce,
            "domain": domain,
            "uri": uri,
            "chain_id": str(chain_id),
            "issued_at": _iso(now),
            "expiration_time": _iso(exp),
            "address": addr,
            "message": message,
            "statement": "Sign in to Veritas to spend prepaid credits.",
        }

    def issue_session(
        self,
        *,
        message: str,
        signature: str,
        expected_domain: str,
        expected_uri: str | None = None,
        expected_chain_id: str | None = None,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> dict[str, Any]:
        """Verify signature, burn the challenge nonce once, issue a session.

        The nonce claim is ``BEGIN IMMEDIATE`` so two concurrent verifications
        of the same signed message cannot both obtain a session.
        """
        if ttl_seconds <= 0:
            raise SiwxError("session ttl_seconds must be positive")
        fields = verify_siwx(
            message,
            signature,
            expected_domain=expected_domain,
            expected_uri=expected_uri,
            expected_chain_id=expected_chain_id,
        )
        token = secrets.token_urlsafe(32)
        now = _now()
        exp = now + timedelta(seconds=ttl_seconds)
        with self._connect() as conn:
            try:
                # IMMEDIATE takes the write lock before the read so two
                # concurrent spends of one challenge cannot both see it free.
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM siwx_challenges WHERE nonce = ?",
                    (fields["nonce"],),
                ).fetchone()
                if row is None:
                    raise SiwxVerifyError("unknown or spent SIWx nonce")
                if row["domain"] != expected_domain:
                    raise SiwxVerifyError("challenge domain mismatch")
                if now >= _parse_iso(row["expires_at"]):
                    raise SiwxVerifyError("SIWx challenge expired")
                if row["address"] and row["address"] != fields["address"]:
                    raise SiwxVerifyError("challenge address mismatch")
                deleted = conn.execute(
                    "DELETE FROM siwx_challenges WHERE nonce = ?",
                    (fields["nonce"],),
                ).rowcount
                if deleted != 1:
                    raise SiwxVerifyError("unknown or spent SIWx nonce")
                conn.execute(
                    "INSERT INTO siwx_sessions "
                    "(token_hash, address, chain_id, domain, expires_at, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        _token_hash(token),
                        fields["address"],
                        fields["chain_id"],
                        expected_domain,
                        _iso(exp),
                        _iso(now),
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        return {
            "session_token": token,
            "address": fields["address"],
            "chain_id": fields["chain_id"],
            "domain": expected_domain,
            "expires_at": _iso(exp),
            "header": "X-VERITAS-SESSION",
        }

    def resolve(self, token: str) -> SiwxSession:
        """Resolve a bearer session token; expired and unknown are refused."""
        if not token or not isinstance(token, str):
            raise SiwxSessionError("session token required")
        th = _token_hash(token)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM siwx_sessions WHERE token_hash = ?",
                (th,),
            ).fetchone()
            if row is None:
                raise SiwxSessionError("unknown session")
            if _now() >= _parse_iso(row["expires_at"]):
                conn.execute(
                    "DELETE FROM siwx_sessions WHERE token_hash = ?",
                    (th,),
                )
                raise SiwxSessionError("session expired")
            return SiwxSession(
                address=row["address"],
                chain_id=row["chain_id"],
                domain=row["domain"],
                expires_at=row["expires_at"],
                created_at=row["created_at"],
            )
