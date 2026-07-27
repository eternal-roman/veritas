"""Wallet self-provisioning: an agent mints its own keypair, locally.

Before this module no code in the repository could produce a receiving
address — `generate_local_seed` is a bare hash that was never a key, and
`derive_stealth_address` deliberately raises because hash-derived addresses
burn funds. These tests pin the real thing: a locally created eth keypair,
persisted as an encrypted keystore with owner-only permissions, whose key
material never leaves disk. Funding the wallet remains external — creating
an address requires no human; filling it does.
"""

from __future__ import annotations

import json
import stat

import pytest

eth_account = pytest.importorskip("eth_account")

from veritas.autonomous.wallet import (  # noqa: E402
    WalletError,
    ensure_wallet,
    load_signer,
)

FAST_KDF = {"kdf": "pbkdf2", "iterations": 100}


def test_ensure_wallet_creates_keypair_without_input(tmp_path):
    info = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    assert info.created is True
    assert info.address.startswith("0x") and len(info.address) == 42
    keystore = json.loads((tmp_path / "wallet.keystore.json").read_text())
    assert keystore["crypto"], "not an encrypted keystore"


def test_ensure_wallet_is_idempotent(tmp_path):
    first = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    second = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    assert second.created is False
    assert second.address.lower() == first.address.lower()


def test_keystore_files_are_owner_only(tmp_path):
    ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    for name in ("wallet.keystore.json", "wallet.passphrase"):
        mode = stat.S_IMODE((tmp_path / name).stat().st_mode)
        assert mode == 0o600, f"{name} has mode {oct(mode)}"


def test_wallet_key_material_stays_on_disk(tmp_path):
    """The returned WalletInfo exposes the address and file location, never
    the private key or passphrase."""
    info = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    exposed = vars(info) if hasattr(info, "__dict__") else info._asdict()
    dumped = json.dumps({k: str(v) for k, v in exposed.items()})
    passphrase = (tmp_path / "wallet.passphrase").read_text()
    assert passphrase not in dumped
    assert set(exposed) == {"address", "keystore_path", "created"}


def test_wallet_signer_signs_for_buyer_payment(tmp_path):
    """The provisioned wallet must plug straight into the existing buyer
    path: load_signer returns a Signer whose address matches the wallet."""
    info = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    signer = load_signer(base_dir=tmp_path)
    assert signer.address.lower() == info.address.lower()


def test_missing_wallet_fails_with_named_error(tmp_path):
    with pytest.raises(WalletError):
        load_signer(base_dir=tmp_path / "nowhere")
