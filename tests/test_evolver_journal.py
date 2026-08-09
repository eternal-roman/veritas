"""Roadblock → Evolver → origin mapping workflow."""
from __future__ import annotations

from pathlib import Path

from veritas.evolver.journal import JournalError, ProblemJournal, workflow_phase
from veritas.evolver.workflow import run_full_cycle, run_tick


def test_submit_requires_sender_and_title(tmp_path: Path) -> None:
    j = ProblemJournal(tmp_path / "j.sqlite3")
    try:
        j.submit("", "t", "d")
        raise AssertionError("expected JournalError")
    except JournalError:
        pass
    j.close()


def test_full_workflow_maps_back_to_origin(tmp_path: Path) -> None:
    jpath = tmp_path / "j.sqlite3"
    root = tmp_path / "artifacts"
    j = ProblemJournal(jpath)
    p = j.submit(
        "conductor",
        "Merge lag on green product PR",
        "PR is green but unmerged past 6m budget.",
        kind="stall",
        severity=3,
        sender_role="conductor",
        source_surface="ORG_LOOPS.md",
        correlation_id="corr-test-1",
    )
    assert p.status == "open"
    assert p.sender_agent == "conductor"
    assert workflow_phase(p.status) == "1_submitted"

    p = j.claim(p.problem_id, "evolver-test")
    assert p.status == "evolving"
    assert p.claimed_by == "evolver-test"

    result = run_full_cycle(
        p, j, artifact_root=root, evolver_id="evolver-test", prefer_langgraph=False,
    )
    j2 = ProblemJournal(jpath)
    final = j2.get(p.problem_id)
    j2.close()

    assert result["mapped_to_origin"] == "conductor"
    assert final.sender_agent == "conductor"
    assert final.status == "engineering"
    assert workflow_phase(final.status) == "6_engineering_handoff"
    assert final.best_blueprint
    assert final.origin_report_path and Path(final.origin_report_path).is_file()
    body = Path(final.origin_report_path).read_text(encoding="utf-8")
    assert "conductor" in body and final.problem_id in body and "corr-test-1" in body
    assert Path(final.overseer_report_path).is_file()
    eng = Path(final.engineering_report_path).read_text(encoding="utf-8")
    assert "Requested by (origin)" in eng and "conductor" in eng
    j.close()


def test_dedup_same_sender_title(tmp_path: Path) -> None:
    j = ProblemJournal(tmp_path / "j.sqlite3")
    a = j.submit("flywheel", "Same title", "d1", kind="block")
    b = j.submit("flywheel", "Same title", "d2", kind="block")
    assert a.problem_id == b.problem_id
    j.close()


def test_seed_and_tick(tmp_path: Path) -> None:
    base = tmp_path / ".veritas"
    arts = tmp_path / "evolver_arts"
    out = run_tick(
        base_dir=base, artifact_root=arts, max_cycles=1, seed=True,
        prefer_langgraph=False, evolver_id="evolver",
    )
    assert out["schema"] == "veritas.evolver.tick.v0"
    assert out["seeded"] and out["acted"]
    acted = out["acted"][0]
    assert acted["mapped_to_origin"]
    assert Path(acted["paths"]["origin_report"]).is_file()
    assert Path(acted["paths"]["overseer_report"]).is_file()
    assert Path(acted["paths"]["engineering_report"]).is_file()


def test_cli_submit_list_cycle(tmp_path: Path) -> None:
    from veritas.evolver.__main__ import main

    j = str(tmp_path / "j.sqlite3")
    arts = str(tmp_path / "arts")
    assert main([
        "--journal", j, "submit",
        "--sender", "pruner", "--role", "pruner",
        "--title", "Ship veto needs clearer battery signal",
        "--detail", "HEAVY path unclear when CI green.",
        "--kind", "concern", "--severity", "2", "--source", "PRUNER.md",
    ]) == 0
    assert main(["--journal", j, "list"]) == 0
    journal = ProblemJournal(j)
    open_ = journal.list_open()
    assert open_
    pid = open_[0].problem_id
    journal.close()
    assert main(["--journal", j, "cycle", pid, "--artifact-root", arts]) == 0
    journal = ProblemJournal(j)
    p = journal.get(pid)
    journal.close()
    assert p.sender_agent == "pruner" and p.status == "engineering"
