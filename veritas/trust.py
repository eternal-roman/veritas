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

The served score is computed from independently verified third-party audit
records the caller supplies. This instance's outcome counters stay in the
basis as an operator log and never set ``overall``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runtime import resolve_runtime_dir

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
        self.base_dir = resolve_runtime_dir(base_dir)

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


def verify_external_attestation(record: Mapping[str, Any]) -> tuple[bool, str]:
    """Verify a third-party audit record. Not this instance's outcome log."""
    from veritas.audit import verify_audit_record

    return verify_audit_record(record)


def score_service(
    log: OutcomeLog | None = None,
    *,
    audit_records: list[Mapping[str, Any]] | None = None,
    publication: list[Mapping[str, Any]] | None = None,
) -> TrustScore:
    """Score from independently verified audit records.

    ``log`` counters stay in the basis as an operator log. They never set
    ``overall``. GET /v1/trust with no records is UNPROVEN.
    """
    from veritas.audit import is_self_audit, survival_report

    stats = (log or OutcomeLog()).stats()
    verified: list[Mapping[str, Any]] = []
    rejected = 0
    for rec in audit_records or []:
        ok, _reason = verify_external_attestation(rec)
        if ok and not is_self_audit(rec):
            verified.append(rec)
        else:
            rejected += 1
    report = survival_report(list(verified), publication=publication)
    basis: dict[str, Any] = {
        **stats,
        "min_samples": MIN_SAMPLES_FOR_SCORE,
        "counts": (
            "independently verified third-party audit records; operator "
            "paid-request counters are reported but never scored"
        ),
        "excluded": (
            "Unpaid requests are recorded and reported here but never scored: "
            "/v1/trust is free and unauthenticated, so free traffic could "
            "otherwise manufacture a reputation at no cost."
        ),
        "score_source": "independent_audits",
        "independent_records": len(verified),
        "rejected_records": rejected,
        "survival": report,
        "operator_log": (
            "this instance's own outcome counters; not the score"
        ),
    }

    verdict = report["verdict"]
    if verdict == "contested":
        return TrustScore(
            overall=None,
            recommendation="NOT_RECOMMENDED",
            flags=["INDEPENDENT_DIVERGENCE"],
            basis=basis,
        )
    if verdict == "surviving" and report["distinct_auditors"] >= 1:
        return TrustScore(
            overall=None,
            recommendation="RECOMMENDED",
            flags=[],
            basis=basis,
        )
    flags = ["INSUFFICIENT_INDEPENDENT_EVIDENCE"]
    if verdict == "curated":
        flags.append("PUBLICATION_WITHHELD")
    elif verdict == "unpublished":
        flags.append("NO_AUDITOR_PUBLICATION")
    return TrustScore(
        overall=None,
        recommendation="UNPROVEN",
        flags=flags,
        basis=basis,
    )
