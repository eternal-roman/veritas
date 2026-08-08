"""EIP-191 attestation of an EvidenceRecord (N1.1).

A completed observation can carry an operator signature over a **canonical
message** built from the buyer-visible binding fields (url, content_hash,
observed_at, extract_version, request_id). The scheme is EIP-191
``personal_sign`` (``eth_account.messages.encode_defunct``) with the same
secp256k1 key family used for payment wallets — not a second crypto stack.

Honesty boundaries:

* Signing is **optional**. Free mode without a configured key omits
  ``attestation`` rather than inventing one.
* The private key is never returned, logged, or written into the record.
* A valid signature means the operator key attested those bound fields. It
  does **not** mean the origin served that body to any other party, that a
  settlement occurred on-chain, or that a Merkle/anchor log exists (N1.2+).
* Standalone ``veritas.verifier`` stays zero-dependency; EIP-191 recovery
  lives here (optional ``eth_account``), not in the vendored verifier.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_KEY_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")

SCHEME = "eip191"
MESSAGE_VERSION = "veritas-evidence-record-v1"
ENV_SIGNING_KEY = "VERITAS_SIGNING_KEY"
ENV_AGENT_DIR = "VERITAS_AGENT_DIR"

ATTEST_NOTE = (
    "operator EIP-191 personal_sign over the bound fields; "
    "not an on-chain anchor and not proof the origin served this to others"
)


class NotarySignError(ValueError):
    """Signing or verification could not proceed."""


@dataclass(frozen=True)
class OperatorSigner:
    """In-process secp256k1 signer for notary attestations. DEV/operator only.

    Same thin shape as the buyer ``LocalAccountSigner``: one process-held key,
    never serialised. Production may later swap a remote signer without
    changing the message format.
    """

    _private_key: str

    def __post_init__(self) -> None:
        key = self._private_key
        if not _KEY_RE.match(key or ""):
            raise NotarySignError(
                "signing key must be 0x-prefixed 32-byte hex (secp256k1)"
            )
        try:
            from eth_account import Account
        except ImportError as exc:  # pragma: no cover - dependency-gated
            raise NotarySignError(
                "eth_account is required for notary signing; "
                "pip install 'veritas-research[signing]'"
            ) from exc
        # Validate key material once at construction.
        object.__setattr__(self, "_account", Account.from_key(key))

    @property
    def address(self) -> str:
        return str(self._account.address)

    def sign_text(self, message: str) -> str:
        from eth_account.messages import encode_defunct

        signable = encode_defunct(text=message)
        signature = self._account.sign_message(signable).signature
        return "0x" + signature.hex().removeprefix("0x")


def _normalize_address(address: str) -> str:
    if not _ADDRESS_RE.match(address or ""):
        raise NotarySignError("address must be 0x-prefixed 20-byte hex")
    return address.lower()


def canonical_attestation_message(record: Mapping[str, Any]) -> str:
    """Build the EIP-191 text message for a record (or record-shaped dict).

    Only fields a buyer can re-check without trusting the operator's body
    truncation are bound. Policy and media metadata are deliberately out of
    scope for N1.1 so the signature stays stable across wire enrichments.
    """
    try:
        url = record["url"]
        content_hash = record["content_hash"]
        observed_at = record["observed_at"]
        extract_version = record["extract_version"]
    except KeyError as exc:
        raise NotarySignError(f"record missing field for attestation: {exc}") from exc
    request_id = record.get("request_id") or ""
    return "\n".join(
        (
            MESSAGE_VERSION,
            f"url: {url}",
            f"content_hash: {content_hash}",
            f"observed_at: {observed_at}",
            f"extract_version: {extract_version}",
            f"request_id: {request_id}",
        )
    )


def recover_attestation_signer(message: str, signature: str) -> str:
    """Recover the operator address from an EIP-191 personal_sign signature."""
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError as exc:  # pragma: no cover - dependency-gated
        raise NotarySignError(
            "eth_account is required to verify notary attestations; "
            "pip install 'veritas-research[signing]'"
        ) from exc
    if not isinstance(signature, str) or not signature.startswith("0x"):
        raise NotarySignError("signature must be 0x-prefixed hex")
    try:
        signable = encode_defunct(text=message)
        recovered = Account.recover_message(signable, signature=signature)
    except Exception as exc:  # eth_account raises varied types
        raise NotarySignError(f"signature recovery failed: {type(exc).__name__}") from exc
    return _normalize_address(recovered)


def sign_evidence_record(
    record: Mapping[str, Any],
    signer: OperatorSigner,
) -> dict[str, Any]:
    """Return a wire-safe attestation object (no private key material)."""
    message = canonical_attestation_message(record)
    signature = signer.sign_text(message)
    return {
        "scheme": SCHEME,
        "signer": signer.address,
        "signature": signature,
        "message": message,
        "attests": ATTEST_NOTE,
    }


def verify_attestation(
    record: Mapping[str, Any],
    attestation: Mapping[str, Any],
    *,
    expected_signer: str | None = None,
) -> tuple[bool, str]:
    """Check an attestation against a record. Returns ``(ok, reason)``."""
    if not attestation:
        return False, "attestation_missing"
    if attestation.get("scheme") != SCHEME:
        return False, "scheme_mismatch"
    signature = attestation.get("signature")
    if not isinstance(signature, str):
        return False, "signature_missing"
    # Prefer reconstructing the message so a tampered `message` field cannot
    # pass when the record fields no longer match.
    try:
        message = canonical_attestation_message(record)
    except NotarySignError as exc:
        return False, str(exc)
    published = attestation.get("message")
    if published is not None and published != message:
        return False, "message_mismatch"
    try:
        recovered = recover_attestation_signer(message, signature)
    except NotarySignError as exc:
        return False, str(exc)
    claimed = attestation.get("signer")
    if isinstance(claimed, str) and claimed.lower() != recovered:
        return False, "signer_mismatch"
    if expected_signer is not None:
        try:
            want = _normalize_address(expected_signer)
        except NotarySignError:
            return False, "expected_signer_malformed"
        if recovered != want:
            return False, "unexpected_signer"
    return True, "ok"


def operator_signer_from_env() -> OperatorSigner | None:
    """Resolve an operator signer, or None when signing is not configured.

    Order:

    1. ``VERITAS_SIGNING_KEY`` — 0x-prefixed 32-byte hex (tests and ops).
    2. Agent wallet under ``VERITAS_AGENT_DIR`` (default ``.veritas_agent``) —
       the same secp256k1 material provisioned for payment receive.

    Missing eth_account or wallet → None (omit attestation; do not invent).
    Invalid key material → raises ``NotarySignError`` so misconfig is loud.
    """
    raw = (os.getenv(ENV_SIGNING_KEY) or "").strip()
    if raw:
        if not raw.startswith("0x"):
            raw = "0x" + raw
        return OperatorSigner(raw)

    base_dir = (os.getenv(ENV_AGENT_DIR) or "").strip() or ".veritas_agent"
    try:
        from veritas.autonomous.wallet import load_signer
    except Exception:  # pragma: no cover - import graph
        return None
    try:
        buyer_signer = load_signer(base_dir)
    except Exception:
        return None
    # LocalAccountSigner holds the key privately; re-open via env is preferred.
    # load_signer returns a LocalAccountSigner — extract address-compatible key
    # only if the adapter exposes the underlying account (dev path).
    account = getattr(buyer_signer, "_account", None)
    if account is None:
        return None
    key = "0x" + bytes(account.key).hex()
    return OperatorSigner(key)


def maybe_attest_record(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Sign ``record`` when a signer is configured; else return None.

    Sign failures after a key was resolved are re-raised only for malformed
    keys at construction. Runtime sign errors return None so a completed
    observation is not discarded for attestation trouble (the product is the
    observation; signature is additive for N1.1).
    """
    try:
        signer = operator_signer_from_env()
    except NotarySignError:
        raise
    if signer is None:
        return None
    try:
        return sign_evidence_record(record, signer)
    except NotarySignError:
        return None


__all__ = [
    "ATTEST_NOTE",
    "ENV_AGENT_DIR",
    "ENV_SIGNING_KEY",
    "MESSAGE_VERSION",
    "SCHEME",
    "NotarySignError",
    "OperatorSigner",
    "canonical_attestation_message",
    "maybe_attest_record",
    "operator_signer_from_env",
    "recover_attestation_signer",
    "sign_evidence_record",
    "verify_attestation",
]
