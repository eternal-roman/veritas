"""Identity-bound self-signed TLS material for a self-hosted peer.

Each agent can host HTTPS with a **self-signed** certificate. The TLS
private key is generated here and is never the commerce/secp256k1 key.
When a ``did:pkh:{network}:{address}`` is known it is written as a SAN
URI. A peer card may then advertise:

    "tls": {
        "fingerprint": "sha256:<hex of DER cert>",
        "binding": "<eip191 signature over the fingerprint string>"
    }

``binding`` is optional. It is an EIP-191 ``personal_sign`` over the
fingerprint string, produced by the commerce identity — so a verifier
can recover the signer and check it against the expected address.

Honesty bound:
- Self-signed. Not a public CA and not a hostname attestation.
- Fingerprint pin of the presented DER, plus optional wallet binding.
- Issuing a cert requires ``cryptography`` (pulled in by the signing
  extra). Stdlib cannot write a SAN URI; the issue path fails closed
  rather than emit a weaker PEM.
- This module does not serve, connect, or publish a network. It is not
  the Mesh Runner.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

CERT_FILENAME = "tls-cert.pem"
KEY_FILENAME = "tls-key.pem"
META_FILENAME = "tls.json"

_PEM_CERT_BEGIN = b"-----BEGIN CERTIFICATE-----"
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_VALIDITY_DAYS = 365
_RSA_KEY_SIZE = 2048


class TlsMaterialError(ValueError):
    """TLS material could not be issued, loaded, or parsed."""


def _as_path(directory: Path | str) -> Path:
    return Path(directory).expanduser()


def _certificate_der(cert_der_or_pem: bytes | str) -> bytes:
    if isinstance(cert_der_or_pem, str):
        raw = cert_der_or_pem.encode("ascii")
    else:
        raw = bytes(cert_der_or_pem)
    if not raw:
        raise TlsMaterialError("certificate is empty")
    if _PEM_CERT_BEGIN in raw:
        return _pem_block_der(raw)
    return raw


def _pem_block_der(raw: bytes) -> bytes:
    begin = b"-----BEGIN CERTIFICATE-----"
    end = b"-----END CERTIFICATE-----"
    start = raw.find(begin)
    stop = raw.find(end)
    if start < 0 or stop < 0 or stop <= start:
        raise TlsMaterialError("PEM CERTIFICATE block not found")
    body = raw[start + len(begin) : stop]
    try:
        return base64.b64decode(body)
    except Exception as exc:  # binascii.Error, ValueError
        raise TlsMaterialError("PEM body is not valid base64") from exc


def cert_fingerprint(cert_der_or_pem: bytes | str) -> str:
    """Return ``sha256:<hex>`` of the certificate DER.

    Accepts DER or PEM. PEM is unwrapped with the standard library; no
    X.509 writer is involved.
    """
    der = _certificate_der(cert_der_or_pem)
    return "sha256:" + hashlib.sha256(der).hexdigest()


def _normalize_address(address: str) -> str:
    if not _ADDRESS_RE.match(address or ""):
        raise TlsMaterialError("address must be 0x-prefixed 20-byte hex")
    return address.lower()


def _require_cryptography() -> Any:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    except ImportError as exc:
        raise TlsMaterialError(
            "cryptography is required to issue TLS certificates "
            "(SAN URI cannot be written with the standard library); "
            "pip install 'veritas-research[signing]'"
        ) from exc
    return x509, hashes, serialization, rsa, NameOID, ExtendedKeyUsageOID


def _write_owner_only(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)


def bind_fingerprint(fingerprint: str, sign_text: Callable[[str], str]) -> str:
    """EIP-191 signature over the fingerprint string (commerce identity)."""
    if not _FINGERPRINT_RE.match(fingerprint or ""):
        raise TlsMaterialError("fingerprint must be sha256:<64 lowercase hex>")
    signature = sign_text(fingerprint)
    if not isinstance(signature, str) or not signature.startswith("0x"):
        raise TlsMaterialError("sign_text must return a 0x-prefixed EIP-191 signature")
    return signature


def issue_tls_material(
    directory: Path | str,
    *,
    did_pkh: str | None = None,
    identity_hash: str | None = None,
    sign_text: Callable[[str], str] | None = None,
) -> dict[str, str]:
    """Create a self-signed cert + TLS key under ``directory``.

    The TLS key is a fresh RSA key. It is never the commerce key. SAN URI
    is set to ``did_pkh`` when known. ``identity_hash`` is stored alongside
    the material for the card; it is not a second key.
    """
    x509, hashes, serialization, rsa, NameOID, ExtendedKeyUsageOID = (
        _require_cryptography()
    )
    from datetime import datetime, timedelta, timezone

    dest = _as_path(directory)
    dest.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=_RSA_KEY_SIZE)
    common_name = "veritas-peer"
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=_VALIDITY_DAYS))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
    )
    did = (did_pkh or "").strip() or None
    if did:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.UniformResourceIdentifier(did)]),
            critical=False,
        )
    cert = builder.sign(key, hashes.SHA256())

    cert_path = dest / CERT_FILENAME
    key_path = dest / KEY_FILENAME
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    _write_owner_only(
        key_path,
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )

    fingerprint = cert_fingerprint(cert.public_bytes(serialization.Encoding.DER))
    material: dict[str, str] = {
        "cert_path": str(cert_path),
        "key_path": str(key_path),
        "fingerprint": fingerprint,
    }
    meta: dict[str, str] = {"fingerprint": fingerprint}
    digest = (identity_hash or "").strip()
    if digest:
        meta["identity_hash"] = digest
    if did:
        meta["did_pkh"] = did
    if sign_text is not None:
        material["binding"] = bind_fingerprint(fingerprint, sign_text)
        meta["binding"] = material["binding"]
    (dest / META_FILENAME).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return material


def _read_meta(directory: Path) -> dict[str, Any]:
    path = directory / META_FILENAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_tls_files(directory: Path | str) -> dict[str, str]:
    """Load issued cert/key paths for serve. Fingerprint is from the cert."""
    dest = _as_path(directory)
    cert_path = dest / CERT_FILENAME
    key_path = dest / KEY_FILENAME
    if not cert_path.is_file() or not key_path.is_file():
        raise TlsMaterialError(f"TLS material missing under {dest}")
    fingerprint = cert_fingerprint(cert_path.read_bytes())
    loaded: dict[str, str] = {
        "cert_path": str(cert_path),
        "key_path": str(key_path),
        "fingerprint": fingerprint,
    }
    meta = _read_meta(dest)
    binding = meta.get("binding")
    stored_fp = meta.get("fingerprint")
    if isinstance(binding, str) and binding and stored_fp == fingerprint:
        loaded["binding"] = binding
    return loaded


def tls_block_for_card(directory: Path | str) -> dict[str, str] | None:
    """Peer-card ``tls`` object, or None when this node has no TLS files.

    ``peer.py`` can call this later. This module does not write the card.
    """
    try:
        loaded = load_tls_files(directory)
    except TlsMaterialError:
        return None
    block = {"fingerprint": loaded["fingerprint"]}
    if "binding" in loaded:
        block["binding"] = loaded["binding"]
    return block


def _recover_binding_signer(fingerprint: str, binding: str) -> str:
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError as exc:
        raise TlsMaterialError(
            "eth_account is required to verify a TLS binding; "
            "pip install 'veritas-research[signing]'"
        ) from exc
    if not isinstance(binding, str) or not binding.startswith("0x"):
        raise TlsMaterialError("binding must be a 0x-prefixed EIP-191 signature")
    try:
        recovered = Account.recover_message(
            encode_defunct(text=fingerprint), signature=binding
        )
    except Exception as exc:  # eth_account raises varied types
        raise TlsMaterialError(f"binding recovery failed: {type(exc).__name__}") from exc
    return str(recovered).lower()


def verify_tls_binding(
    cert_der: bytes | str,
    fingerprint: str,
    binding: str,
    expected_address: str,
) -> tuple[bool, str]:
    """Recover the binder and check it plus the cert fingerprint."""
    try:
        computed = cert_fingerprint(cert_der)
    except TlsMaterialError as exc:
        return False, str(exc)
    if not _FINGERPRINT_RE.match(fingerprint or ""):
        return False, "malformed fingerprint"
    if computed != fingerprint:
        return False, "fingerprint does not match certificate"
    try:
        expect = _normalize_address(expected_address)
        recovered = _recover_binding_signer(fingerprint, binding)
    except TlsMaterialError as exc:
        return False, str(exc)
    if recovered != expect:
        return False, f"signer {recovered} != {expect}"
    return True, "ok"


def verify_presented_cert(
    cert_der: bytes | str,
    *,
    fingerprint: str,
    binding: str | None = None,
    expected_address: str | None = None,
) -> tuple[bool, str]:
    """Accept a presented cert against a card fingerprint and optional binding."""
    try:
        computed = cert_fingerprint(cert_der)
    except TlsMaterialError as exc:
        return False, str(exc)
    if not _FINGERPRINT_RE.match(fingerprint or ""):
        return False, "malformed fingerprint"
    if computed != fingerprint:
        return False, "fingerprint does not match certificate"
    if binding is None and expected_address is None:
        return True, "ok"
    if expected_address and not binding:
        return False, "binding missing"
    if binding and not expected_address:
        try:
            _recover_binding_signer(fingerprint, binding)
        except TlsMaterialError as exc:
            return False, str(exc)
        return True, "ok"
    return verify_tls_binding(cert_der, fingerprint, binding, expected_address)
