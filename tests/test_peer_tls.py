"""Identity-bound self-signed TLS material. Not a public CA, not a mesh."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veritas.peer_tls import (
    TlsMaterialError,
    cert_fingerprint,
    issue_tls_material,
    load_tls_files,
    tls_block_for_card,
    verify_presented_cert,
    verify_tls_binding,
)

pytest.importorskip("cryptography")


def _sign_with(account):
    from eth_account.messages import encode_defunct

    def sign_text(message: str) -> str:
        signature = account.sign_message(encode_defunct(text=message)).signature
        return "0x" + signature.hex().removeprefix("0x")

    return sign_text


def _der(path: str | Path) -> bytes:
    from cryptography.hazmat.primitives.serialization import Encoding
    from cryptography.x509 import load_pem_x509_certificate

    return load_pem_x509_certificate(Path(path).read_bytes()).public_bytes(Encoding.DER)


def test_issue_fingerprint_is_stable(tmp_path):
    material = issue_tls_material(tmp_path)
    pem = Path(material["cert_path"]).read_bytes()
    der = _der(material["cert_path"])
    assert material["fingerprint"] == cert_fingerprint(pem)
    assert cert_fingerprint(pem) == cert_fingerprint(der)
    assert material["fingerprint"] == cert_fingerprint(der)
    assert material["fingerprint"].startswith("sha256:")
    hex_part = material["fingerprint"].removeprefix("sha256:")
    assert len(hex_part) == 64
    assert hex_part == hex_part.lower()
    loaded = load_tls_files(tmp_path)
    assert loaded["fingerprint"] == material["fingerprint"]


def test_verify_accepts_matching_cert_and_fingerprint(tmp_path):
    material = issue_tls_material(tmp_path)
    ok, reason = verify_presented_cert(
        _der(material["cert_path"]),
        fingerprint=material["fingerprint"],
    )
    assert ok is True, reason


def test_verify_rejects_wrong_fingerprint(tmp_path):
    material = issue_tls_material(tmp_path)
    ok, reason = verify_presented_cert(
        _der(material["cert_path"]),
        fingerprint="sha256:" + ("00" * 32),
    )
    assert ok is False
    assert "fingerprint" in reason


def test_verify_rejects_binding_that_does_not_recover_expected_address(tmp_path):
    eth_account = pytest.importorskip("eth_account")
    alice = eth_account.Account.create()
    mallory = eth_account.Account.create()
    did = f"did:pkh:eip155:84532:{alice.address.lower()}"
    material = issue_tls_material(
        tmp_path,
        did_pkh=did,
        sign_text=_sign_with(alice),
    )
    cert_der = _der(material["cert_path"])
    ok, reason = verify_presented_cert(
        cert_der,
        fingerprint=material["fingerprint"],
        binding=material["binding"],
        expected_address=alice.address,
    )
    assert ok is True, reason
    ok, reason = verify_tls_binding(
        cert_der,
        material["fingerprint"],
        material["binding"],
        mallory.address,
    )
    assert ok is False
    assert mallory.address.lower() in reason or "signer" in reason
    ok, reason = verify_presented_cert(
        cert_der,
        fingerprint=material["fingerprint"],
        binding=material["binding"],
        expected_address=mallory.address,
    )
    assert ok is False


def test_commerce_key_is_not_written_as_the_tls_key(tmp_path):
    eth_account = pytest.importorskip("eth_account")
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    from veritas.autonomous.wallet import ensure_wallet

    info = ensure_wallet(tmp_path, kdf="pbkdf2", iterations=100)
    keystore_path = tmp_path / "wallet.keystore.json"
    passphrase = (tmp_path / "wallet.passphrase").read_text(encoding="utf-8")
    keystore_before = keystore_path.read_text(encoding="utf-8")
    material = issue_tls_material(
        tmp_path,
        did_pkh=f"did:pkh:eip155:84532:{info.address.lower()}",
    )
    assert Path(material["key_path"]).resolve() != keystore_path.resolve()
    assert Path(material["key_path"]).name != "wallet.keystore.json"
    assert keystore_path.read_text(encoding="utf-8") == keystore_before
    tls_key = load_pem_private_key(Path(material["key_path"]).read_bytes(), password=None)
    assert isinstance(tls_key, RSAPrivateKey)
    commerce_key = bytes(eth_account.Account.decrypt(json.loads(keystore_before), passphrase))
    assert commerce_key not in Path(material["key_path"]).read_bytes()


def test_issue_fails_closed_without_cryptography(tmp_path, monkeypatch):
    def missing():
        raise TlsMaterialError(
            "cryptography is required to issue TLS certificates "
            "(SAN URI cannot be written with the standard library); "
            "pip install 'veritas-research[signing]'"
        )

    monkeypatch.setattr("veritas.peer_tls._require_cryptography", missing)
    with pytest.raises(TlsMaterialError, match="SAN URI"):
        issue_tls_material(tmp_path)


def test_issued_san_uri_is_did_pkh(tmp_path):
    from cryptography import x509

    did = "did:pkh:eip155:84532:0x" + ("ab" * 20)
    material = issue_tls_material(tmp_path, did_pkh=did)
    cert = x509.load_pem_x509_certificate(Path(material["cert_path"]).read_bytes())
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert did in san.get_values_for_type(x509.UniformResourceIdentifier)
    block = tls_block_for_card(tmp_path)
    assert block is not None
    assert block["fingerprint"] == material["fingerprint"]
    assert "binding" not in block
