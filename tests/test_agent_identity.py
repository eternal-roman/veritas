"""L1: plane network visa identity."""

from __future__ import annotations

import pytest

from veritas.agent_identity import (
    PlaneIdentityIssuer,
    VisaVerifyError,
    bootstrap_plane_roster,
)


def test_issue_and_verify():
    issuer = PlaneIdentityIssuer(secret=b"test-secret-plane")
    visa = issuer.issue("overseer", "overseer", ttl_seconds=3600)
    got = issuer.verify(visa, expected_role="overseer")
    assert got.agent_id == "overseer"
    assert got.role == "overseer"


def test_bad_signature():
    issuer = PlaneIdentityIssuer(secret=b"test-secret-plane")
    visa = issuer.issue("scout", "scout")
    bad = visa.to_dict()
    bad["signature"] = "AAAA"
    with pytest.raises(VisaVerifyError):
        issuer.verify(bad)


def test_expired():
    issuer = PlaneIdentityIssuer(secret=b"test-secret-plane")
    visa = issuer.issue("steward", "steward", ttl_seconds=1, now=1000.0)
    with pytest.raises(VisaVerifyError):
        issuer.verify(visa, now=2000.0)


def test_bootstrap_roster():
    roster = bootstrap_plane_roster(
        {
            "overseer": "overseer",
            "money_loop": "money_loop",
            "multiparty_trust": "multiparty_trust",
        },
        secret=b"roster-secret",
    )
    assert set(roster) == {"overseer", "money_loop", "multiparty_trust"}
    issuer = PlaneIdentityIssuer(secret=b"roster-secret")
    for vid, doc in roster.items():
        issuer.verify(doc)
