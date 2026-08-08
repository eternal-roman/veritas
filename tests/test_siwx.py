"""M7 SIWx: EIP-4361 message build/verify, EIP-191 recover, offline store.

Acceptance for package M7.2:
- build/verify EIP-4361-shaped message + EIP-191 recover
- challenge nonce one-time
- session token resolve
- expired / unknown refused
- no RPC or facilitator in veritas.siwx
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from veritas.siwx import (
    SiwxError,
    SiwxSessionError,
    SiwxSessionStore,
    SiwxVerifyError,
    build_siwx_message,
    parse_siwx_message,
    recover_siwx_signer,
    verify_siwx,
)

eth_account = pytest.importorskip("eth_account")


DOMAIN = "research.example.org"
URI = "https://research.example.org/v1/siwx/verify"
CHAIN = "84532"


def _sig_hex(signed) -> str:
    sig = signed.signature.hex()
    return sig if sig.startswith("0x") else "0x" + sig


def _sign(acct, message: str) -> str:
    from eth_account.messages import encode_defunct

    return _sig_hex(acct.sign_message(encode_defunct(text=message)))


def _signed_session(tmp_path, acct=None, *, ttl_seconds: int = 3600):
    acct = acct or eth_account.Account.create()
    store = SiwxSessionStore(tmp_path)
    challenge = store.create_challenge(
        domain=DOMAIN,
        uri=URI,
        chain_id=CHAIN,
        address=acct.address,
    )
    assert challenge["message"]
    session = store.issue_session(
        message=challenge["message"],
        signature=_sign(acct, challenge["message"]),
        expected_domain=DOMAIN,
        expected_uri=URI,
        expected_chain_id=CHAIN,
        ttl_seconds=ttl_seconds,
    )
    return store, session, acct


# --- pure message / recover (no store) ---------------------------------------


def test_build_and_verify_roundtrip():
    acct = eth_account.Account.create()
    msg = build_siwx_message(
        domain=DOMAIN,
        address=acct.address,
        uri=URI,
        chain_id=CHAIN,
        nonce="abc123",
        issued_at="2026-08-08T00:00:00Z",
        expiration_time="2099-01-01T00:00:00Z",
    )
    fields = verify_siwx(
        msg,
        _sign(acct, msg),
        expected_domain=DOMAIN,
        expected_uri=URI,
        expected_chain_id=CHAIN,
    )
    assert fields["recovered"] == acct.address.lower()
    assert fields["nonce"] == "abc123"
    assert fields["chain_id"] == CHAIN


def test_parse_siwx_message_fields():
    msg = build_siwx_message(
        domain=DOMAIN,
        address="0x" + "ab" * 20,
        uri=URI,
        chain_id=84532,
        nonce="n-parse",
        issued_at="2026-08-08T00:00:00Z",
        expiration_time="2099-01-01T00:00:00Z",
    )
    fields = parse_siwx_message(msg)
    assert fields["domain"] == DOMAIN
    assert fields["address"] == ("0x" + "ab" * 20)
    assert fields["uri"] == URI
    assert fields["nonce"] == "n-parse"
    assert fields["version"] == "1"


def test_eip191_recover_matches_signer():
    acct = eth_account.Account.create()
    msg = build_siwx_message(
        domain=DOMAIN,
        address=acct.address,
        uri=URI,
        chain_id=CHAIN,
        nonce="rec1",
        issued_at="2026-08-08T00:00:00Z",
        expiration_time="2099-01-01T00:00:00Z",
    )
    recovered = recover_siwx_signer(msg, _sign(acct, msg))
    assert recovered == acct.address.lower()


def test_wrong_signer_rejected():
    acct = eth_account.Account.create()
    other = eth_account.Account.create()
    msg = build_siwx_message(
        domain=DOMAIN,
        address=acct.address,
        uri=URI,
        chain_id=CHAIN,
        nonce="n1",
        issued_at="2026-08-08T00:00:00Z",
        expiration_time="2099-01-01T00:00:00Z",
    )
    with pytest.raises(SiwxVerifyError):
        verify_siwx(msg, _sign(other, msg), expected_domain=DOMAIN)


def test_domain_mismatch_rejected():
    acct = eth_account.Account.create()
    msg = build_siwx_message(
        domain=DOMAIN,
        address=acct.address,
        uri=URI,
        chain_id=CHAIN,
        nonce="n-dom",
        issued_at="2026-08-08T00:00:00Z",
        expiration_time="2099-01-01T00:00:00Z",
    )
    with pytest.raises(SiwxVerifyError, match="domain"):
        verify_siwx(msg, _sign(acct, msg), expected_domain="other.example")


def test_expired_message_refused():
    acct = eth_account.Account.create()
    msg = build_siwx_message(
        domain=DOMAIN,
        address=acct.address,
        uri=URI,
        chain_id=CHAIN,
        nonce="n-exp",
        issued_at="2020-01-01T00:00:00Z",
        expiration_time="2020-01-01T00:05:00Z",
    )
    with pytest.raises(SiwxVerifyError, match="expired"):
        verify_siwx(
            msg,
            _sign(acct, msg),
            expected_domain=DOMAIN,
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
        )


def test_malformed_address_refused():
    with pytest.raises(SiwxError):
        build_siwx_message(
            domain=DOMAIN,
            address="not-an-address",
            uri=URI,
            chain_id=CHAIN,
            nonce="x",
            issued_at="2026-08-08T00:00:00Z",
            expiration_time="2099-01-01T00:00:00Z",
        )


def test_garbage_signature_refused():
    acct = eth_account.Account.create()
    msg = build_siwx_message(
        domain=DOMAIN,
        address=acct.address,
        uri=URI,
        chain_id=CHAIN,
        nonce="n-g",
        issued_at="2026-08-08T00:00:00Z",
        expiration_time="2099-01-01T00:00:00Z",
    )
    with pytest.raises(SiwxVerifyError):
        verify_siwx(msg, "0xdead", expected_domain=DOMAIN)
    with pytest.raises(SiwxVerifyError):
        verify_siwx(msg, "not-hex", expected_domain=DOMAIN)


# --- store: challenge / session ----------------------------------------------


def test_session_issue_and_resolve(tmp_path):
    store, session, acct = _signed_session(tmp_path)
    resolved = store.resolve(session["session_token"])
    assert resolved.address == acct.address.lower()
    assert resolved.domain == DOMAIN
    assert resolved.chain_id == CHAIN
    assert session["header"] == "X-VERITAS-SESSION"
    store.close()


def test_unknown_session_refused(tmp_path):
    store = SiwxSessionStore(tmp_path)
    with pytest.raises(SiwxSessionError, match="unknown"):
        store.resolve("not-a-real-token")
    with pytest.raises(SiwxSessionError):
        store.resolve("")
    store.close()


def test_expired_session_refused(tmp_path):
    store, session, _acct = _signed_session(tmp_path, ttl_seconds=3600)
    # Force expiry in the store without sleeping.
    th = __import__("hashlib").sha256(
        session["session_token"].encode("utf-8")
    ).hexdigest()
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace(
        "+00:00", "Z"
    )
    import sqlite3

    conn = sqlite3.connect(str(Path(tmp_path) / "siwx_sessions.sqlite3"))
    conn.execute(
        "UPDATE siwx_sessions SET expires_at = ? WHERE token_hash = ?",
        (past, th),
    )
    conn.commit()
    conn.close()
    with pytest.raises(SiwxSessionError, match="expired"):
        store.resolve(session["session_token"])
    # Second resolve: row may be deleted; still refused (unknown or expired).
    with pytest.raises(SiwxSessionError):
        store.resolve(session["session_token"])
    store.close()


def test_challenge_nonce_one_time(tmp_path):
    acct = eth_account.Account.create()
    store = SiwxSessionStore(tmp_path)
    challenge = store.create_challenge(
        domain=DOMAIN, uri=URI, chain_id=CHAIN, address=acct.address,
    )
    sig = _sign(acct, challenge["message"])
    store.issue_session(
        message=challenge["message"],
        signature=sig,
        expected_domain=DOMAIN,
        expected_uri=URI,
        expected_chain_id=CHAIN,
    )
    with pytest.raises(SiwxVerifyError, match="nonce|spent|unknown"):
        store.issue_session(
            message=challenge["message"],
            signature=sig,
            expected_domain=DOMAIN,
            expected_uri=URI,
            expected_chain_id=CHAIN,
        )
    store.close()


def test_unknown_nonce_refused(tmp_path):
    acct = eth_account.Account.create()
    store = SiwxSessionStore(tmp_path)
    # Message with a nonce never issued as a challenge.
    msg = build_siwx_message(
        domain=DOMAIN,
        address=acct.address,
        uri=URI,
        chain_id=CHAIN,
        nonce="never-issued-nonce",
        issued_at="2026-08-08T00:00:00Z",
        expiration_time="2099-01-01T00:00:00Z",
    )
    with pytest.raises(SiwxVerifyError, match="nonce|unknown|spent"):
        store.issue_session(
            message=msg,
            signature=_sign(acct, msg),
            expected_domain=DOMAIN,
            expected_uri=URI,
            expected_chain_id=CHAIN,
        )
    store.close()


def test_expired_challenge_refused(tmp_path):
    acct = eth_account.Account.create()
    store = SiwxSessionStore(tmp_path)
    challenge = store.create_challenge(
        domain=DOMAIN,
        uri=URI,
        chain_id=CHAIN,
        address=acct.address,
        ttl_seconds=300,
    )
    # Backdate challenge expiry in the DB; keep message signature valid long-term.
    import sqlite3

    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace(
        "+00:00", "Z"
    )
    conn = sqlite3.connect(str(Path(tmp_path) / "siwx_sessions.sqlite3"))
    conn.execute(
        "UPDATE siwx_challenges SET expires_at = ? WHERE nonce = ?",
        (past, challenge["nonce"]),
    )
    conn.commit()
    conn.close()
    # Message still has future expiration so verify_siwx passes; store refuses.
    with pytest.raises(SiwxVerifyError, match="challenge expired|expired"):
        store.issue_session(
            message=challenge["message"],
            signature=_sign(acct, challenge["message"]),
            expected_domain=DOMAIN,
            expected_uri=URI,
            expected_chain_id=CHAIN,
        )
    store.close()


def test_challenge_without_address_builds_no_message(tmp_path):
    store = SiwxSessionStore(tmp_path)
    challenge = store.create_challenge(domain=DOMAIN, uri=URI, chain_id=CHAIN)
    assert challenge["message"] is None
    assert challenge["nonce"]
    assert challenge["address"] is None
    store.close()


def test_session_ttl_must_be_positive(tmp_path):
    acct = eth_account.Account.create()
    store = SiwxSessionStore(tmp_path)
    challenge = store.create_challenge(
        domain=DOMAIN, uri=URI, chain_id=CHAIN, address=acct.address,
    )
    with pytest.raises(SiwxError, match="ttl"):
        store.issue_session(
            message=challenge["message"],
            signature=_sign(acct, challenge["message"]),
            expected_domain=DOMAIN,
            expected_uri=URI,
            expected_chain_id=CHAIN,
            ttl_seconds=0,
        )
    store.close()


def test_module_has_no_rpc_or_facilitator():
    """Offline constraint: module-level imports exclude facilitator / HTTP / RPC."""
    import veritas.siwx as siwx

    # Only lines before the first function/class body — module-level imports.
    src = Path(inspect.getsourcefile(siwx)).read_text(encoding="utf-8")
    head = src.split("class SiwxError", 1)[0]
    top_imports = "\n".join(
        line
        for line in head.splitlines()
        if line.startswith(("import ", "from "))
    )
    for token in (
        "facilitator", "web3", "httpx", "aiohttp", "urllib", "requests",
        "eth_account",
    ):
        assert token not in top_imports, f"banned top-level import: {token}"
