"""Signed public-URL introductions: PEX-style, no registry, no LAN leak."""

from __future__ import annotations

import ipaddress

import pytest

eth_account = pytest.importorskip("eth_account")

from veritas.peer_intro import (  # noqa: E402
    DEFAULT_LIMIT,
    SCHEMA,
    PeerIntroError,
    accept_introduction,
    introduction_record,
    public_introductions,
    verify_introduction,
)


def _sign(acct, message: str) -> str:
    from eth_account.messages import encode_defunct

    signed = acct.sign_message(encode_defunct(text=message))
    return "0x" + signed.signature.hex().removeprefix("0x")


def _signer():
    acct = eth_account.Account.create()

    def sign_text(message: str) -> str:
        return _sign(acct, message)

    return acct, sign_text


def _resolver(host, port):
    """IP literals stay themselves; hostnames resolve to a public address."""
    try:
        ipaddress.ip_address(host)
        return [(2, 1, 6, "", (host, 0))]
    except ValueError:
        return [(2, 1, 6, "", ("93.184.216.34", 0))]


def _row(base_url: str, peer_id: str | None = None, **extra):
    row = {"base_url": base_url, "peer_id": peer_id or base_url}
    row.update(extra)
    return row


def test_public_introductions_excludes_rfc1918_loopback_and_metadata():
    acct, sign_text = _signer()
    peers = [
        _row("http://10.0.0.5:8080", "rfc1918-10"),
        _row("http://192.168.1.10", "rfc1918-192"),
        _row("http://172.16.0.1", "rfc1918-172"),
        _row("http://127.0.0.1:8765", "loopback"),
        _row("http://169.254.169.254/latest/meta-data", "metadata"),
        _row("https://example.com", "public"),
    ]
    cards = public_introductions(
        peers,
        sign_text=sign_text,
        introducer_address=acct.address,
        resolver=_resolver,
    )
    urls = [card["base_url"] for card in cards]
    assert urls == ["https://example.com"]
    assert all(card["schema"] == SCHEMA for card in cards)
    assert all(card["introducer"] == acct.address.lower() for card in cards)


def test_public_introductions_includes_https_example_com():
    acct, sign_text = _signer()
    cards = public_introductions(
        [_row("https://example.com", "ex")],
        sign_text=sign_text,
        introducer_address=acct.address,
        resolver=_resolver,
    )
    assert len(cards) == 1
    assert cards[0]["base_url"] == "https://example.com"
    assert cards[0]["peer_id"] == "ex"
    assert cards[0]["signature"].startswith("0x")


def test_verify_accepts_a_signed_record():
    acct, sign_text = _signer()
    record = introduction_record(
        _row("https://example.com", "ex", identity_hash="sha256:peer"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    ok, reason = verify_introduction(record)
    assert ok is True, reason
    assert reason == "ok"
    ok_expected, _ = verify_introduction(
        record, expected_introducer=acct.address
    )
    assert ok_expected is True


def test_verify_rejects_tampered_base_url():
    acct, sign_text = _signer()
    record = introduction_record(
        _row("https://example.com", "ex"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    tampered = dict(record)
    tampered["base_url"] = "https://evil.example"
    ok, reason = verify_introduction(tampered)
    assert ok is False
    assert reason


def test_public_introductions_caps_at_32():
    acct, sign_text = _signer()
    peers = [_row(f"https://p{i}.example.com", f"p{i}") for i in range(40)]
    cards = public_introductions(
        peers,
        sign_text=sign_text,
        introducer_address=acct.address,
        resolver=_resolver,
    )
    assert len(cards) == DEFAULT_LIMIT == 32
    limited = public_introductions(
        peers,
        limit=5,
        sign_text=sign_text,
        introducer_address=acct.address,
        resolver=_resolver,
    )
    assert len(limited) == 5


def test_unsigned_and_missing_signer_fail_closed():
    acct, sign_text = _signer()
    with pytest.raises(PeerIntroError):
        introduction_record(_row("https://example.com", "ex"))
    assert public_introductions([_row("https://example.com", "ex")]) == []
    record = introduction_record(
        _row("https://example.com", "ex"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    unsigned = dict(record)
    unsigned.pop("signature")
    ok, reason = verify_introduction(unsigned)
    assert ok is False
    assert "signature" in reason


def test_verify_without_eth_account_fails_closed(monkeypatch):
    acct, sign_text = _signer()
    record = introduction_record(
        _row("https://example.com", "ex"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    monkeypatch.setattr("veritas.peer_intro._eth_account_modules", lambda: None)
    ok, reason = verify_introduction(record)
    assert ok is False
    assert "eth_account" in reason
    with pytest.raises(PeerIntroError):
        introduction_record(
            _row("https://example.com", "ex"),
            sign_text=sign_text,
            introducer_address=acct.address,
        )


def test_accept_introduction_verifies_then_connects():
    acct, sign_text = _signer()
    record = introduction_record(
        _row("https://example.com", "ex"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    seen: list[str] = []

    def connect_fn(base_url: str):
        seen.append(base_url)
        return {"ok": True, "base_url": base_url}

    result = accept_introduction(record, connect_fn=connect_fn, resolver=_resolver)
    assert result["ok"] is True
    assert seen == ["https://example.com"]


def test_accept_introduction_refuses_lan_and_does_not_fetch():
    acct, sign_text = _signer()
    # Sign a LAN row directly (public_introductions would have dropped it).
    record = introduction_record(
        _row("http://192.168.1.50:8080", "lan"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    called = []
    result = accept_introduction(
        record,
        connect_fn=lambda url: called.append(url) or {"ok": True},
        allow_local=False,
        resolver=_resolver,
    )
    assert result["ok"] is False
    assert result["code"] == "refused"
    assert called == []


def test_accept_introduction_returns_record_when_no_connect_fn():
    acct, sign_text = _signer()
    record = introduction_record(
        _row("https://example.com", "ex"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    accepted = accept_introduction(record, resolver=_resolver)
    assert accepted["base_url"] == "https://example.com"
    assert accepted["signature"] == record["signature"]


def test_accept_rejects_bad_signature_without_connecting():
    acct, sign_text = _signer()
    record = introduction_record(
        _row("https://example.com", "ex"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    record = dict(record)
    record["base_url"] = "https://other.example"
    called = []
    result = accept_introduction(
        record, connect_fn=lambda url: called.append(url), resolver=_resolver
    )
    assert result["ok"] is False
    assert result["code"] == "invalid"
    assert called == []


def test_wrong_expected_introducer_is_rejected():
    acct, sign_text = _signer()
    other = eth_account.Account.create()
    record = introduction_record(
        _row("https://example.com", "ex"),
        sign_text=sign_text,
        introducer_address=acct.address,
    )
    ok, reason = verify_introduction(record, expected_introducer=other.address)
    assert ok is False
    assert reason
