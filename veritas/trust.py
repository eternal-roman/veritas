"""Trust scoring derived from paid behaviour, not self-assertion or free traffic.

Three defects shaped this module's current form.

The first version awarded points for features being present in the source tree
and hardcoded `uptime=99.0`, so `/v1/trust` always returned 90 / RECOMMENDED
regardless of what the service actually did. A self-graded score is worse than
none: it invites a buying agent to rely on a number that carries no
information.

The second version fixed that by scoring recorded outcomes — but it recorded
*every* request, including unpaid ones, and `/v1/trust` is free and
unauthenticated. So anyone could move the service's own reputation signal at no
cost (constitution gap G7), and reading the score re-read the whole outcome log
on every call, which meant the cheapest way to degrade the service was to use
it (defect O3).

Both are fixed here. Outcomes are stored as counters — reading them is one row,
whatever the lifetime request count — and only requests that were **paid for**
contribute to the score. Free traffic is still counted and still reported in
the basis, because it is real behaviour and hiding it would be its own
dishonesty; it simply cannot manufacture a reputation. An instance nobody has
paid has no commercial track record, and UNPROVEN is the correct answer.

What this still is not: an external attestation. The graded party computes the
score from its own records. A buyer should treat it as one input, cross-check
the enforcement pointers in the constitution, and weigh an unverifiable
self-report accordingly — see constitution gap G10.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MIN_SAMPLES_FOR_SCORE = 10

_DB_FILENAME = "trust.sqlite3"

#: One row, incremented in place. The whole point of O3's fix: the cost of
#: reading the score does not grow with how much the service has been used.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS outcome_counts (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    paid_total        INTEGER NOT NULL DEFAULT 0,
    paid_completed    INTEGER NOT NULL DEFAULT 0,
    paid_refused      INTEGER NOT NULL DEFAULT 0,
    paid_unavailable  INTEGER NOT NULL DEFAULT 0,
    paid_custody_ok   INTEGER NOT NULL DEFAULT 0,
    free_total        INTEGER NOT NULL DEFAULT 0,
    free_completed    INTEGER NOT NULL DEFAULT 0,
    free_refused      INTEGER NOT NULL DEFAULT 0,
    free_unavailable  INTEGER NOT NULL DEFAULT 0,
    free_custody_ok   INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO outcome_counts (id) VALUES (1);
"""

_COLUMNS = (
    "paid_total", "paid_completed", "paid_refused", "paid_unavailable",
    "paid_custody_ok", "free_total", "free_completed", "free_refused",
    "free_unavailable", "free_custody_ok",
)


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
    """Counters of served requests, split by whether anyone paid for them."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(
            base_dir or os.getenv("VERITAS_RUNTIME_DIR") or ".veritas_runtime"
        )

    @property
    def path(self) -> Path:
        return self.base_dir / _DB_FILENAME

    def _connect(self) -> sqlite3.Connection:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn

    def record(self, status: str, custody_valid: bool, billable: bool,
               paid: bool = False) -> None:
        """Count one served request. Never raises: telemetry must not break
        request serving, and a request that was delivered stays delivered
        whether or not we managed to count it."""
        prefix = "paid" if paid else "free"
        bumps = [f"{prefix}_total"]
        if status in ("completed", "refused", "unavailable"):
            bumps.append(f"{prefix}_{status}")
        if custody_valid:
            bumps.append(f"{prefix}_custody_ok")
        assignments = ", ".join(f"{column} = {column} + 1" for column in bumps)
        try:
            conn = self._connect()
        except (sqlite3.Error, OSError):
            return
        try:
            with conn:
                # Column names come from the fixed tuple above, never from a
                # caller: `status` is checked against a literal allowlist
                # before it can reach the statement.
                conn.execute(
                    f"UPDATE outcome_counts SET {assignments} WHERE id = 1"  # nosec B608
                )
        except (sqlite3.Error, OSError):
            return
        finally:
            conn.close()

    def row_count(self) -> int:
        """Rows backing the counters. One, by construction — the structural
        assertion behind the O3 fix."""
        try:
            conn = self._connect()
        except (sqlite3.Error, OSError):
            return 0
        try:
            return int(conn.execute("SELECT COUNT(*) AS n FROM outcome_counts").fetchone()["n"])
        finally:
            conn.close()

    def stats(self) -> dict[str, Any]:
        empty = dict.fromkeys(_COLUMNS, 0)
        try:
            conn = self._connect()
        except (sqlite3.Error, OSError):
            return empty
        try:
            row = conn.execute("SELECT * FROM outcome_counts WHERE id = 1").fetchone()
        except (sqlite3.Error, OSError):
            return empty
        finally:
            conn.close()
        return {column: int(row[column]) for column in _COLUMNS} if row else empty


def score_service(log: OutcomeLog | None = None) -> TrustScore:
    stats = (log or OutcomeLog()).stats()
    total = stats["paid_total"]
    basis: dict[str, Any] = {
        **stats,
        "min_samples": MIN_SAMPLES_FOR_SCORE,
        "counts": (
            "verified-payment requests, recorded at delivery time — before "
            "the settlement outcome is known"
        ),
        "excluded": (
            "Unpaid requests are recorded and reported here but never scored: "
            "/v1/trust is free and unauthenticated, so free traffic could "
            "otherwise manufacture a reputation at no cost."
        ),
        "self_reported": (
            "Computed by the graded party from its own records. Treat it as "
            "one input, not as authorization; see constitution gap G10."
        ),
    }

    if total < MIN_SAMPLES_FOR_SCORE:
        return TrustScore(
            overall=None,
            recommendation="UNPROVEN",
            flags=["INSUFFICIENT_DATA"],
            basis=basis,
        )

    custody_rate = stats["paid_custody_ok"] / total
    availability = 1.0 - (stats["paid_unavailable"] / total)
    # Refusing sometimes is a positive signal — a service that never refuses is
    # not exercising its epistemic gate — but refusing almost always is not.
    refusal_rate = stats["paid_refused"] / total
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
        basis={**basis, "custody_rate": round(custody_rate, 3),
               "availability": round(availability, 3),
               "refusal_rate": round(refusal_rate, 3)},
    )
