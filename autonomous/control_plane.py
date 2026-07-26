"""Unified agent-native control plane.

Single entry point that requires zero human configuration.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from autonomous.bootstrap import bootstrap, load_config
from autonomous.zero_key_retrieval import free_retrieve
from autonomous.local_facilitator import verify_payment, record_settlement, record_attempt
from autonomous.self_calibrator import SelfCalibrator
from veritas.hashing import compute_content_hash
from veritas.custody import CustodyLedger
from veritas.bayesian import BayesianBelief, update_belief


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def agent_start() -> Dict[str, Any]:
    return bootstrap()


def agent_research(query: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    headers = headers or {}
    cfg = load_config()
    request_id = str(uuid.uuid4())

    # Payment check (local autonomous mode defaults to allow)
    require = cfg.get("require_payment", False)
    record_attempt(request_id, headers)
    if not verify_payment(headers, require=require):
        return {
            "status": "payment_required",
            "request_id": request_id,
            "human_required": False,
            "payment": {
                "payTo": cfg.get("pay_to"),
                "network": cfg.get("network", "eip155:8453"),
                "mode": "local_autonomous",
            },
        }

    ledger = CustodyLedger()
    ledger.append("created", "control_plane", {"query": query, "request_id": request_id})

    sources = free_retrieve(query, max_results=4)
    evidence_items = []
    for s in sources:
        text = s.get("text") or ""
        if len(text) < 20:
            continue
        h = compute_content_hash(text)
        ledger.append("evidence_created", "zero_key_retrieval", {"content_hash": h, "url": s.get("url")})
        evidence_items.append({
            "hash": h,
            "url": s.get("url"),
            "title": s.get("title"),
            "excerpt": text[:320],
        })

    if not evidence_items:
        ledger.append("refused", "control_plane", {"reason": "no_evidence"})
        record_settlement(request_id, "$0.00", status="refused")
        return {
            "request_id": request_id,
            "status": "refused",
            "query": query,
            "posterior": 0.1,
            "claims": [],
            "evidence": [],
            "custody_root": ledger.root_hash(),
            "custody_valid": ledger.verify_chain(),
            "human_required": False,
            "mode": "autonomous_free",
            "timestamp": _now(),
        }

    claims = []
    overall = BayesianBelief(hypothesis=query, prior=0.3)
    for i, ev in enumerate(evidence_items):
        statement = f"[{ev.get('title') or ev['url']}] {ev['excerpt']}"
        belief = BayesianBelief(hypothesis=statement, prior=0.4)
        belief = update_belief(belief, 0.8, 0.25, ev["hash"])
        claims.append({
            "id": f"c{i+1}",
            "statement": statement,
            "evidence_hash": ev["hash"],
            "confidence": round(belief.posterior, 3),
        })
        overall = update_belief(overall, 0.75, 0.3, ev["hash"])

    if len(evidence_items) >= 2:
        overall = update_belief(overall, 0.85, 0.22, "multi_source")

    # Self-calibration pass
    calibrator = SelfCalibrator()
    calibrated = calibrator.calibrate(overall.posterior)

    status = "completed" if calibrated >= 0.4 else "refused"
    if status == "refused":
        claims = []

    ledger.append(status, "control_plane", {"posterior": calibrated})
    record_settlement(request_id, "$0.00" if not require else "$0.25", status=status)

    return {
        "request_id": request_id,
        "status": status,
        "query": query,
        "posterior": round(calibrated, 3),
        "raw_posterior": round(overall.posterior, 3),
        "claims": claims,
        "evidence": evidence_items,
        "custody_root": ledger.root_hash(),
        "custody_valid": ledger.verify_chain(),
        "human_required": False,
        "mode": "autonomous_free",
        "calibrator": calibrator.summary(),
        "timestamp": _now(),
    }


if __name__ == "__main__":
    import pprint
    print("Starting autonomous control plane...")
    pprint.pp(agent_start())
    print("\nResearch:")
    pprint.pp(agent_research("What is the x402 payment protocol?"))
