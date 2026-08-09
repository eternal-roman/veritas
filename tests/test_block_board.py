"""L1: block board claim/resolve without thrash."""

from __future__ import annotations

import pytest

from veritas.block_board import BlockBoard, BlockBoardError, seed_known_blocks


def test_post_claim_resolve_inbox(tmp_path):
    board = BlockBoard(tmp_path / "b.sqlite3")
    b = board.post("steward", "Card lag", "tip lag only", kind="cohesion", severity=1)
    assert b.status == "open"
    # dedup
    b2 = board.post("steward", "Card lag", "again", kind="cohesion", severity=1)
    assert b2.block_id == b.block_id
    claimed = board.claim(b.block_id, "researcher")
    assert claimed.status == "claimed"
    with pytest.raises(BlockBoardError):
        board.claim(b.block_id, "other")
    resolved = board.resolve(
        b.block_id, "noop_coherent; no PR", status="resolved"
    )
    assert resolved.status == "resolved"
    path = board.write_inbox(
        "steward", resolved, reports_dir=tmp_path / "inbox"
    )
    assert path.is_file()
    assert "Card lag" in path.read_text(encoding="utf-8")
    board.close()


def test_seed_known_blocks(tmp_path):
    board = BlockBoard(tmp_path / "b.sqlite3")
    seeds = seed_known_blocks(board)
    assert len(seeds) >= 3
    assert any(s.severity == 3 for s in seeds)
    open_ = board.list_open()
    assert len(open_) >= 3
    board.close()


def test_seed_known_blocks_does_not_reopen_resolved(tmp_path):
    """Catalog seeds must not thrash seed→resolve→seed every Researcher tick."""
    board = BlockBoard(tmp_path / "b.sqlite3")
    first = seed_known_blocks(board)
    assert len(first) >= 3
    money = next(s for s in first if s.blocked_agent == "money_loop")
    board.claim(money.block_id, "researcher")
    board.resolve(money.block_id, "probe OK", status="resolved")
    second = seed_known_blocks(board)
    # money_loop title must not reappear as a new open block
    open_money = [
        b
        for b in board.list_open()
        if b.blocked_agent == "money_loop"
        and "Money-path env unset" in b.title
    ]
    assert open_money == []
    # force=True reopens catalog for deliberate re-probe
    forced = seed_known_blocks(board, force=True)
    assert any(
        s.blocked_agent == "money_loop" and s.status == "open" for s in forced
    )
    board.close()
    assert isinstance(second, list)

