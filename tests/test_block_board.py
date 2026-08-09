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
