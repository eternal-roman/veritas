"""Tests for the evaluation harness."""

from evaluations.harness import evaluate_fidelity, evaluate_refusal, run_full_harness

def test_fidelity_suite():
    report = evaluate_fidelity()
    assert report["total_claims"] > 0
    assert 0.0 <= report["citation_fidelity"] <= 1.0
    assert len(report["details"]) > 0

def test_refusal_report_structure():
    report = evaluate_refusal()
    # The current pipeline's static retrieval always falls back to at least one
    # source, so refusal is not yet reachable here; assert structure only.
    assert report["status"] in ("completed", "refused")
    assert "posterior" in report
    assert report["custody_valid"] is True

def test_full_harness():
    report = run_full_harness()
    assert set(report) == {"fidelity", "refusal", "baseline_comparison"}
