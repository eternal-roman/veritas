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

import uuid
from datetime import datetime, timezone
from typing import Any

from veritas.payment_config import get_payment_config
from veritas.pipeline import observe_urls_enabled, run_research
from veritas.trust import OutcomeLog

from .bootstrap import bootstrap, load_config
from .local_facilitator import record_attempt, record_settlement, verify_payment


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def agent_start() -> dict[str, Any]:
    """Provision a free-mode config with no human input."""
    return bootstrap()


def agent_research(
    query: str,
    headers: dict[str, str] | None = None,
    max_results: int = 4,
) -> dict[str, Any]:
    """Run research through the shared engine under agent-native settlement."""
    headers = headers or {}
    cfg = load_config()
    require = bool(cfg.get("require_payment", False))
    # The recorded amount follows payment config; it was previously a
    # hardcoded "$0.25" that ignored VERITAS_PRICE entirely.
    price = get_payment_config().price

    # Verify before doing the work. The previous ordering ran the full
    # retrieval and belief pass first and discarded the result if payment was
    # missing, which let an unpaid caller consume the entire cost of a request
    # and contradicted the verify-before-work ordering the HTTP surface uses.
    request_id = str(uuid.uuid4())
    record_attempt(request_id, headers, amount=price if require else "$0.00")

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

    result = run_research(
        query, max_results=max_results, observe_urls=observe_urls_enabled()
    )
    # The pipeline mints its own request_id; keep the one already recorded
    # against the payment attempt so settlement and research reconcile.
    result["request_id"] = request_id

    # The calibration overlay is gone with the posterior it calibrated. It read
    # a number whose hypothesis was the query string, and reported it through an
    # identity function because no labelled outcome has ever been recorded.
    # `SelfCalibrator` stays in the tree for when labelled outcomes exist; it is
    # no longer applied to a response, because there is nothing honest to apply
    # it to. See veritas/support.py for what ships instead.
    OutcomeLog().record(result["status"], bool(result["custody_valid"]), bool(result["billable"]))

    # Never record settlement for work we could not perform.
    if result["billable"]:
        record_settlement(request_id, price if require else "$0.00", status=result["status"])
    else:
        record_settlement(request_id, "$0.00", status="not_billable")

    result.update({
        "human_required": False,
        "mode": "live" if require else "autonomous_free",
        "served_at": _now(),
    })
    return result


def record_feedback(raw_posterior: float, was_correct: bool) -> dict[str, Any]:
    """Feed a ground-truth outcome back into the calibrator and persist it.

    The calibrator can only learn from labelled outcomes. Nothing in the
    service generates those labels on its own, so this must be called by an
    evaluation harness or by a consuming agent reporting back. Until it is,
    `calibrate()` is an honest identity function rather than a fake adjustment.
    """
    from .self_calibrator import SelfCalibrator

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
