"""Simple trust scoring for the service."""

from dataclasses import dataclass
from typing import List

@dataclass
class TrustScore:
    overall: float
    flags: List[str]
    recommendation: str

def score_service(
    has_custody: bool = True,
    has_bayesian: bool = True,
    has_refusal: bool = True,
    uptime: float = 99.0,
) -> TrustScore:
    score = 40.0
    flags: List[str] = []
    if has_custody:
        score += 20
    if has_bayesian:
        score += 15
    if has_refusal:
        score += 15
    score += min(10.0, max(0.0, uptime - 90))
    if score >= 80:
        rec = "RECOMMENDED"
    elif score >= 60:
        rec = "CAUTION"
    else:
        rec = "NOT_RECOMMENDED"
        flags.append("LOW_SCORE")
    return TrustScore(overall=round(score, 1), flags=flags, recommendation=rec)
