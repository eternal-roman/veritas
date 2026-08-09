"""L1: product-worth baseline is measurable and honest about limits."""

from __future__ import annotations

from veritas.evaluations.product_worth import (
    measure_payload,
    run_product_worth_baseline,
)


def test_payload_metrics_offline():
    p = measure_payload()
    assert p["n_queries"] >= 1
    assert p["corpus"] == "offline_static"
    assert p["not_commercial_grade"] is True
    assert 0.0 <= p["completed_rate"] <= 1.0
    assert p["median_excerpt_chars"] >= 0


def test_baseline_does_not_claim_commercial_win():
    report = run_product_worth_baseline()
    assert report["schema"] == "veritas.product_worth.v0"
    assert report["commercial_grade"] is False
    assert report["compared_to_search_api"] is False
    assert "fidelity" in report
    assert "refusal" in report
    assert "payload" in report
    # Offline corpus is structurally honest (same bar as harness gates).
    assert report["structural_ok"] is True
    assert report["unavailability_honesty"]["correct"] is True
