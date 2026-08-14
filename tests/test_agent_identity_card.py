"""Wallet-signed ecosystem identity: did:pkh + EIP-191, not ERC-8004."""

from __future__ import annotations

import pytest

eth_account = pytest.importorskip("eth_account")

from veritas.agent_identity_card import (  # noqa: E402
    IDENTITY_SCHEMA,
    issue_identity_card,
    verify_identity_card,
)
from veritas.autonomous.wallet import ensure_wallet, sign_personal_message  # noqa: E402

FAST_KDF = {"kdf": "pbkdf2", "iterations": 100}


def test_identity_card_recovers_commerce_address(tmp_path):
    info = ensure_wallet(base_dir=tmp_path, **FAST_KDF)

    def sign_text(message: str) -> str:
        _, sig = sign_personal_message(tmp_path, message)
        return sig

    card = issue_identity_card(
        agent_id="alice",
        did_plane="did:veritas:plane:alice",
        commerce_address=info.address,
        network="eip155:84532",
        sign_text=sign_text,
    )
    assert card["schema"] == IDENTITY_SCHEMA
    assert card["did_pkh"] == f"did:pkh:eip155:84532:{info.address.lower()}"
    assert card["not_erc8004"] is True
    ok, reason = verify_identity_card(card)
    assert ok is True, reason


def test_tampered_identity_card_fails(tmp_path):
    info = ensure_wallet(base_dir=tmp_path, **FAST_KDF)

    def sign_text(message: str) -> str:
        _, sig = sign_personal_message(tmp_path, message)
        return sig

    card = issue_identity_card(
        agent_id="alice",
        did_plane="did:veritas:plane:alice",
        commerce_address=info.address,
        network="eip155:84532",
        sign_text=sign_text,
    )
    card["agent_id"] = "mallory"
    ok, reason = verify_identity_card(card)
    assert ok is False
    assert reason
