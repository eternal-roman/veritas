"""The dogfooding cycles run in CI, not just once by hand.

A cycle that was run once and written up is an anecdote. Running them as tests
means a regression in the paid path or in the limits fails the build, and the
committed reports under `docs/dogfood/` stay true rather than becoming a
description of a version that no longer exists.

They stay *scripts* as well as tests because an operator evaluating this
service should be able to run them against their own instance and read the
JSON, without pytest and without reading our test suite.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import dogfood_cycle1, dogfood_cycle2, dogfood_cycle3, dogfood_cycle4, dogfood_cycle5

REPO = Path(__file__).resolve().parents[1]




def test_cycle1_cold_install_first_boot_passes():
    report = dogfood_cycle1.run()
    failed = [c for c in report["checks"] if not c["pass"]]
    assert not failed, json.dumps(failed, indent=2)
    assert report["total"] >= 7
    assert report["all_pass"] is True

def test_cycle2_paying_buyer_passes_every_scenario():
    report = dogfood_cycle2.run()
    failed = [s for s in report["scenarios"] if not s["pass"]]
    assert not failed, json.dumps(failed, indent=2)
    assert report["total"] >= 7


def test_cycle3_hostile_caller_refuses_every_probe():
    report = dogfood_cycle3.run()
    got_through = [p for p in report["probes"] if not p["refused"]]
    assert not got_through, json.dumps(got_through, indent=2)
    assert report["total"] >= 8


def test_cycle4_answers_every_operator_question_from_the_ledger():
    report = dogfood_cycle4.run(count=4)
    assert not report["unanswerable"], report["unanswerable"]
    assert report["owed_agrees_with_reconcile"], (
        "`veritas-ops owed` and `veritas-ops reconcile` tell different stories"
    )




def test_cycle5_ecosystem_participant_passes():
    report = dogfood_cycle5.run()
    failed = [c for c in report["checks"] if not c["pass"]]
    assert not failed, __import__("json").dumps(failed, indent=2)
    assert report["total"] >= 7
    assert report["all_pass"] is True

def test_the_committed_reports_match_the_current_code():
    """A stale artifact is worse than no artifact: it documents behaviour the
    service no longer has. Scenario names and pass/fail are compared, not
    timings or transaction ids, which vary per run by design."""
    for cycle, module, collection, name_field, verdict in (
        (2, dogfood_cycle2, "scenarios", "scenario", "pass"),
        (3, dogfood_cycle3, "probes", "probe", "refused"),
    ):
        path = REPO / "docs" / "dogfood" / f"cycle{cycle}" / "report.json"
        committed = json.loads(path.read_text(encoding="utf-8"))
        fresh = module.run()
        assert {case[name_field] for case in committed[collection]} == {
            case[name_field] for case in fresh[collection]
        }, f"cycle {cycle}: the committed report lists different cases"
        assert all(case[verdict] for case in committed[collection]), (
            f"cycle {cycle}: the committed report records a failure"
        )


def test_no_dogfood_script_performs_an_outbound_request():
    """Both cycles claim to make no network call. That claim is load-bearing:
    it is why their results describe the product rather than this sandbox's
    egress."""
    for name in ("dogfood_cycle1.py", "dogfood_cycle2.py", "dogfood_cycle3.py", "dogfood_cycle4.py", "dogfood_cycle5.py"):
        source = (REPO / "scripts" / name).read_text(encoding="utf-8")
        for forbidden in ("urlopen(", "requests.get", "requests.post", "httpx.get"):
            assert forbidden not in source, f"{name} may reach the network via {forbidden}"
