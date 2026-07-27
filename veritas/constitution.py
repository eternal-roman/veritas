"""The Veritas venue constitution, machine-readable and enforcement-linked.

This module is the normative source; CONSTITUTION.md is a rendering of it and
a test keeps the two in sync. Each article states one norm of the venue this
service operates in — the network of buyer agents, seller services,
facilitators, registries, and attesters — and either points at the artifact
that enforces it (a test, a CI gate, or a schema invariant) or admits it is
aspirational (evidence level L0, with the roadmap phase expected to promote
it).

`CONSTITUTION_VERSION` is the version of this document, not of the package:
the package version stays single-sourced in `veritas/__init__.py` (article
A8), and `build_constitution` embeds both so a reader can tell which package
shipped which articles.

Pointer resolution is string-level (the named test function, CI step string,
or schema message exists). That proves the enforcement artifact is real, not
that it fully covers the article's meaning — the same L1 "holds on these
cases" register as the rest of this repository.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import __version__
from .hashing import compute_content_hash

CONSTITUTION_VERSION = "1.0"

VALID_ENFORCEMENT_KINDS = {"test", "ci-gate", "schema"}
VALID_EVIDENCE_LEVELS = {"L0", "L1"}
VALID_SCOPES = {"service", "venue"}


def _article(
    id: str,
    title: str,
    statement: str,
    scope: str,
    evidence_level: str,
    enforcement: list[dict[str, str]],
    promoted_by: str | None = None,
) -> dict[str, Any]:
    article: dict[str, Any] = {
        "id": id,
        "title": title,
        "statement": statement,
        "scope": scope,
        "evidence_level": evidence_level,
        "enforcement": enforcement,
    }
    if promoted_by is not None:
        article["promoted_by"] = promoted_by
    return article


ARTICLES: tuple[dict[str, Any], ...] = (
    # Service articles: the eight invariants from AGENTS.md, now citable.
    _article(
        "A1",
        "One engine",
        "Every surface routes research through veritas.pipeline.run_research; there is no second retrieval, custody, or belief path.",
        "service",
        "L1",
        [{"kind": "test", "pointer": "tests/test_integration.py::test_control_plane_uses_shared_engine"}],
    ),
    _article(
        "A2",
        "Outage honesty",
        "Absent evidence is never reported when retrieval failed: unavailable is not no_evidence.",
        "service",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_pipeline.py::test_outage_is_unavailable_not_no_evidence"},
            {"kind": "ci-gate", "pointer": "unavailability_honesty"},
        ],
    ),
    _article(
        "A3",
        "Never bill own failure",
        "The service never bills for its own failure: an unavailable response is never billable.",
        "service",
        "L1",
        [
            {"kind": "schema", "pointer": "unavailable response must not be billable"},
            {"kind": "test", "pointer": "tests/test_pipeline.py::test_outage_is_not_billable"},
        ],
    ),
    _article(
        "A4",
        "Verify before work, settle after",
        "Payment is verified before work begins and settled only after deliverable work exists.",
        "service",
        "L1",
        [{"kind": "test", "pointer": "tests/test_integration.py::test_payment_is_checked_before_work_is_done"}],
    ),
    _article(
        "A5",
        "Retrievers are untrusted",
        "Retrievers may raise and may ignore max_results; the pipeline defends against both.",
        "service",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_pipeline.py::test_raising_retriever_becomes_unavailable_not_a_crash"},
            {"kind": "test", "pointer": "tests/test_pipeline.py::test_max_results_is_enforced_against_the_retriever"},
        ],
    ),
    _article(
        "A6",
        "Enforced wire contract",
        "The wire contract is validated against real pipeline output, so contract and behaviour cannot silently diverge.",
        "service",
        "L1",
        [{"kind": "test", "pointer": "tests/test_pipeline.py::test_response_conforms_to_contract"}],
    ),
    _article(
        "A7",
        "Misconfiguration is never free service",
        "Invalid payment configuration is reported as misconfigured and never silently becomes free or live service.",
        "service",
        "L1",
        [{"kind": "test", "pointer": "tests/test_integration.py::test_invalid_pay_to_does_not_become_live"}],
    ),
    _article(
        "A8",
        "Single-sourced version",
        "The package version is single-sourced from veritas.__init__ and flows to every surface that reports it.",
        "service",
        "L1",
        [{"kind": "ci-gate", "pointer": "veritas.__version__"}],
    ),
    # Venue articles: the norms this service holds toward the wider venue.
    _article(
        "A9",
        "Discovery honesty",
        "Discovery surfaces advertise only networks on which the service can actually construct a settlement.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_integration.py::test_every_supported_network_has_a_settlement_asset"},
            {"kind": "test", "pointer": "tests/test_payment.py::test_unknown_network_has_no_settlement_asset"},
        ],
    ),
    _article(
        "A10",
        "Pricing transparency",
        "The price is disclosed before any work as a spec-shaped 402 challenge with exact atomic amounts, and discovery endpoints are free to read.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_payment.py::test_challenge_is_spec_shaped"},
            {"kind": "test", "pointer": "tests/test_api.py::test_missing_payment_returns_spec_shaped_402"},
        ],
    ),
    _article(
        "A11",
        "Reputation is not self-attested",
        "Trust is derived from recorded behaviour only, and below the sample floor the service reports UNPROVEN rather than a manufactured score.",
        "venue",
        "L1",
        [{"kind": "test", "pointer": "tests/test_api.py::test_trust_is_unproven_without_data"}],
    ),
    _article(
        "A12",
        "Refusal rights and independent verification",
        "The seller may refuse honestly and bill for the refusal, and the buyer can verify every published hash and receipt without the seller's cooperation.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_pipeline.py::test_genuine_emptiness_is_billable_refusal"},
            {"kind": "test", "pointer": "tests/test_api.py::test_verify_endpoint_checks_hashes"},
            {"kind": "test", "pointer": "tests/test_custody.py::test_ledger_detects_tampering"},
        ],
    ),
    _article(
        "A13",
        "Settlement fairness",
        "A request whose retrieval failed is never billed and never settled.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_pipeline.py::test_outage_is_not_billable"},
            {"kind": "ci-gate", "pointer": "unavailability_honesty"},
        ],
    ),
    _article(
        "A14",
        "Simulators declare themselves",
        "Simulated components label themselves as simulated, and known deviations from production strength are published in this document's known_gaps.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_payment.py::test_simulated_facilitator_labels_itself"},
            {"kind": "test", "pointer": "tests/test_constitution.py::test_known_gaps_shape"},
        ],
    ),
    _article(
        "A15",
        "Evidence-level register",
        "Every article in this constitution carries an evidence level, and any unenforced article is explicitly marked aspirational.",
        "venue",
        "L1",
        [{"kind": "test", "pointer": "tests/test_constitution.py::test_article_ids_unique_and_levels_consistent"}],
    ),
    # Aspirational articles: named norms with no enforcement yet. Each cites
    # the roadmap phase expected to promote it to L1.
    _article(
        "A16",
        "Portable reputation",
        "Reputation should become portable through signed attestations and on-chain identity so buyers can carry trust across venues.",
        "venue",
        "L0",
        [],
        promoted_by="ROADMAP Phase 4.3 (ERC-8004 registration) and 5.1 (signed attestations)",
    ),
    _article(
        "A17",
        "Dispute path",
        "Disputes should have a resolution path beyond independent hash verification.",
        "venue",
        "L0",
        [],
        promoted_by="ROADMAP Phase 5 (reputation and counterparty checks)",
    ),
    _article(
        "A18",
        "Registry liveness honesty",
        "Registry listings should reflect liveness: register on boot, deregister on shutdown.",
        "venue",
        "L0",
        [],
        promoted_by="ROADMAP Phase 4.1 (registry publication)",
    ),
)

# Deviations between what an article claims and what the code does today.
# An open gap must name a witness test that pins the current weak behaviour,
# so fixing the code forces this register to be updated.
KNOWN_GAPS: tuple[dict[str, Any], ...] = (
    {
        "id": "G1",
        "article": "A14",
        "status": "open",
        "description": (
            "veritas/autonomous/local_facilitator.py verify_payment() accepts any "
            "non-empty payment header, and control_plane.agent_research() hardcodes "
            "the $0.25 price instead of reading payment config. Both are labelled "
            "simulator behaviour, but they are weaker than the HTTP path, whose "
            "facilitator verification fails closed. The control plane must not be "
            "exposed as a paid network surface until this is fixed."
        ),
        "witness_test": "tests/test_constitution.py::test_known_gap_simulator_accepts_any_header",
    },
)


def build_constitution() -> dict[str, Any]:
    """Return the served constitution document with a stable content hash."""
    doc: dict[str, Any] = {
        "name": "Veritas Venue Constitution",
        "constitution_version": CONSTITUTION_VERSION,
        "veritas_version": __version__,
        "articles": [dict(a) for a in ARTICLES],
        "known_gaps": [dict(g) for g in KNOWN_GAPS],
    }
    # Hash the stable body only; generatedAt is added after (see
    # veritas/identity.py for the defect this ordering prevents).
    doc["content_hash"] = compute_content_hash(json.dumps(doc, sort_keys=True))
    doc["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return doc


def validate_constitution(doc: dict[str, Any]) -> list[str]:
    """Return a list of constitution-document violations; empty means conformant."""
    problems: list[str] = []

    for key in ("constitution_version", "veritas_version", "articles", "known_gaps", "content_hash"):
        if key not in doc:
            problems.append(f"missing field: {key}")
    if problems:
        return problems

    seen_ids: set[str] = set()
    for article in doc["articles"]:
        aid = article.get("id", "<missing id>")
        if aid in seen_ids:
            problems.append(f"duplicate article id: {aid}")
        seen_ids.add(aid)
        for key in ("title", "statement", "scope", "evidence_level", "enforcement"):
            if key not in article:
                problems.append(f"{aid}: missing field {key}")
        if article.get("scope") not in VALID_SCOPES:
            problems.append(f"{aid}: invalid scope {article.get('scope')!r}")
        level = article.get("evidence_level")
        if level not in VALID_EVIDENCE_LEVELS:
            problems.append(f"{aid}: invalid evidence_level {level!r}")
        enforcement = article.get("enforcement", [])
        if level == "L1" and not enforcement:
            problems.append(f"{aid}: L1 requires at least one enforcement entry")
        if level == "L0":
            if enforcement:
                problems.append(f"{aid}: L0 must not list enforcement")
            if not article.get("promoted_by"):
                problems.append(f"{aid}: L0 must name what promotes it to L1")
        for entry in enforcement:
            if entry.get("kind") not in VALID_ENFORCEMENT_KINDS:
                problems.append(f"{aid}: invalid enforcement kind {entry.get('kind')!r}")
            if not entry.get("pointer"):
                problems.append(f"{aid}: enforcement entry missing pointer")

    for gap in doc["known_gaps"]:
        gid = gap.get("id", "<missing id>")
        if gap.get("article") not in seen_ids:
            problems.append(f"{gid}: references unknown article {gap.get('article')!r}")
        if gap.get("status") not in {"open", "closed"}:
            problems.append(f"{gid}: invalid status {gap.get('status')!r}")
        if gap.get("status") == "open" and not gap.get("witness_test"):
            problems.append(f"{gid}: open gap must name a witness test")

    return problems
