"""Falsifiable commerce W0: bonded warranties, deterministic challenges (A27).

Constitution pointers live here:
`test_challenge_terminates_in_deterministic_reexecution`,
`test_unwarrantable_content_is_labeled_never_dressed_in_a_warranty`,
`test_undecidable_context_forfeits_nothing_either_way`.
Warranties are exercised against real pipeline output, per the wire-contract
convention.
"""

from __future__ import annotations

import pytest
from eth_account import Account

from veritas.notary.sign import OperatorSigner, verify_attestation
from veritas.pipeline import run_research
from veritas.retrieval import StaticCorpusRetriever
from veritas.warranty import (
    CLASS_D0,
    CLASS_U,
    OUTCOME_FIRED,
    OUTCOME_NOT_FIRED,
    OUTCOME_UNDECIDABLE,
    PREDICATES,
    WarrantyError,
    build_warranty,
    evaluate_challenge,
    falsifiability_class,
    unwarranted_label,
    verify_warranty,
    warranty_report,
)

pytest.importorskip("eth_account")

BOND = {"amount_atomic": "250000", "asset": "USDC", "network": "eip155:84532"}
ALL_D0 = list(PREDICATES)


def _signer():
    return OperatorSigner("0x" + bytes(Account.create().key).hex())


@pytest.fixture(scope="module")
def completed_response():
    r = run_research("What is the x402 protocol?", retriever=StaticCorpusRetriever())
    assert r["status"] == "completed"
    return r


@pytest.fixture
def warranted(completed_response):
    seller = _signer()
    warranty = build_warranty(
        completed_response,
        predicates=ALL_D0,
        bond=BOND,
        window_seconds=86400,
        signer=seller,
    )
    return seller, warranty, completed_response


# --- construction ------------------------------------------------------------


def test_warranty_over_real_pipeline_output_verifies(warranted):
    seller, warranty, response = warranted
    assert warranty["falsifiability_class"] == CLASS_D0
    assert warranty["bond_binding"] == "signed_commitment_not_escrow"
    ok, reason = verify_warranty(warranty, response)
    assert (ok, reason) == (True, "ok")
    assert warranty["seller"]["signer"] == seller.address.lower()


def test_unwarrantable_content_is_labeled_never_dressed_in_a_warranty(
    completed_response,
):
    """A27. Class-U content ships the honest label; a warranty with no
    predicates is refused rather than sold as decoration."""
    with pytest.raises(WarrantyError, match="unwarrantable"):
        build_warranty(
            completed_response,
            predicates=[],
            bond=BOND,
            window_seconds=3600,
            signer=_signer(),
        )
    label = unwarranted_label()
    assert label["falsifiability_class"] == CLASS_U
    assert label["warranted"] is False
    assert falsifiability_class([]) == CLASS_U


def test_seller_cannot_sell_a_warranty_already_lost(completed_response):
    """A predicate that already fires would convert challenge stakes into
    seller revenue; construction refuses."""
    broken = dict(completed_response)
    broken["claims"] = [
        {**completed_response["claims"][0], "evidence_hash": "sha256:" + "ff" * 32}
    ]
    with pytest.raises(WarrantyError, match="predicate_already_fires:citation_unbacked"):
        build_warranty(
            broken,
            predicates=["citation_unbacked.v1"],
            bond=BOND,
            window_seconds=3600,
            signer=_signer(),
        )


def test_malformed_bond_is_refused(completed_response):
    for bad in (
        {**BOND, "amount_atomic": "0"},
        {**BOND, "amount_atomic": "0.25"},
        {**BOND, "asset": ""},
    ):
        with pytest.raises(WarrantyError, match="bond_malformed"):
            build_warranty(
                completed_response,
                predicates=["status_incoherent.v1"],
                bond=bad,
                window_seconds=3600,
                signer=_signer(),
            )


# --- deterministic challenge -------------------------------------------------


def test_challenge_terminates_in_deterministic_reexecution(warranted):
    """A27. The dispute is a computation: identical inputs give identical
    outcomes to any party, with no arbiter in the loop — and an untampered
    deliverable does not fire."""
    _, warranty, response = warranted
    first = evaluate_challenge(warranty, response, challenged_at=warranty["issued_at"])
    second = evaluate_challenge(warranty, response, challenged_at=warranty["issued_at"])
    assert first == second  # bitwise-identical decision for any evaluator
    assert first["outcome"] == OUTCOME_NOT_FIRED
    assert all(not r["fired"] for r in first["predicate_results"])


def test_altered_bytes_are_undecidable_not_forfeit(warranted):
    """A challenger evaluating bytes other than the ones the warranty binds
    gets wrong-bytes, not a win: forfeits attach only to what was signed."""
    _, warranty, response = warranted
    tampered = dict(response)
    tampered["claims"] = [
        {**response["claims"][0], "evidence_hash": "sha256:" + "aa" * 32}
    ]
    wrong_bytes = evaluate_challenge(
        warranty, tampered, challenged_at=warranty["issued_at"]
    )
    assert wrong_bytes["outcome"] == OUTCOME_UNDECIDABLE
    assert "forfeit" not in wrong_bytes


def test_fired_outcome_on_seller_signed_defective_bytes():
    """End-to-end forfeit path: a seller that signs a warranty over bytes a
    predicate refutes loses deterministically."""
    seller = _signer()
    defective = {
        "status": "unavailable",
        "billable": True,  # invariant 3 violated on the delivered bytes
        "claims": [],
        "evidence": [],
        "custody_chain": [{"event_type": "x", "event_hash": "bad"}],
    }
    # build_warranty refuses, so a defective warranty must be hand-signed —
    # exactly what a dishonest seller would do off-path:
    from veritas.warranty import (
        WARRANTY_VERSION,
        canonical_response_hash,
        canonical_warranty_message,
    )

    warranty = {
        "warranty_version": WARRANTY_VERSION,
        "response_hash": canonical_response_hash(defective),
        "predicates": ["status_incoherent.v1"],
        "falsifiability_class": CLASS_D0,
        "bond": BOND,
        "bond_binding": "signed_commitment_not_escrow",
        "window_seconds": 3600,
        "issued_at": "2026-08-08T12:00:00Z",
    }
    message = canonical_warranty_message(warranty)
    warranty["seller"] = {
        "scheme": "eip191",
        "signer": seller.address.lower(),
        "signature": seller.sign_text(message),
        "message": message,
    }
    outcome = evaluate_challenge(
        warranty, defective, challenged_at="2026-08-08T12:30:00Z"
    )
    assert outcome["outcome"] == OUTCOME_FIRED
    assert outcome["forfeit"]["amount_atomic"] == BOND["amount_atomic"]
    assert outcome["forfeit"]["binding"] == "signed_commitment_not_escrow"
    reasons = {r["reason"] for r in outcome["predicate_results"] if r["fired"]}
    assert "billed_own_failure" in reasons


def test_undecidable_context_forfeits_nothing_either_way(warranted):
    """A27. Invalid warranty, wrong bytes, or a closed window is the
    layer's could-not-decide: kept apart from both verdicts, no forfeit."""
    _, warranty, response = warranted

    # closed window
    late = evaluate_challenge(warranty, response, challenged_at="2099-01-01T00:00:00Z")
    assert late["outcome"] == OUTCOME_UNDECIDABLE
    assert late["reason"] == "window_closed"
    assert "forfeit" not in late

    # wrong bytes
    other = dict(response)
    other["query"] = "a different deliverable"
    wrong = evaluate_challenge(warranty, other, challenged_at=warranty["issued_at"])
    assert wrong["outcome"] == OUTCOME_UNDECIDABLE
    assert wrong["reason"].startswith("response_mismatch")

    # tampered warranty signature
    forged = {**warranty, "window_seconds": 999999}
    bad = evaluate_challenge(forged, response, challenged_at=warranty["issued_at"])
    assert bad["outcome"] == OUTCOME_UNDECIDABLE
    assert bad["reason"].startswith("warranty_invalid")


def test_escrowed_warranty_forfeit_is_collectable(tmp_path):
    """G12. An escrowed warranty that fires is collectable via settle_forfeit.

    Construction refuses a deliverable that already fires, so a dishonest
    seller must hand-sign over defective bytes — the same path as
    test_fired_outcome_on_seller_signed_defective_bytes — and attach a
    real lock. Collection submits that lock; the commitment-only path
    stays unlabeled as collectable.
    """
    from veritas.escrow import (
        BOND_BINDING_ESCROW,
        EscrowStore,
        escrow_bond,
        settle_forfeit,
    )
    from veritas.facilitator import SimulatedFacilitatorClient
    from veritas.warranty import (
        WARRANTY_VERSION,
        canonical_response_hash,
        canonical_warranty_message,
    )

    seller = _signer()
    defective = {
        "status": "unavailable",
        "billable": True,
        "claims": [],
        "evidence": [],
        "custody_chain": [{"event_type": "x", "event_hash": "bad"}],
    }
    store = EscrowStore(tmp_path)
    lock = escrow_bond(
        {
            "from": "0x" + "11" * 20,
            "to": "0x" + "22" * 20,
            "value": BOND["amount_atomic"],
            "validAfter": "0",
            "validBefore": "9999999999",
            "nonce": "0x" + "aa" * 32,
            "signature": "0x" + "ee" * 65,
        },
        network=BOND["network"],
        warranty_hash=canonical_response_hash(defective),
        store=store,
    )
    warranty = {
        "warranty_version": WARRANTY_VERSION,
        "response_hash": canonical_response_hash(defective),
        "predicates": ["status_incoherent.v1"],
        "falsifiability_class": CLASS_D0,
        "bond": BOND,
        "bond_binding": BOND_BINDING_ESCROW,
        "escrow": {
            "lock_id": lock["lock_id"],
            "state": lock["state"],
            "pay_to": lock["pay_to"],
            "valid_before": lock["valid_before"],
            "method": lock["method"],
        },
        "window_seconds": 3600,
        "issued_at": "2026-08-08T12:00:00Z",
    }
    message = canonical_warranty_message(warranty)
    warranty["seller"] = {
        "scheme": "eip191",
        "signer": seller.address.lower(),
        "signature": seller.sign_text(message),
        "message": message,
    }
    outcome = evaluate_challenge(
        warranty, defective, challenged_at="2026-08-08T12:30:00Z"
    )
    assert outcome["outcome"] == OUTCOME_FIRED
    assert outcome["forfeit"]["binding"] == BOND_BINDING_ESCROW
    assert outcome["forfeit"]["lock_id"] == lock["lock_id"]
    collected = settle_forfeit(
        lock,
        outcome=outcome,
        facilitator=SimulatedFacilitatorClient(),
        store=store,
    )
    assert collected["settlement"]["success"] is True
    assert store.get(lock["lock_id"])["state"] == "forfeited"


def test_escrowed_build_warranty_locks_matching_amount(completed_response, tmp_path):
    from veritas.escrow import BOND_BINDING_ESCROW, EscrowStore, escrow_bond

    store = EscrowStore(tmp_path)
    warranty = build_warranty(
        completed_response,
        predicates=["status_incoherent.v1"],
        bond=BOND,
        window_seconds=3600,
        signer=_signer(),
        authorization={
            "from": "0x" + "11" * 20,
            "to": "0x" + "22" * 20,
            "value": BOND["amount_atomic"],
            "validAfter": "0",
            "validBefore": "9999999999",
            "nonce": "0x" + "bb" * 32,
            "signature": "0x" + "ff" * 65,
        },
        escrow_store=store,
    )
    assert warranty["bond_binding"] == BOND_BINDING_ESCROW
    assert warranty["escrow"]["state"] == "locked"
    mismatch_auth = {
        "from": "0x" + "11" * 20,
        "to": "0x" + "22" * 20,
        "value": "1",
        "validAfter": "0",
        "validBefore": "9999999999",
        "nonce": "0x" + "cc" * 32,
        "signature": "0x" + "ff" * 65,
    }
    with pytest.raises(WarrantyError, match="escrow_amount_mismatch"):
        build_warranty(
            completed_response,
            predicates=["status_incoherent.v1"],
            bond=BOND,
            window_seconds=3600,
            signer=_signer(),
            authorization=mismatch_auth,
            escrow_store=store,
        )
    # Amount is checked before lock — the nonce is still free.
    leftover = escrow_bond(mismatch_auth, network=BOND["network"], store=store)
    assert leftover["state"] == "locked"


def test_swapping_escrow_lock_after_sign_fails_verify(completed_response, tmp_path):
    """The lock id is in the signed message. Swapping it is a forfeit of
    someone else's bond and must not verify."""
    from veritas.escrow import EscrowStore

    warranty = build_warranty(
        completed_response,
        predicates=["status_incoherent.v1"],
        bond=BOND,
        window_seconds=3600,
        signer=_signer(),
        authorization={
            "from": "0x" + "11" * 20,
            "to": "0x" + "22" * 20,
            "value": BOND["amount_atomic"],
            "validAfter": "0",
            "validBefore": "9999999999",
            "nonce": "0x" + "dd" * 32,
            "signature": "0x" + "ff" * 65,
        },
        escrow_store=EscrowStore(tmp_path),
    )
    ok, _ = verify_warranty(warranty, completed_response)
    assert ok
    tampered = {
        **warranty,
        "escrow": {**warranty["escrow"], "lock_id": "ff" * 32},
    }
    ok, reason = verify_warranty(tampered, completed_response)
    assert ok is False
    assert reason in {"message_mismatch", "signer_mismatch", "signature_invalid"}


def test_warranty_signature_is_domain_separated(warranted):
    """A warranty signature must never verify as an evidence attestation."""
    _, warranty, _ = warranted
    masquerade = {
        "url": "https://example.org/x",
        "content_hash": warranty["response_hash"],
        "observed_at": warranty["issued_at"],
        "extract_version": "extract.v1",
        "request_id": "",
    }
    ok, _reason = verify_attestation(masquerade, warranty["seller"])
    assert not ok


# --- report ------------------------------------------------------------------


def test_warranty_report_counts(warranted):
    _, warranty, response = warranted
    ok = evaluate_challenge(warranty, response, challenged_at=warranty["issued_at"])
    late = evaluate_challenge(warranty, response, challenged_at="2099-01-01T00:00:00Z")
    report = warranty_report([ok, ok, late, {"outcome": "??"}])
    assert report["n_outcomes"] == 4
    assert report["not_fired"] == 2
    assert report["undecidable_reported"] == 1
    assert report["malformed_excluded"] == 1
    assert report["fired"] == 0


def test_research_does_not_auto_attach_a_warranty(completed_response):
    """G12 is a primitive. Research is not a warranted product path."""
    assert "warranty" not in completed_response
    assert "bond_binding" not in completed_response
    assert "forfeit" not in completed_response
    assert completed_response.get("claims")

