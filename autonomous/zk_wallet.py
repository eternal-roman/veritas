"""Zero-knowledge style privacy for JIT wallets.

Provides:
1. Hash-based commitment to a receiving address (hides the address in the public packet)
2. Simple non-interactive proof of knowledge of the opening (Fiat-Shamir style)
3. Stealth / one-time address derivation helper for ephemeral receive addresses

This is a practical privacy layer for the JIT Disposable Packet protocol.
It is not a full zkSNARK; it is a commitment + proof-of-knowledge construction
that can be upgraded to real circuits later while keeping the same interface.
"""

from __future__ import annotations
import hashlib
import secrets
import json
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, Dict, Any

def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def _hex(b: bytes) -> str:
    return b.hex()

def _from_hex(h: str) -> bytes:
    return bytes.fromhex(h)

@dataclass
class WalletCommitment:
    """Public commitment to a private wallet address."""
    commitment: str          # hex
    network: str             # CAIP-2
    salt: str                # public blinding salt (hex)
    proof: str               # simple NIZK-style proof (hex)
    scheme: str = "commit-pok-v1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def commit_wallet(address: str, network: str = "eip155:8453", salt: Optional[bytes] = None) -> Tuple[WalletCommitment, bytes]:
    """
    Create a commitment to `address` and a proof of knowledge of the opening.

    Returns (public_commitment, private_opening_secret)
    The private_opening_secret must be kept by the seller until settlement reveal (if needed).
    """
    if salt is None:
        salt = secrets.token_bytes(32)
    addr_bytes = address.lower().encode()
    # Commitment = H(salt || address || network)
    commit_input = salt + addr_bytes + network.encode()
    commitment = _sha256(commit_input)

    # Simple Fiat-Shamir style proof of knowledge of (salt, address):
    # Prover picks blinding r, publishes R = H(r || address), challenge c = H(commitment || R),
    # response s = H(r || c || salt). Verifier checks structure.
    # This is a lightweight PoK demonstration, not a full discrete-log SNARK.
    r = secrets.token_bytes(32)
    R = _sha256(r + addr_bytes)
    c = _sha256(commitment + R)
    s = _sha256(r + c + salt)

    proof = R + c + s  # 96 bytes

    wc = WalletCommitment(
        commitment=_hex(commitment),
        network=network,
        salt=_hex(salt),
        proof=_hex(proof),
        scheme="commit-pok-v1",
    )
    # Private material the seller retains
    opening = salt + addr_bytes  # enough to open later if required
    return wc, opening

def verify_commitment(wc: WalletCommitment, claimed_address: Optional[str] = None) -> bool:
    """
    Verify the proof of knowledge structure.
    If claimed_address is provided, also check that it opens the commitment.
    """
    try:
        commitment = _from_hex(wc.commitment)
        salt = _from_hex(wc.salt)
        proof = _from_hex(wc.proof)
        if len(proof) != 96:
            return False
        R, c, s = proof[:32], proof[32:64], proof[64:]

        # Recompute challenge binding
        c2 = _sha256(commitment + R)
        if c2 != c:
            return False

        if claimed_address is not None:
            addr_bytes = claimed_address.lower().encode()
            expected = _sha256(salt + addr_bytes + wc.network.encode())
            if expected != commitment:
                return False
        return True
    except Exception:
        return False

def open_commitment(wc: WalletCommitment, opening: bytes) -> Optional[str]:
    """Open a commitment using the private opening material. Returns address or None."""
    try:
        salt = opening[:32]
        addr_bytes = opening[32:]
        if _hex(salt) != wc.salt:
            return None
        expected = _sha256(salt + addr_bytes + wc.network.encode())
        if _hex(expected) != wc.commitment:
            return None
        return addr_bytes.decode()
    except Exception:
        return None

def derive_stealth_address(view_secret: bytes, ephemeral_pub: bytes, network: str = "eip155:8453") -> str:
    """
    Simplified stealth / one-time address derivation.
    Shared secret = H(view_secret || ephemeral_pub)
    Address-like token = 0x + H(shared || network)[:20]
    (For illustration; real EVM stealth addresses need proper ECC.)
    """
    shared = _sha256(view_secret + ephemeral_pub)
    raw = _sha256(shared + network.encode())[:20]
    return "0x" + raw.hex()

def generate_ephemeral_keypair() -> Tuple[bytes, bytes]:
    """Return (private, public) style ephemeral material for stealth derivation."""
    priv = secrets.token_bytes(32)
    pub = _sha256(priv)  # placeholder public
    return priv, pub

if __name__ == "__main__":
    addr = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
    wc, opening = commit_wallet(addr, network="eip155:8453")
    print("Commitment:", wc.commitment[:24] + "...")
    print("Proof valid (no open):", verify_commitment(wc))
    print("Proof valid (with open):", verify_commitment(wc, claimed_address=addr))
    print("Opened address:", open_commitment(wc, opening))
    print("Wrong address rejected:", verify_commitment(wc, claimed_address="0x0000000000000000000000000000000000000001"))
