"""LLM seam for the Evolver ensemble.

Default is a deterministic offline model so CI and free-mode ticks stay honest
without network keys. Live providers are opt-in via env.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol


class ChatModel(Protocol):
    def complete(self, system: str, user: str) -> str: ...


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


class OfflineEvolutionaryModel:
    """Deterministic recombinant generator — no network, no invented authority.

    Produces schema-valid outputs so the graph can be CI-tested and used under
    HOLD invent when no API key is present. Scores are structural, not market
    claims.
    """

    def complete(self, system: str, user: str) -> str:
        low = (system + "\n" + user).lower()
        problem = _slice_after(user, "Problem:") or _slice_after(user, "problem:") or user
        problem = problem.strip()[:400]

        if "first principles engine" in low or "deconstructive reduction" in low:
            return json.dumps(
                [
                    "Value exchange must be verifiable by a party that does not trust the operator",
                    "Failure modes must be distinguishable from empty results",
                    "Work must not be billed when delivery is impossible",
                    "Coordination cost grows with dual sources of truth",
                    f"The scarce resource for '{problem[:80]}' is contact with external reality",
                ]
            )

        if "constraints mapper" in low:
            return json.dumps(
                [
                    "Single settlement / claim path — no dual money rails",
                    "Fail closed on verification outage",
                    "Evidence for environment claims must be dated probes",
                    "Human Stage-1 residues cannot be invented green by agents",
                    "Seedlings and blueprints are WATCH hypotheses, not approvals",
                ]
            )

        if "recombinant search" in low:
            return json.dumps(
                [
                    {
                        "domain": "ecology_predation",
                        "mechanism": "predators cull free-riders so honest producers are not outcompeted",
                        "transfer": "challenge/forfeit markets cull false warranties",
                    },
                    {
                        "domain": "double_entry_bookkeeping",
                        "mechanism": "no debit without matching credit under audit",
                        "transfer": "every spend needs a durable counterpart record",
                    },
                    {
                        "domain": "supply_chain_lot_trace",
                        "mechanism": "lot codes bind physical goods to custody events",
                        "transfer": "hash-chained custody binds deliverables to payments",
                    },
                ]
            )

        if "evolutionary mutator" in low:
            gen = 0
            m = re.search(r"Gen\s+(\d+)", user)
            if m:
                gen = int(m.group(1))
            return json.dumps(
                [
                    {
                        "blueprint": (
                            f"Gen{gen + 1}-A: predator-audit market for D0 warranties — "
                            "bonded refutation predicates with deterministic re-exec; "
                            "buyer SDK checks standing before pay."
                        ),
                        "paradigm_ids": ["ecology_predation"],
                        "rationale": "Cross predation with payment diligence.",
                    },
                    {
                        "blueprint": (
                            f"Gen{gen + 1}-B: double-entry credits ledger with reserve-before-work "
                            "(Tollgate-style) and crash-refund paths already on the money rail."
                        ),
                        "paradigm_ids": ["double_entry_bookkeeping"],
                        "rationale": "Credits as prepaid balance only; no second payer.",
                    },
                    {
                        "blueprint": (
                            f"Gen{gen + 1}-C: lot-trace evidence packs as the SKU "
                            "(notarize/verify) with public existence before discovery theater."
                        ),
                        "paradigm_ids": ["supply_chain_lot_trace"],
                        "rationale": "Stage-1 existence first; D0 wedge SKUs.",
                    },
                ]
            )

        if "lead systems architect" in low:
            return (
                "# Evolutionary execution plan (Idea fuel — not STATE NEXT)\n\n"
                "## DAG\n"
                "1. Measure landmass (`veritas-ops existence`)\n"
                "2. Stage-1 human residues (PyPI / TLS / mainnet pay-to)\n"
                "3. D0 SKU hardening (notarize/verify warrants)\n"
                "4. Unsolicited contact falsifier window\n\n"
                "## Acceptance (falsifiable)\n"
                "- unsolicited_settlements remains measured, never invented\n"
                "- existence scorecard green on testnet evidence\n"
                "- no dual payer/engine\n\n"
                f"## Problem\n{problem}\n"
            )

        if "score each blueprint" in low:
            # Fallback empty list; validator has programmatic path.
            return "[]"

        return json.dumps({"error": "unknown_prompt", "echo": problem[:120]})


def _slice_after(text: str, marker: str) -> str:
    i = text.find(marker)
    if i < 0:
        return ""
    return text[i + len(marker) :]


class OpenAICompatibleModel:
    """Minimal OpenAI-compatible chat completion client (optional)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, system: str, user: str) -> str:
        import urllib.request

        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.4,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "veritas-evolver/0.1",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310 — fixed API URL
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]


def get_model() -> ChatModel:
    """Resolve model from env; default offline.

    Env:
      VERITAS_EVOLVER_MODEL=offline|openai
      OPENAI_API_KEY / VERITAS_EVOLVER_API_KEY
      VERITAS_EVOLVER_BASE_URL
      VERITAS_EVOLVER_MODEL_NAME
    """
    mode = (os.environ.get("VERITAS_EVOLVER_MODEL") or "offline").strip().lower()
    if mode in ("offline", "mock", "none", "0"):
        return OfflineEvolutionaryModel()

    key = (
        os.environ.get("VERITAS_EVOLVER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()
    if not key:
        return OfflineEvolutionaryModel()

    base = (
        os.environ.get("VERITAS_EVOLVER_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    )
    name = os.environ.get("VERITAS_EVOLVER_MODEL_NAME") or "gpt-4o-mini"
    return OpenAICompatibleModel(api_key=key, base_url=base, model=name)


def parse_json_response(text: str, *, expect: type = list) -> Any:
    try:
        data = _extract_json(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return [] if expect is list else {}
    if expect is list and not isinstance(data, list):
        return []
    if expect is dict and not isinstance(data, dict):
        return {}
    return data
