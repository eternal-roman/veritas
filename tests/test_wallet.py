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
import os
import stat
import warnings

import pytest

eth_account = pytest.importorskip("eth_account")

from veritas.autonomous.wallet import (  # noqa: E402
    WalletError,
    WalletPermissionWarning,
    ensure_wallet,
    load_signer,
)

FAST_KDF = {"kdf": "pbkdf2", "iterations": 100}


def test_ensure_wallet_creates_keypair_without_input(tmp_path):
    info = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    assert info.created is True
    assert info.address.startswith("0x") and len(info.address) == 42
    keystore = json.loads((tmp_path / "wallet.keystore.json").read_text(encoding="utf-8"))
    assert keystore["crypto"], "not an encrypted keystore"


def test_ensure_wallet_is_idempotent(tmp_path):
    first = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    second = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    assert second.created is False
    assert second.address.lower() == first.address.lower()


KEY_MATERIAL_FILES = ("wallet.keystore.json", "wallet.passphrase")


def test_keystore_files_are_owner_only_or_say_they_are_not(tmp_path):
    """Key material is owner-only, and where the OS refuses to make it so, the
    caller is told.

    Asserting `0o600` unconditionally is a test that only passes where the
    property is free: Windows ignores the mode argument entirely (observed
    `0o666`), so on that platform the old assertion failed while the *code*
    was doing everything it could. Weakening it to "whatever the platform
    gives" would have been worse — it would let a silently world-readable
    passphrase pass as protected. So the invariant is stated as the
    disjunction that is actually true on every platform: either the mode is
    owner-only, or a WalletPermissionWarning named the file that is not.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ensure_wallet(base_dir=tmp_path, **FAST_KDF)

    unprotected = {
        w.message.args[0].split()[0]
        for w in caught
        if isinstance(w.message, WalletPermissionWarning)
    }

    for name in KEY_MATERIAL_FILES:
        mode = stat.S_IMODE((tmp_path / name).stat().st_mode)
        if mode & 0o077:
            assert name in unprotected, (
                f"{name} has mode {oct(mode)} — readable beyond its owner — and "
                "nothing warned about it. Silent unprotected key material is the "
                "one outcome this test exists to forbid."
            )
        else:
            assert mode == 0o600, f"{name} has mode {oct(mode)}"
            assert name not in unprotected, f"{name} is owner-only but warned anyway"


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits are not enforced here")
def test_keystore_files_are_owner_only_on_posix(tmp_path):
    """On the platform we actually deploy to, the mode is not negotiable."""
    ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    for name in KEY_MATERIAL_FILES:
        mode = stat.S_IMODE((tmp_path / name).stat().st_mode)
        assert mode == 0o600, f"{name} has mode {oct(mode)}"


def test_wallet_key_material_stays_on_disk(tmp_path):
    """The returned WalletInfo exposes the address and file location, never
    the private key or passphrase."""
    info = ensure_wallet(base_dir=tmp_path, **FAST_KDF)
    exposed = vars(info) if hasattr(info, "__dict__") else info._asdict()
    dumped = json.dumps({k: str(v) for k, v in exposed.items()})
    passphrase = (tmp_path / "wallet.passphrase").read_text(encoding="utf-8")
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
