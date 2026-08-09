"""Evolver — evolutionary Idea agent (formerly Scout).

Implements a cyclic evolutionary creativity ensemble:
deconstruct → expand → explore → mutate ⇄ evaluate → orchestrate.

Outputs are **vision fuel** (WATCH), never STATE NEXT or product ship claims.
"""

from __future__ import annotations

from veritas.evolver.engine import (
    render_idea_bus_section,
    run_creativity_engine,
    write_report,
)
from veritas.evolver.graph import MAX_GENERATIONS, SCORE_THRESHOLD, evolution_check

__all__ = [
    "run_creativity_engine",
    "render_idea_bus_section",
    "write_report",
    "evolution_check",
    "SCORE_THRESHOLD",
    "MAX_GENERATIONS",
]
