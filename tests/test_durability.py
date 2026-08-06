"""Durable, bounded state: trust counters and custody receipts.

Two audited defects and one constitution gap:

* O3 — `/v1/trust` re-read the entire outcome log on every call, and the
  endpoint is free and unauthenticated. Cost per request grew with lifetime
  request count, so the cheapest way to degrade the service was to use it.
* G7 / T1 — that same log counted *every* request including unpaid ones, so
  anyone could move the service's own reputation signal for free.
* O7 — custody receipts were written with a plain `write_text`. A crash
  mid-write leaves a truncated JSON file, and the receipt is the artifact a
  buyer relies on after the response is gone.
"""

from __future__ import annotations

import json

from veritas.custody import CustodyStore
from veritas.trust import MIN_SAMPLES_FOR_SCORE, OutcomeLog, score_service


def _record(log: OutcomeLog, n: int, *, paid: bool, status: str = "completed") -> None:
    for _ in range(n):
        log.record(status, custody_valid=True, billable=True, paid=paid)


# -- O3: reading trust is O(1), not O(lifetime requests) --------------------


def test_stats_are_counters_not_a_rescan(tmp_path):
    """The fix is structural: counts are stored, so reading them cannot get
    slower as the service is used."""
    log = OutcomeLog(tmp_path)
    _record(log, 3, paid=True)
    assert log.stats()["paid_total"] == 3

    # A rescan implementation would have to read three rows; a counter reads
    # one. Asserting the shape rather than the timing keeps this honest: this
    # is not a benchmark and no timing claim is made here.
    assert log.row_count() == 1, "one counter row, regardless of request count"


def test_counts_survive_restart(tmp_path):
    _record(OutcomeLog(tmp_path), 4, paid=True)
    assert OutcomeLog(tmp_path).stats()["paid_total"] == 4


def test_recording_never_raises_when_the_store_is_unusable(tmp_path):
    """Trust telemetry must never break request serving."""
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the store wants a directory")
    OutcomeLog(blocked).record("completed", True, True, paid=True)  # must not raise
    assert OutcomeLog(blocked).stats()["paid_total"] == 0


# -- G7: free traffic cannot move the score ---------------------------------


def test_free_traffic_does_not_establish_a_trust_score(tmp_path):
    """The gap this closes. Unpaid requests are still counted and reported —
    they are real behaviour — but they do not produce a score, because
    anyone can generate them at no cost."""
    log = OutcomeLog(tmp_path)
    _record(log, MIN_SAMPLES_FOR_SCORE * 3, paid=False)
    score = score_service(log)
    assert score.recommendation == "UNPROVEN"
    assert score.overall is None
    assert score.basis["free_total"] == MIN_SAMPLES_FOR_SCORE * 3


def test_paid_traffic_does_establish_a_score(tmp_path):
    log = OutcomeLog(tmp_path)
    _record(log, MIN_SAMPLES_FOR_SCORE, paid=True)
    # A little honest refusal is a positive signal, not a defect.
    log.record("refused", custody_valid=True, billable=True, paid=True)
    score = score_service(log)
    assert score.recommendation != "UNPROVEN"
    assert score.overall is not None


def test_the_score_states_that_it_counts_paid_requests_only(tmp_path):
    """A buyer weighing the number needs to know what population it is over."""
    log = OutcomeLog(tmp_path)
    _record(log, MIN_SAMPLES_FOR_SCORE, paid=True)
    basis = score_service(log).basis
    assert basis["counts"] == "settled paid requests only"
    assert basis["free_total"] == 0


def test_free_requests_are_still_visible_in_the_basis(tmp_path):
    """Suppressing them would hide real behaviour; they are reported and
    simply not scored."""
    log = OutcomeLog(tmp_path)
    _record(log, 5, paid=False, status="unavailable")
    _record(log, MIN_SAMPLES_FOR_SCORE, paid=True)
    basis = score_service(log).basis
    assert basis["free_total"] == 5
    assert basis["free_unavailable"] == 5


# -- O7: a receipt is written atomically or not at all ----------------------


def test_a_receipt_is_never_left_half_written(tmp_path):
    """Written to a temporary file and renamed, so a reader sees the old
    complete receipt or the new complete receipt, never a truncated one."""
    store = CustodyStore(str(tmp_path))
    record = store.save({
        "request_id": "r1", "query": "q", "status": "completed",
        "custody_root": "sha256:x", "custody_valid": True, "evidence": [],
    })
    assert record["persisted"] is True
    path = tmp_path / "receipts" / "r1.json"
    assert json.loads(path.read_text())["request_id"] == "r1"
    # No temporary files left behind for a scraper or a retention pass to trip on.
    assert [p.name for p in (tmp_path / "receipts").iterdir()] == ["r1.json"]


def test_rewriting_a_receipt_replaces_it_atomically(tmp_path):
    store = CustodyStore(str(tmp_path))
    base = {"request_id": "r1", "query": "q", "custody_root": "sha256:x",
            "custody_valid": True, "evidence": []}
    store.save({**base, "status": "completed"})
    store.save({**base, "status": "refused"})
    assert store.load("r1")["status"] == "refused"
    assert len(list((tmp_path / "receipts").iterdir())) == 1


def test_an_unwritable_receipt_is_reported_not_raised(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    record = CustodyStore(str(blocked)).save({
        "request_id": "r1", "status": "completed", "custody_root": "sha256:x",
        "custody_valid": True, "evidence": [],
    })
    assert record["persisted"] is False
    assert "/" not in record["error"]
