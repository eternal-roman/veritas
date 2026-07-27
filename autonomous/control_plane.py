"""Unified agent-native control plane.

Single entry point requiring zero human configuration.

This module used to contain a *second*, independent implementation of the
research pipeline — its own retrieval, custody, Bayesian updating and refusal
logic — while the HTTP surface ran a different one. The two drifted: the API
served a static three-document corpus while the real retrieval lived here and
was never reachable over the network. There is now one engine
(`veritas.pipeline`); this module adds only the agent-native concerns:
zero-config bootstrap, local settlement recording, and calibration feedback.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from autonomous.bootstrap import bootstrap, load_config
from autonomous.local_facilitator import record_attempt, record_settlement, verify_payment
from autonomous.self_calibrator import SelfCalibrator
from veritas.pipeline import run_research
from veritas.trust import OutcomeLog


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def agent_start() -> Dict[str, Any]:
    """Provision a free-mode config with no human input."""
    return bootstrap()


def agent_research(
    query: str,
    headers: Optional[Dict[str, str]] = None,
    max_results: int = 4,
) -> Dict[str, Any]:
    """Run research through the shared engine under agent-native settlement."""
    headers = headers or {}
    cfg = load_config()
    require = bool(cfg.get("require_payment", False))

    result = run_research(query, max_results=max_results)
    request_id = result["request_id"]
    record_attempt(request_id, headers)

    if not verify_payment(headers, require=require):
        return {
            "request_id": request_id,
            "status": "payment_required",
            "human_required": False,
            "payment": {
                "payTo": cfg.get("pay_to"),
                "network": cfg.get("network", "eip155:8453"),
                "mode": "local_autonomous",
            },
        }

    # Calibration is applied only as a reporting overlay: the raw posterior is
    # always returned alongside it so a buyer can see both.
    calibrator = SelfCalibrator()
    raw_posterior = result["posterior"]
    calibrated = calibrator.calibrate(raw_posterior)

    OutcomeLog().record(result["status"], bool(result["custody_valid"]), bool(result["billable"]))

    # Never record settlement for work we could not perform.
    if result["billable"]:
        record_settlement(request_id, "$0.25" if require else "$0.00", status=result["status"])
    else:
        record_settlement(request_id, "$0.00", status="not_billable")

    result.update({
        "raw_posterior": raw_posterior,
        "calibrated_posterior": round(calibrated, 3),
        "calibration": calibrator.summary(),
        "human_required": False,
        "mode": "live" if require else "autonomous_free",
        "served_at": _now(),
    })
    return result


def record_feedback(raw_posterior: float, was_correct: bool) -> Dict[str, Any]:
    """Feed a ground-truth outcome back into the calibrator and persist it.

    The calibrator can only learn from labelled outcomes. Nothing in the
    service generates those labels on its own, so this must be called by an
    evaluation harness or by a consuming agent reporting back. Until it is,
    `calibrate()` is an honest identity function rather than a fake adjustment.
    """
    calibrator = SelfCalibrator()
    calibrator.update(raw_posterior, 1.0 if was_correct else 0.0)
    calibrator.save()
    return calibrator.summary()


if __name__ == "__main__":
    import pprint

    print("Starting autonomous control plane...")
    pprint.pp(agent_start())
    print("\nResearch:")
    pprint.pp(agent_research("What is the x402 payment protocol?"))
