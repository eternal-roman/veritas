"""Self-provisioned agent wallet: a real keypair, created locally.

Nothing in this repository could previously produce a receiving address —
`generate_local_seed` is a bare hash that was never a key, and
`zk_wallet.derive_stealth_address` deliberately raises because hash-derived
addresses have no private key and burn funds. This module provisions the
real thing with zero human input: `eth_account.Account.create()` → an
encrypted eth-keystore-v3 file plus a locally generated random passphrase,
both written owner-only **where the platform enforces POSIX mode bits**.

Honest threat model: the passphrase sits beside the keystore, so this
protects a single leaked or backed-up file, NOT an attacker who can read
this host's filesystem. Production custody (managed signer, policy-bounded)
remains ROADMAP 3.2. Creating an address requires no human; funding it does.

Platform limit, stated rather than hidden: `os.open(..., 0o600)` is ignored
on Windows and on filesystems that do not carry mode bits (FAT/exFAT, some
bind-mounted volumes). There the keystore and its plaintext passphrase are
left at whatever the filesystem grants — commonly world-readable. We do not
silently pretend otherwise: the mode is read back after every write and a
`WalletPermissionWarning` names the file that is unprotected. Deploy on a
POSIX filesystem, or supply custody the operating system can actually
enforce.

Requires the ``signing`` extra (`pip install "veritas-research[signing]"`).
"""

from __future__ import annotations

import json
import os
import secrets
import stat
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KEYSTORE_NAME = "wallet.keystore.json"
PASSPHRASE_NAME = "wallet.passphrase"


class WalletError(ValueError):
    """Raised when wallet provisioning or loading cannot proceed."""


class WalletPermissionWarning(UserWarning):
    """Key material was written where the OS will not restrict access to it.

    A warning rather than an error: refusing outright would make the agent
    unprovisionable on Windows, and a developer wallet there is legitimate.
    Never ignore it for a wallet holding real funds.
    """


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
    """Write key material owner-only, and say so when that did not happen.

    Permissions are set at creation via `os.open`, not chmod-after-write, so
    on POSIX the file is never readable by others even for an instant. The
    mode argument is advisory, though: Windows ignores it outright and
    mode-less filesystems drop it. Reading the mode back is what separates
    "protected" from "we asked politely" — without it this function's name is
    a claim we never checked.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)

    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        warnings.warn(
            f"{path.name} holds wallet key material but its permissions are "
            f"{oct(mode)}, not 0o600: this platform or filesystem does not "
            "enforce POSIX mode bits, so the file is readable beyond its "
            "owner. Treat this wallet as development-only.",
            WalletPermissionWarning,
            stacklevel=3,
        )


def _stored_address(keystore_path: Path) -> str:
    keystore = json.loads(keystore_path.read_text(encoding="utf-8"))
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

    key = Account.decrypt(
        json.loads(keystore_path.read_text(encoding="utf-8")),
        passphrase_path.read_text(encoding="utf-8"),
    )

    from veritas.buyer_payment import LocalAccountSigner

    return LocalAccountSigner("0x" + bytes(key).hex())


def sign_personal_message(base_dir: str | Path, message: str) -> tuple[str, str]:
    """EIP-191 personal_sign over text using the local commerce wallet.

    Returns ``(address, signature)``. Decrypts the same keystore ``load_signer``
    uses; does not go through the payment Signer seam (typed data only).
    """
    from eth_account.messages import encode_defunct

    Account = _require_eth_account()
    base = Path(base_dir)
    keystore_path = base / KEYSTORE_NAME
    passphrase_path = base / PASSPHRASE_NAME
    if not keystore_path.exists() or not passphrase_path.exists():
        raise WalletError(f"no provisioned wallet under {base}; run ensure_wallet first")
    key = Account.decrypt(
        json.loads(keystore_path.read_text(encoding="utf-8")),
        passphrase_path.read_text(encoding="utf-8"),
    )
    account = Account.from_key(key)
    signature = account.sign_message(encode_defunct(text=message)).signature
    return account.address, "0x" + signature.hex().removeprefix("0x")
