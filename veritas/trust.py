"""Trust scoring derived from observed behaviour, not self-assertion.

The previous version awarded points for features being present in the source
tree and hardcoded `uptime=99.0`, so `/v1/trust` always returned 90 /
RECOMMENDED regardless of what the service actually did. A self-graded score
is worse than none: it invites a buying agent to rely on a number that carries
no information.

Scores here are computed from recorded outcomes. With no outcomes recorded,
the service reports UNPROVEN rather than inventing a number.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MIN_SAMPLES_FOR_SCORE = 10


@dataclass
class TrustScore:
    overall: float | None
    recommendation: str
    flags: list[str] = field(default_factory=list)
    basis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "recommendation": self.recommendation,
            "flags": self.flags,
            "basis": self.basis,
        }


class OutcomeLog:
    """Append-only record of served requests, used to compute trust."""

    def __init__(self, base_dir: str | None = None):
        runtime = Path(base_dir or os.getenv("VERITAS_RUNTIME_DIR", ".veritas_runtime"))
        self.path = runtime / "outcomes.jsonl"

    def record(self, status: str, custody_valid: bool, billable: bool) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as fh:
                fh.write(json.dumps({
                    "status": status,
                    "custody_valid": custody_valid,
                    "billable": billable,
                }) + "\n")
        except OSError:
            # Trust telemetry must never break request serving.
            pass

    def stats(self) -> dict[str, Any]:
        total = completed = refused = unavailable = custody_ok = 0
        try:
            with self.path.open() as fh:
                for line in fh:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    total += 1
                    status = entry.get("status")
                    completed += status == "completed"
                    refused += status == "refused"
                    unavailable += status == "unavailable"
                    custody_ok += bool(entry.get("custody_valid"))
        except OSError:
            pass
        return {
            "total": total,
            "completed": completed,
            "refused": refused,
            "unavailable": unavailable,
            "custody_valid": custody_ok,
        }


def score_service(log: OutcomeLog | None = None) -> TrustScore:
    stats = (log or OutcomeLog()).stats()
    total = stats["total"]

    if total < MIN_SAMPLES_FOR_SCORE:
        return TrustScore(
            overall=None,
            recommendation="UNPROVEN",
            flags=["INSUFFICIENT_DATA"],
            basis={**stats, "min_samples": MIN_SAMPLES_FOR_SCORE},
        )

    custody_rate = stats["custody_valid"] / total
    availability = 1.0 - (stats["unavailable"] / total)
    # Refusing sometimes is a positive signal — a service that never refuses is
    # not exercising its epistemic gate — but refusing almost always is not.
    refusal_rate = stats["refused"] / total
    refusal_health = 1.0 if 0.02 <= refusal_rate <= 0.5 else 0.5

    score = 100.0 * (0.5 * custody_rate + 0.3 * availability + 0.2 * refusal_health)

    flags: list[str] = []
    if custody_rate < 1.0:
        flags.append("CUSTODY_FAILURES_OBSERVED")
    if availability < 0.9:
        flags.append("LOW_AVAILABILITY")
    if refusal_rate > 0.5:
        flags.append("EXCESSIVE_REFUSAL")

    if score >= 80:
        rec = "RECOMMENDED"
    elif score >= 60:
        rec = "CAUTION"
    else:
        rec = "NOT_RECOMMENDED"
        flags.append("LOW_SCORE")

    return TrustScore(
        overall=round(score, 1),
        recommendation=rec,
        flags=flags,
        basis={**stats, "custody_rate": round(custody_rate, 3),
               "availability": round(availability, 3),
               "refusal_rate": round(refusal_rate, 3)},
    )
