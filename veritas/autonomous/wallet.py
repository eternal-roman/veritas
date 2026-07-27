"""Self-provisioned agent wallet: a real keypair, created locally.

Nothing in this repository could previously produce a receiving address —
`generate_local_seed` is a bare hash that was never a key, and
`zk_wallet.derive_stealth_address` deliberately raises because hash-derived
addresses have no private key and burn funds. This module provisions the
real thing with zero human input: `eth_account.Account.create()` → an
encrypted eth-keystore-v3 file plus a locally generated random passphrase,
both written with owner-only permissions.

Honest threat model: the passphrase sits beside the keystore, so this
protects a single leaked or backed-up file, NOT an attacker who can read
this host's filesystem. Production custody (managed signer, policy-bounded)
remains ROADMAP 3.2. Creating an address requires no human; funding it does.

Requires the ``signing`` extra (`pip install "veritas-research[signing]"`).
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KEYSTORE_NAME = "wallet.keystore.json"
PASSPHRASE_NAME = "wallet.passphrase"


class WalletError(ValueError):
    """Raised when wallet provisioning or loading cannot proceed."""


@dataclass(frozen=True)
class WalletInfo:
    """What the caller learns: the address and where the keystore lives.

    Never carries key material or the passphrase.
    """

    address: str
    keystore_path: str
    created: bool


def _require_eth_account() -> Any:
    try:
        from eth_account import Account
    except ImportError as exc:  # pragma: no cover - exercised via WalletError path
        raise WalletError(
            "eth_account is required for wallet provisioning; "
            "pip install 'veritas-research[signing]'"
        ) from exc
    return Account


def _write_owner_only(path: Path, content: str) -> None:
    # Permissions set at creation via os.open, not chmod-after-write, so the
    # file is never readable by others even for an instant.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)


def _stored_address(keystore_path: Path) -> str:
    keystore = json.loads(keystore_path.read_text())
    address = str(keystore.get("address", ""))
    if not address:
        raise WalletError(f"keystore at {keystore_path} carries no address")
    return address if address.startswith("0x") else f"0x{address}"


def ensure_wallet(
    base_dir: str | Path = ".veritas_agent",
    kdf: str | None = None,
    iterations: int | None = None,
) -> WalletInfo:
    """Create the agent's wallet if absent; reuse it if present.

    `kdf`/`iterations` exist so tests can use a fast KDF; the default is
    eth_account's scrypt parameters.
    """
    Account = _require_eth_account()
    base = Path(base_dir)
    keystore_path = base / KEYSTORE_NAME
    passphrase_path = base / PASSPHRASE_NAME

    if keystore_path.exists() and passphrase_path.exists():
        return WalletInfo(_stored_address(keystore_path), str(keystore_path), created=False)
    if keystore_path.exists() != passphrase_path.exists():
        raise WalletError(
            f"wallet state in {base} is partial (keystore or passphrase missing); "
            "refusing to overwrite key material"
        )

    base.mkdir(parents=True, exist_ok=True)
    account = Account.create()
    passphrase = secrets.token_urlsafe(32)
    encrypted = Account.encrypt(account.key, passphrase, kdf=kdf, iterations=iterations)
    _write_owner_only(keystore_path, json.dumps(encrypted))
    _write_owner_only(passphrase_path, passphrase)
    return WalletInfo(account.address, str(keystore_path), created=True)


def wallet_address(base_dir: str | Path = ".veritas_agent") -> str | None:
    """The receiving address, or None when no wallet has been provisioned."""
    keystore_path = Path(base_dir) / KEYSTORE_NAME
    if not keystore_path.exists():
        return None
    return _stored_address(keystore_path)


def load_signer(base_dir: str | Path = ".veritas_agent"):
    """Load the wallet as a buyer-side Signer (`LocalAccountSigner`).

    The key is decrypted in-process only at the moment of use — the same
    TESTNET/DEV caveat LocalAccountSigner itself carries.
    """
    Account = _require_eth_account()
    base = Path(base_dir)
    keystore_path = base / KEYSTORE_NAME
    passphrase_path = base / PASSPHRASE_NAME
    if not keystore_path.exists() or not passphrase_path.exists():
        raise WalletError(f"no provisioned wallet under {base}; run ensure_wallet first")

    key = Account.decrypt(json.loads(keystore_path.read_text()), passphrase_path.read_text())

    from veritas.buyer_payment import LocalAccountSigner

    return LocalAccountSigner("0x" + bytes(key).hex())
