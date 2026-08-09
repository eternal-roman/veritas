"""Shared DNA for the evolutionary Idea ensemble (Evolver)."""

from __future__ import annotations

from typing import Any, TypedDict


class PopulationMember(TypedDict, total=False):
    id: int
    blueprint: str
    score: float
    generation: int
    parents: list[int]
    paradigm_ids: list[str]


class AgentState(TypedDict, total=False):
    """Memory passed between evolutionary nodes.

    Built for Veritas program fuel (WATCH patterns + recombinant blueprints),
    not for setting STATE NEXT or shipping product code.
    """

    original_problem: str
    first_principles: list[str]
    system_constraints: list[str]
    distant_paradigms: list[dict[str, Any]]
    population: list[dict[str, Any]]
    generation_count: int
    best_solution: dict[str, Any]
    final_architecture: str
    history: list[dict[str, Any]]
