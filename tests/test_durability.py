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
* O10 / O.6 — receipts and ledger rows grew without bound; pruning without
  tombstones collapses "we deleted this" into 404 "never existed".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from veritas.custody import CustodyStore, ReceiptPresence
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


def test_paid_traffic_does_not_establish_an_independent_score(tmp_path):
    """G10 closed: operator paid counters never set overall."""
    log = OutcomeLog(tmp_path)
    _record(log, MIN_SAMPLES_FOR_SCORE, paid=True)
    log.record("refused", custody_valid=True, billable=True, paid=True)
    score = score_service(log)
    assert score.recommendation == "UNPROVEN"
    assert score.overall is None
    assert score.basis["score_source"] == "independent_audits"


def test_the_score_states_that_it_counts_paid_requests_only(tmp_path):
    """A buyer weighing the number needs to know what population it is over."""
    log = OutcomeLog(tmp_path)
    _record(log, MIN_SAMPLES_FOR_SCORE, paid=True)
    basis = score_service(log).basis
    assert "independently verified" in basis["counts"]
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


def test_independent_audits_set_the_recommendation(tmp_path):
    """G10 close: only verified third-party audits move the recommendation."""
    pytest.importorskip("eth_account")
    from eth_account import Account

    from veritas.audit import perform_audit
    from veritas.hashing import compute_content_hash
    from veritas.notary.fetch import FetchResult
    from veritas.notary.pack import build_evidence_pack
    from veritas.notary.sign import OperatorSigner, sign_evidence_record

    def fetch(body: bytes):
        def fake(request_url, **kwargs):
            return FetchResult(
                request_url=request_url, final_url=request_url, status=200,
                headers={"content-type": "text/plain"}, body=body, truncated=False,
            )
        return fake

    def signer():
        return OperatorSigner("0x" + bytes(Account.create().key).hex())

    body = "independent standing body"
    seller = signer()
    fields = {
        "url": "https://example.org/g10",
        "content_hash": compute_content_hash(body),
        "observed_at": "2026-08-08T12:00:00Z",
        "extract_version": "extract.v1",
        "request_id": "req-g10",
    }
    pack = build_evidence_pack(
        **fields, attestation=sign_evidence_record(fields, seller)
    )
    record = perform_audit(
        pack, signer=signer(), robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=fetch(body.encode("utf-8")),
    )
    log = OutcomeLog(tmp_path)
    _record(log, MIN_SAMPLES_FOR_SCORE, paid=True)
    score = score_service(
        log, audit_records=[record], publication=[record]
    )
    assert score.recommendation == "RECOMMENDED"
    assert score.overall is None
    assert score.basis["score_source"] == "independent_audits"
    assert "verify_external_attestation" in Path(
        __import__("veritas.trust", fromlist=["score_service"]).__file__
    ).read_text(encoding="utf-8")


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
    assert json.loads(path.read_text(encoding="utf-8"))["request_id"] == "r1"
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


# --- O17: receipt lookup must not become an arbitrary-file read -------------
#
# `GET /v1/receipts/{request_id}` passed the caller's string straight into
# `base_dir / f"{request_id}.json"`. Starlette's router refuses a path
# parameter containing "/", which hid the defect on Linux — but "\" is a
# separator on Windows and is *not* a URL separator, so it survives routing
# intact. Observed against a running server before the fix:
#
#     GET /v1/receipts/..%5Ccanary  ->  200 {"SECRET":"canary-must-not-leak"}
#
# Any *.json file the service could read was readable by an unauthenticated
# caller, and `.veritas_agent/wallet.keystore.json` is exactly such a file.

TRAVERSAL_IDS = [
    "../canary",
    r"..\canary",
    "../../canary",
    r"..\..\canary",
    "sub/../../canary",
    r"sub\..\..\canary",
    "/etc/passwd",
    r"C:\Windows\win",
    r"\\server\share\x",
    "",
    ".",
    "..",
    ".hidden",
]


def test_a_receipt_id_cannot_escape_the_receipt_directory(tmp_path):
    """A traversing id reads nothing, on every platform."""
    store = CustodyStore(str(tmp_path))
    store.save({"request_id": "r1", "status": "completed", "query": "q",
                "custody_root": "sha256:x", "custody_valid": True, "evidence": []})

    # A real JSON file one level above the receipts directory: the exact shape
    # the live exploit reached.
    (tmp_path / "canary.json").write_text('{"SECRET":"canary"}', encoding="utf-8")

    for bad in TRAVERSAL_IDS:
        assert store.load(bad) is None, f"{bad!r} escaped the receipt directory"

    # The legitimate id still works — the guard must not break the feature.
    assert store.load("r1")["status"] == "completed"


def test_a_traversing_id_is_refused_before_it_reaches_the_filesystem(tmp_path, monkeypatch):
    """Rejection is by validation, not by the file happening to be absent.

    If the guard were only a containment check after a read, a symlinked or
    race-swapped path could still be opened. Nothing may touch the disk.
    """
    store = CustodyStore(str(tmp_path))
    opened: list[str] = []
    real = Path.read_text

    def spy(self, *a, **kw):
        opened.append(str(self))
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", spy)
    for bad in TRAVERSAL_IDS:
        store.load(bad)
    assert opened == [], f"traversing ids reached the filesystem: {opened}"


def test_a_receipt_is_never_written_outside_its_directory(tmp_path):
    """The write side takes the same guard as the read side."""
    store = CustodyStore(str(tmp_path))
    record = store.save({"request_id": "../escaped", "status": "completed",
                         "query": "q", "custody_root": "sha256:x",
                         "custody_valid": True, "evidence": []})
    assert record["persisted"] is False
    assert not (tmp_path / "escaped.json").exists()
    assert not (tmp_path.parent / "escaped.json").exists()


# -- O10 / O.6: retention prune with durable tombstones ---------------------


def _save_receipt(store: CustodyStore, request_id: str = "r1") -> dict:
    return store.save({
        "request_id": request_id, "query": "q", "status": "completed",
        "custody_root": "sha256:x", "custody_valid": True, "evidence": [],
    })


def _backdate_receipt(store: CustodyStore, request_id: str, stored_at: str) -> None:
    path = store.base_dir / f"{request_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["stored_at"] = stored_at
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def test_expired_receipt_is_pruned_to_gone_with_tombstone(tmp_path):
    """Expired → body gone + durable tombstone; lookup says gone, not unknown."""
    store = CustodyStore(str(tmp_path))
    assert _save_receipt(store, "r-old")["persisted"] is True
    _backdate_receipt(store, "r-old", "2020-01-01T00:00:00Z")
    cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)

    report = store.prune(cutoff)
    assert report["deleted"] == 1
    assert report["tombstoned"] == 1
    assert store.load("r-old") is None
    assert store.lookup("r-old") is ReceiptPresence.GONE
    assert (tmp_path / "receipt_tombstones" / "r-old.json").is_file()


def test_unexpired_receipt_survives_prune_and_stays_loadable(tmp_path):
    store = CustodyStore(str(tmp_path))
    _save_receipt(store, "r-fresh")
    # Cutoff in the past: nothing stored after it is expired.
    cutoff = datetime(2000, 1, 1, tzinfo=timezone.utc)
    report = store.prune(cutoff)
    assert report["deleted"] == 0
    assert store.lookup("r-fresh") is ReceiptPresence.PRESENT
    assert store.load("r-fresh")["request_id"] == "r-fresh"


def test_never_existed_receipt_stays_unknown(tmp_path):
    store = CustodyStore(str(tmp_path))
    assert store.lookup("never-seen") is ReceiptPresence.UNKNOWN
    assert store.load("never-seen") is None
    # Prune must not invent a tombstone for ids we never held.
    store.prune(datetime(2099, 1, 1, tzinfo=timezone.utc))
    assert store.lookup("never-seen") is ReceiptPresence.UNKNOWN


def test_reprune_does_not_erase_tombstones(tmp_path):
    """Re-deleting tombstones would collapse 410 back into 404."""
    store = CustodyStore(str(tmp_path))
    _save_receipt(store, "r-old")
    _backdate_receipt(store, "r-old", "2020-01-01T00:00:00Z")
    cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
    store.prune(cutoff)
    store.prune(cutoff)
    assert store.lookup("r-old") is ReceiptPresence.GONE


def test_unsafe_request_id_never_escapes_on_lookup_or_tombstone(tmp_path):
    """Same path guard on lookup and tombstone paths as on load/save."""
    store = CustodyStore(str(tmp_path))
    _save_receipt(store, "r1")
    (tmp_path / "canary.json").write_text('{"SECRET":"canary"}', encoding="utf-8")
    for bad in TRAVERSAL_IDS:
        assert store.lookup(bad) is ReceiptPresence.UNKNOWN, bad
        assert store._tombstone_path(bad) is None, bad
    assert store.lookup("r1") is ReceiptPresence.PRESENT


def test_trust_counters_stay_one_row_after_volume(tmp_path):
    """O3 structural bound: OutcomeLog cannot grow with request volume.
    O.6 does not add a per-request log; prune is a no-op for counters."""
    log = OutcomeLog(tmp_path)
    _record(log, 50, paid=True)
    _record(log, 50, paid=False)
    assert log.row_count() == 1
    assert log.stats()["paid_total"] == 50
