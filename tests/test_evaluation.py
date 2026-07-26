"""Tests for the evaluation harness."""

from evaluations.harness import evaluate_single, run_fidelity_suite, run_refusal_suite

def test_evaluate_single_smoke():
    r = evaluate_single("What is a hash chain?")
    assert "status" in r
    assert "custody_valid" in r
    assert r["custody_valid"] is True

def test_fidelity_suite():
    report = run_fidelity_suite()
    assert report["n"] > 0
    assert report["all_custody_valid"] is True

def test_refusal_suite():
    report = run_refusal_suite()
    assert report["n"] > 0
    # We do not assert a specific refusal rate yet because retrieval is still conservative;
    # we only assert the suite runs and returns structured data.
    assert "refusal_rate" in report
