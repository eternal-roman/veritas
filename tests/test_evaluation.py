"""Tests for the evaluation harness."""

from evaluations.harness import (
    evaluate_fidelity,
    evaluate_refusal,
    evaluate_unavailability_honesty,
    run_full_harness,
)


def test_fidelity_all_claims_hash_match():
    report = evaluate_fidelity()
    assert report["total_claims"] > 0
    assert report["citation_fidelity"] == 1.0
    assert report["all_custody_valid"] is True


def test_refusal_discriminates():
    """Refusal rate alone is gameable — a service that refuses everything
    scores perfectly. Measure the gap between supported and unsupported."""
    report = evaluate_refusal()
    assert report["correct_refusal_rate"] > 0.5
    assert report["correct_answer_rate"] > 0.5
    assert report["discrimination"] > 0.0


def test_unavailability_is_never_reported_as_no_evidence():
    report = evaluate_unavailability_honesty()
    assert report["correct"] is True
    assert report["status"] == "unavailable"
    assert report["billable"] is False


def test_full_harness_shape():
    report = run_full_harness()
    assert set(report) == {"fidelity", "refusal", "unavailability_honesty"}
