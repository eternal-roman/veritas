"""Hiding wallet commitments for JIT packets.

WHAT THIS IS: a hiding, binding commitment to a payout address, so a publicly
broadcast offer does not leak the address that will receive funds, plus a
keyed proof of knowledge of the opening.

WHAT THIS IS NOT: a zero-knowledge proof system. The previous version claimed
"ZK-style" privacy and had two fatal flaws that this module fixes:

1. It published the blinding `salt` alongside the commitment. A commitment
   H(salt || address || network) with a public salt is trivially brute-forced
   by enumerating candidate addresses — it provided no hiding whatsoever
   against the only adversary that matters (someone with a list of addresses).
   The salt is now private and never leaves the holder until opening.

2. Its "proof" verified only that c == H(commitment || R), which a forger can
   satisfy from the commitment alone by picking any R; the response `s` was
   never checked. It proved nothing. Proof of knowledge is now a keyed MAC
   over a caller-supplied challenge, which cannot be produced without the
   secret salt.

A true zero-knowledge preimage proof requires a circuit (Groth16/PLONK) and is
out of scope; the interface below is designed so such a backend can replace
`prove`/`verify_proof` without changing callers.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import asdict, dataclass
from typing import Any

SCHEME = "hiding-commit-hmac-v2"
SALT_BYTES = 32


def _mac(key: bytes, message: bytes) -> bytes:
    return hmac.new(key, message, hashlib.sha256).digest()


def _commitment_bytes(salt: bytes, address: str, network: str) -> bytes:
    """C = HMAC(salt, address || network). Hiding while salt is secret; binding by MAC."""
    return _mac(salt, address.lower().encode() + b"|" + network.encode())


@dataclass
class WalletCommitment:
    """The PUBLIC half. Safe to broadcast: contains no salt and no address."""
    commitment: str
    network: str
    scheme: str = SCHEME

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WalletOpening:
    """The PRIVATE half. Never transmit until settlement requires disclosure."""
    salt: bytes
    address: str
    network: str

    def reveal(self) -> dict[str, str]:
        return {"salt": self.salt.hex(), "address": self.address, "network": self.network}


def commit_wallet(
    address: str,
    network: str = "eip155:8453",
    salt: bytes | None = None,
) -> tuple[WalletCommitment, WalletOpening]:
    """Commit to a payout address. Returns (public commitment, private opening)."""
    if not address:
        raise ValueError("address is required")
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    if len(salt) < SALT_BYTES:
        raise ValueError(f"salt must be at least {SALT_BYTES} bytes to be hiding")

    commitment = _commitment_bytes(salt, address, network)
    return (
        WalletCommitment(commitment=commitment.hex(), network=network),
        WalletOpening(salt=salt, address=address, network=network),
    )


def prove(opening: WalletOpening, challenge: bytes) -> str:
    """Prove knowledge of the opening against a verifier-supplied challenge.

    The challenge must be fresh and chosen by the verifier (or bound to unique
    packet context) — a replayed challenge admits a replayed proof.
    """
    if not challenge:
        raise ValueError("challenge is required; a static challenge permits replay")
    return _mac(opening.salt, b"pok|" + challenge).hex()


def verify_proof(
    commitment: WalletCommitment,
    challenge: bytes,
    proof: str,
    opening: WalletOpening,
) -> bool:
    """Verify a proof. Requires the opening, so this is holder-side or post-reveal.

    Honest limitation: without a real ZK circuit, a third party cannot verify
    knowledge of the salt without learning it. Callers who need public
    verifiability must wait for the reveal at settlement (`open_commitment`).
    """
    try:
        expected = _mac(opening.salt, b"pok|" + challenge).hex()
        if not hmac.compare_digest(expected, proof):
            return False
        return verify_commitment(commitment, opening)
    except (TypeError, ValueError):
        return False


def verify_commitment(commitment: WalletCommitment, opening: WalletOpening) -> bool:
    """Check that an opening actually opens a commitment."""
    try:
        expected = _commitment_bytes(opening.salt, opening.address, opening.network)
        return hmac.compare_digest(expected.hex(), commitment.commitment)
    except (TypeError, ValueError, AttributeError):
        return False


def open_commitment(commitment: WalletCommitment, opening: WalletOpening) -> str | None:
    """Reveal the address at settlement, returning it only if it opens correctly."""
    if not verify_commitment(commitment, opening):
        return None
    return opening.address


def verify_revealed(commitment: WalletCommitment, salt_hex: str, address: str) -> bool:
    """Third-party check once the holder has revealed (salt, address)."""
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    expected = _commitment_bytes(salt, address, commitment.network)
    return hmac.compare_digest(expected.hex(), commitment.commitment)


def derive_stealth_address(*_args, **_kwargs):
    """Removed: the previous implementation burned funds.

    It derived an 'address' by hashing, so no private key existed for it. Any
    payment sent there is permanently unrecoverable. Real EVM stealth addresses
    (ERC-5564) require secp256k1 point arithmetic; use a library that
    implements it rather than a hash.
    """
    raise NotImplementedError(
        "derive_stealth_address was unsafe: hash-derived addresses have no "
        "private key and burn any funds sent to them. Use an ERC-5564 "
        "implementation with real secp256k1 arithmetic."
    )


if __name__ == "__main__":
    addr = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
    wc, opening = commit_wallet(addr)
    print("Public commitment (safe to broadcast):", wc.to_dict())
    challenge = secrets.token_bytes(16)
    proof = prove(opening, challenge)
    print("Proof verifies:", verify_proof(wc, challenge, proof, opening))
    print("Opened address:", open_commitment(wc, opening))
    print("Third-party check after reveal:", verify_revealed(wc, opening.salt.hex(), addr))
    print("Wrong address rejected:", verify_revealed(wc, opening.salt.hex(), "0x" + "0" * 40))
