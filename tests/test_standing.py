"""Composed standing: the evidence hierarchy as one recomputable document."""

from __future__ import annotations

import pytest
from eth_account import Account

from veritas.audit import perform_audit
from veritas.hashing import compute_content_hash
from veritas.notary.fetch import FetchResult
from veritas.notary.pack import build_evidence_pack
from veritas.notary.sign import OperatorSigner, sign_evidence_record
from veritas.standing import (
    EVIDENCE_HIERARCHY,
    VERDICT_CONTESTED,
    VERDICT_FORFEITED,
    VERDICT_SURVIVING_CHALLENGED,
    standing_report,
)

pytest.importorskip("eth_account")

ROBOTS_OK = "User-agent: *\nAllow: /\n"
BODY = "Standing composition body."


def _signer():
    return OperatorSigner("0x" + bytes(Account.create().key).hex())


def _fetch(body: bytes):
    def fake(request_url, **kwargs):
        return FetchResult(
            request_url=request_url, final_url=request_url, status=200,
            headers={"content-type": "text/plain"}, body=body, truncated=False,
        )
    return fake


def _confirmed_audit(seller):
    fields = {
        "url": "https://example.org/standing",
        "content_hash": compute_content_hash(BODY),
        "observed_at": "2026-08-08T12:00:00Z",
        "extract_version": "extract.v1",
        "request_id": "req-standing",
    }
    pack = build_evidence_pack(
        **fields, attestation=sign_evidence_record(fields, seller)
    )
    return perform_audit(
        pack, signer=_signer(), robots_body=ROBOTS_OK,
        fetch_fn=_fetch(BODY.encode("utf-8")),
    )


def _outcome(kind: str, wid: str):
    return {"outcome": kind, "warranty_hash": wid, "method": "veritas.warranty.v1"}


def test_hierarchy_is_declared_strongest_first():
    report = standing_report()
    assert report["hierarchy"] == list(EVIDENCE_HIERARCHY)
    assert report["hierarchy"][0] == "forfeited_bond"
    assert report["hierarchy"][-1] == "self_reported"
    assert report["verdict"] == "unaudited"


def test_forfeit_dominates_everything():
    seller = _signer()
    report = standing_report(
        audit_records=[_confirmed_audit(seller)],
        challenge_outcomes=[
            _outcome("not_fired", "sha256:" + "aa" * 32),
            _outcome("fired", "sha256:" + "bb" * 32),
        ],
        self_reported={"recommendation": "RECOMMENDED"},
    )
    assert report["verdict"] == VERDICT_FORFEITED
    assert report["forfeited_bonds"] == 1
    assert report["forfeit_binding"] == "signed_commitment_not_escrow"


def test_one_warranty_counts_once_and_fired_beats_survived():
    wid = "sha256:" + "cc" * 32
    report = standing_report(
        challenge_outcomes=[
            _outcome("not_fired", wid),
            _outcome("not_fired", wid),
            _outcome("fired", wid),
        ],
    )
    assert report["forfeited_bonds"] == 1
    assert report["survived_challenges"] == 0
    assert report["verdict"] == VERDICT_FORFEITED


def test_survived_challenge_upgrades_surviving():
    seller = _signer()
    audits = [_confirmed_audit(seller)]
    report = standing_report(
        audit_records=audits,
        audit_publication=audits,
        challenge_outcomes=[_outcome("not_fired", "sha256:" + "dd" * 32)],
    )
    assert report["audits"]["verdict"] == "surviving"
    assert report["verdict"] == VERDICT_SURVIVING_CHALLENGED


def test_audit_divergence_still_contests_without_forfeit():
    seller = _signer()
    fields = {
        "url": "https://example.org/standing2",
        "content_hash": compute_content_hash(BODY),
        "observed_at": "2026-08-08T12:00:00Z",
        "extract_version": "extract.v1",
        "request_id": "req-standing-2",
    }
    pack = build_evidence_pack(
        **fields, attestation=sign_evidence_record(fields, seller)
    )
    diverged = perform_audit(
        pack, signer=_signer(), robots_body=ROBOTS_OK,
        fetch_fn=_fetch(b"changed body"),
    )
    report = standing_report(
        audit_records=[diverged],
        challenge_outcomes=[_outcome("not_fired", "sha256:" + "ee" * 32)],
    )
    assert report["verdict"] == VERDICT_CONTESTED


def test_undecidable_and_malformed_are_reported_never_scored():
    report = standing_report(
        challenge_outcomes=[
            _outcome("undecidable", "sha256:" + "ff" * 32),
            {"outcome": "fired"},  # no warranty_hash — malformed
        ],
    )
    assert report["undecidable_challenges_reported"] == 1
    assert report["challenge_records_excluded"] == 1
    assert report["forfeited_bonds"] == 0
    assert report["verdict"] == "unaudited"


def test_self_report_is_labeled_floor_never_verdict():
    report = standing_report(self_reported={"recommendation": "RECOMMENDED"})
    assert report["self_reported"]["included"] is True
    assert report["self_reported"]["recommendation"] == "RECOMMENDED"
    assert "operator" in report["self_reported"]["role"]
    # A glowing self-report moves nothing:
    assert report["verdict"] == "unaudited"
