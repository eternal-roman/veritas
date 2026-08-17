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

CONSTITUTION_VERSION = "3.0"

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
        "Catalog pull and URL observe share one money path and one signals store; there is no research engine.",
        "service",
        "L1",
        [{"kind": "test", "pointer": "tests/test_integration.py::test_catalog_engine_is_signals_not_research"}],
    ),
    _article(
        "A2",
        "Outage honesty",
        "Absent evidence is never reported when retrieval failed: unavailable is not no_evidence.",
        "service",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_signals.py::test_venue_unavailable_is_not_an_empty_catalog"},
            {"kind": "ci-gate", "pointer": "catalog_honesty"},
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
            {"kind": "test", "pointer": "tests/test_signals.py::test_venue_unavailable_is_not_settled"},
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
        "Venues are untrusted",
        "Venue fetches may raise and may ignore limit; the catalog pull defends against both.",
        "service",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_signals.py::test_raising_opener_becomes_signals_error"},
            {"kind": "test", "pointer": "tests/test_signals.py::test_pull_caps_limit"},
        ],
    ),
    _article(
        "A6",
        "Enforced wire contract",
        "The wire contract is validated against real catalog output, so contract and behaviour cannot silently diverge.",
        "service",
        "L1",
        [{"kind": "test", "pointer": "tests/test_signals.py::test_catalog_response_conforms_to_contract"}],
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
        "Reputation is earned, not manufactured",
        "Trust served at /v1/trust is derived from independently verified third-party audit records; free traffic cannot move it; without those records the service reports UNPROVEN rather than a manufactured score.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_api.py::test_trust_is_unproven_without_data"},
            {"kind": "test", "pointer": "tests/test_durability.py::test_free_traffic_does_not_establish_a_trust_score"},
            {"kind": "test", "pointer": "tests/test_durability.py::test_independent_audits_set_the_recommendation"},
        ],
    ),
    _article(
        "A12",
        "Refusal rights and independent verification",
        "The seller may refuse honestly and bill for the refusal, and the buyer can verify every published hash and receipt without the seller's cooperation.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_signals.py::test_polymarket_search_miss_does_not_dump_the_book"},
            {"kind": "test", "pointer": "tests/test_custody.py::test_delivered_chain_is_verifiable_without_the_seller"},
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
            {"kind": "test", "pointer": "tests/test_signals.py::test_venue_unavailable_is_not_settled"},
            {"kind": "test", "pointer": "tests/test_money_path.py::test_venue_failure_abandons_the_authorization_and_never_settles"},
            {"kind": "ci-gate", "pointer": "catalog_honesty"},
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
    _article(
        "A19",
        "Replay safety",
        "A resubmitted payment authorization never consumes a second retrieval pass; where the work was already delivered it is re-delivered rather than refused, and an unusable replay guard refuses rather than waves through.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_replay.py::test_resubmitted_header_does_the_work_once"},
            {"kind": "test", "pointer": "tests/test_money_path.py::test_replayed_authorization_returns_the_deliverable_it_paid_for"},
            {"kind": "test", "pointer": "tests/test_replay.py::test_an_unusable_ledger_refuses_rather_than_waving_through"},
        ],
    ),
    _article(
        "A20",
        "Bounded buyer spending",
        "A buyer-side payment is signed only after challenge validation and within declared spend caps, and a refused payment never reaches the signer.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_gated_payment.py::test_gated_payment_enforces_spend_caps"},
            {"kind": "ci-gate", "pointer": "veritas.evaluations.payment_model"},
        ],
    ),
    _article(
        "A21",
        "Agent self-provisioning",
        "An agent can provision this service — configuration, receiving keypair, and running server — without human input, with key material created locally and never transmitted, and with the steps that still require a human, funding and public deployment, stated rather than hidden.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_wallet.py::test_wallet_key_material_stays_on_disk"},
            {"kind": "test", "pointer": "tests/test_agent_cli.py::test_up_configures_server_from_bootstrap_config"},
        ],
    ),
    _article(
        "A22",
        "Observation limits",
        "A record attests what this service received from a source at a time, not what that source served to any other party.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_signals.py::test_snapshots_state_they_are_not_verdicts"},
        ],
    ),
    _article(
        "A23",
        "Provenance truthfulness",
        "The provider named in a piece of evidence is the provider that was actually queried, and evidence carries the licence under which it may be reused.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_signals.py::test_off_allowlist_host_is_refused"},
            {"kind": "test", "pointer": "tests/test_signals.py::test_as_evidence_is_not_a_verdict_and_uses_license"},
        ],
    ),
    _article(
        "A24",
        "Delivery is recorded before payment is captured",
        "What was produced for a buyer is written durably before settlement is attempted, so a failure between the two leaves a record of what is owed rather than silence.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_money_path.py::test_delivery_is_durable_before_settlement_is_attempted"},
            {"kind": "test", "pointer": "tests/test_ledger.py::test_settlement_before_delivery_is_refused"},
        ],
    ),
    _article(
        "A25",
        "An unknown settlement is not reported as a failed one",
        "A settlement whose facilitator never answered is recorded and reported as indeterminate, not as failure, and the buyer receives the work rather than having it withheld on an outcome we did not observe.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_money_path.py::test_indeterminate_settlement_delivers_and_says_so"},
            {"kind": "test", "pointer": "tests/test_ledger.py::test_indeterminate_settlement_is_not_recorded_as_failure"},
        ],
    ),
    _article(
        "A26",
        "Standing is what survives independent audit",
        "Counterparty standing is computed by the record holder from third-party-signed audit records, never by the audited party: an origin that could not be observed is never scored against a seller, a self-audit carries no independence, and any volume of records signed by one key counts as one auditor.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_audit.py::test_unobserved_never_counts_for_or_against_a_seller"},
            {"kind": "test", "pointer": "tests/test_audit.py::test_self_audit_is_excluded_from_independence_counts"},
            {"kind": "test", "pointer": "tests/test_audit.py::test_record_volume_from_one_key_counts_as_one_auditor"},
        ],
    ),
    _article(
        "A27",
        "Warranted claims are falsifiable or labeled",
        "A warranted deliverable carries seller-authored falsification predicates that any party evaluates deterministically — a challenge terminates in re-execution, never in an arbiter — a defective challenge context decides nothing and forfeits nothing either way, and content with no decidable refutation procedure is sold labeled unwarrantable rather than dressed in a warranty.",
        "venue",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_warranty.py::test_challenge_terminates_in_deterministic_reexecution"},
            {"kind": "test", "pointer": "tests/test_warranty.py::test_unwarrantable_content_is_labeled_never_dressed_in_a_warranty"},
            {"kind": "test", "pointer": "tests/test_warranty.py::test_undecidable_context_forfeits_nothing_either_way"},
        ],
    ),
    _article(
        "A28",
        "Integration surfaces are registered",
        "Integration surfaces are registered, not discovered by accident: every HTTP route the service mounts is either listed in the machine-readable hooks registry served at /v1/hooks or named in an explicit exclusion list, the registry never advertises a surface that does not exist, and the absence of push delivery is stated in the registry rather than left to be inferred.",
        "service",
        "L1",
        [
            {"kind": "test", "pointer": "tests/test_hooks.py::test_every_app_route_is_registered_or_excluded"},
            {"kind": "test", "pointer": "tests/test_hooks.py::test_registry_advertises_no_phantom_routes"},
            {"kind": "test", "pointer": "tests/test_hooks.py::test_push_absence_is_honest"},
        ],
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
        "status": "closed",
        "description": (
            "veritas/autonomous/local_facilitator.py verify_payment() accepted any "
            "non-empty payment header, and control_plane.agent_research() hardcoded "
            "the $0.25 price instead of reading payment config. Both were labelled "
            "simulator behaviour, but they were weaker than the HTTP path, whose "
            "facilitator verification fails closed."
        ),
        "resolution": (
            "Closed in constitution 1.1: the simulator now decodes headers via the "
            "shared veritas.x402.decode_payment_header and requires the x402 "
            "structural shape (tests/test_autonomous_payment.py::"
            "test_simulator_rejects_malformed_header_when_required), and recorded "
            "simulator amounts follow payment config (tests/"
            "test_autonomous_payment.py::test_control_plane_price_follows_payment_config). "
            "The remaining weakness is registered as G2."
        ),
    },
    {
        "id": "G2",
        "article": "A14",
        "status": "closed",
        "description": (
            "The local simulator validates payment structure and configuration, not "
            "signatures: a structurally valid payload with a forged signature passes. "
            "The HTTP path's facilitator verification remains the strong gate, and "
            "the control plane must not be exposed as a paid network surface while "
            "this gap is open."
        ),
        "resolution": (
            "Closed in constitution 2.9: verify_payment(require=True) recovers the "
            "EIP-712 signer of the EIP-3009 transferWithAuthorization (pinned USDC "
            "domain) and refuses unless it equals authorization.from. Forged, "
            "expired, and incomplete authorizations fail closed. Missing "
            "eth_account fails closed. Balance and nonce-unused stay on-chain and "
            "are not claimed "
            "(tests/test_autonomous_payment.py::"
            "test_simulator_rejects_structurally_valid_forged_signature, "
            "tests/test_eip3009.py::test_valid_authorization_passes). "
            "The remaining weakness is registered as G13."
        ),
    },
    {
        "id": "G13",
        "article": "A14",
        "status": "open",
        "description": (
            "The local simulator recovers the EIP-712 signer (G2 closed) but "
            "does not check that the nonce is unused on chain or that the "
            "payer has balance. A valid signature over an empty or already-"
            "spent authorization still passes. The HTTP path's live "
            "facilitator remains the strong gate for settlement. The control "
            "plane must not be exposed as a paid network surface while this "
            "gap is open."
        ),
        "witness_test": "tests/test_autonomous_payment.py::test_known_gap_simulator_does_not_check_nonce_or_balance",
    },
    {
        "id": "G3",
        "article": "A2",
        "status": "closed",
        "description": (
            "The relevance gate was enforced only inside StaticCorpusRetriever, never in "
            "the pipeline, so on the served path any source of 40 or more characters "
            "produced a billable 'completed' answer however unrelated to the query. The "
            "evaluation harness certified a filter production never applied."
        ),
        "resolution": (
            "Closed in constitution 2.0 on the research path. Constitution 3.0 "
            "removed that engine "
            "(tests/test_integration.py::test_catalog_engine_is_signals_not_research)."
        ),
    },
    {
        "id": "G4",
        "article": "A23",
        "status": "closed",
        "description": (
            "The keyless retrieval tier called a metasearch library that shuffles across "
            "Google, Bing, Yandex, Brave and others, then labelled every result "
            "provider: 'duckduckgo' — reselling scraped result pages under a falsified "
            "provenance label, inside a product selling provenance."
        ),
        "resolution": (
            "Closed in constitution 2.0: the metasearch dependency is removed. "
            "Constitution 3.0 dropped the research retrievers; venue hosts are "
            "allowlisted "
            "(tests/test_signals.py::test_off_allowlist_host_is_refused)."
        ),
    },
    {
        "id": "G5",
        "article": "A12",
        "status": "closed",
        "description": (
            "The custody chain was computed and then discarded: only the root hash and a "
            "self-asserted custody_valid were published, so a buyer had nothing to check "
            "and A12 was false as written."
        ),
        "resolution": (
            "Closed in constitution 2.0: the chain ships in the response and a buyer "
            "re-runs verify_chain_records over delivered data "
            "(tests/test_custody.py::"
            "test_delivered_chain_is_verifiable_without_the_seller)."
        ),
    },
    {
        "id": "G6",
        "article": "A13",
        "status": "closed",
        "description": (
            "A paid request was not idempotent. The nonce was burned before the work, and "
            "a buyer whose connection dropped after settlement was charged and received "
            "nothing: retrying the same authorization returned 409 rather than the "
            "deliverable already paid for. Settlement fairness (A13) did not hold on "
            "this path."
        ),
        "resolution": (
            "Closed in constitution 2.1: veritas/ledger.py records the delivery before "
            "settlement is attempted and keys a state machine on the authorization "
            "nonce, so resubmitting it returns the stored deliverable "
            "(tests/test_money_path.py::"
            "test_replayed_authorization_returns_the_deliverable_it_paid_for). "
            "The retrieval pass still runs exactly once "
            "(tests/test_money_path.py::test_a_replay_does_not_run_the_work_again). "
            "Bounded: single-instance scope — two instances behind a balancer do not "
            "share the ledger, so a replay routed to the other one still fails; and a "
            "settlement whose facilitator never answers stays indeterminate until "
            "reconciliation, which G9 tracks."
        ),
    },
    {
        "id": "G7",
        "article": "A11",
        "status": "closed",
        "description": (
            "The trust score was derived from an outcome log that recorded every request "
            "including unpaid ones, and the endpoint is unauthenticated, so anyone could "
            "move the service's own reputation signal with free traffic."
        ),
        "resolution": (
            "Closed in constitution 2.2: only paid requests are scored "
            "(tests/test_durability.py::test_free_traffic_does_not_establish_a_trust_score). "
            "Free outcomes are still counted and reported in the basis — they are real "
            "behaviour — but cannot manufacture a reputation. An instance nobody has paid "
            "reports UNPROVEN, which is the correct answer. This closes the manipulation "
            "route only. Independent standing is G10 (closed in 2.7)."
        ),
    },
    {
        "id": "G10",
        "article": "A11",
        "status": "closed",
        "description": (
            "The trust score is computed by the graded party from its own records. "
            "Nothing external attests to it, and a seller that simply logged favourable "
            "outcomes would produce an identical document. Restricting scoring to paid "
            "traffic (G7) raises the cost of manipulation; it does not make the number "
            "verifiable by the buyer relying on it."
        ),
        "resolution": (
            "Closed in constitution 2.7: GET /v1/trust is UNPROVEN from the "
            "operator log alone; POST /v1/trust scores only independently "
            "verified third-party audit records "
            "(tests/test_durability.py::"
            "test_independent_audits_set_the_recommendation). Seller outcome "
            "counters stay in the basis and never set overall."
        ),
    },
    {
        "id": "G8",
        "article": "A13",
        "status": "closed",
        "description": (
            "No financial ledger existed. The settlement result, including the on-chain "
            "transaction hash, was returned in a response header and then discarded, so "
            "an operator could not say how much was earned, from whom, or for what, and "
            "no settlement could be reconciled."
        ),
        "resolution": (
            "Closed in constitution 2.1: veritas/ledger.py durably records every "
            "authorization, delivery and settlement attempt, and revenue is answerable "
            "from the ledger alone "
            "(tests/test_money_path.py::test_revenue_is_answerable_from_the_ledger_alone). "
            "Bounded: it records what this instance did, which is not proof the chain "
            "agrees — reconciling recorded settlements against on-chain state needs an "
            "RPC endpoint and is tracked as G9."
        ),
    },
    {
        "id": "G11",
        "article": "A26",
        "status": "closed",
        "description": (
            "A survival report summarises the audit records provided to it, and "
            "nothing forces an unfavourable record into that set: whoever assembles "
            "the records can withhold divergence they observed. Divergence counts are "
            "therefore a floor, never a ceiling, and a clean report from a curated "
            "set is not proof of a clean history. Removing this requires auditor-side "
            "publication the seller cannot filter (the Merkle/anchor axis named in "
            "later N1 work)."
        ),
        "resolution": (
            "Closed in constitution 2.7: survival_report is surviving only when "
            "an auditor publication is supplied and no published countable "
            "record is withheld; otherwise unpublished or curated "
            "(tests/test_audit.py::test_withheld_publication_is_curated)."
        ),
    },
    {
        "id": "G12",
        "article": "A27",
        "status": "closed",
        "description": (
            "Warranty bonds are signed commitments, not escrowed value. "
            "Settlement has run only in operator-run testnet arcs (evidence: "
            "docs/program/fable/settlement/), and no escrow or forfeit path "
            "exists on any network, so a fired challenge indicates a forfeit "
            "the payment rails cannot yet enforce, and the "
            "unomittable-negative-reputation property of forfeits is designed, not "
            "real. The wire says so on every warranty (bond_binding: "
            "signed_commitment_not_escrow). Removal requires escrowed bonds over "
            "routine proven settlement (W1)."
        ),
        "resolution": (
            "Closed in constitution 2.8: escrow_bond persists an EIP-3009 "
            "authorization as the lock; settle_forfeit submits it through "
            "the existing facilitator and records a settlement "
            "(tests/test_escrow.py::test_settle_forfeit_submits_locked_authorization, "
            "tests/test_warranty.py::test_escrowed_warranty_forfeit_is_collectable). "
            "Warranties that omit a lock stay labeled "
            "signed_commitment_not_escrow and do not claim collectability. "
            "Not a deployed vault contract. "
            "Mainnet collect unproven."
        ),
    },
    {
        "id": "G9",
        "article": "A13",
        "status": "closed",
        "description": (
            "Recorded settlements are never reconciled against the chain. The ledger "
            "stores what the facilitator told us, including 'indeterminate' entries "
            "where it told us nothing, and no code re-checks any of it against an RPC "
            "endpoint. An operator can therefore say what this instance believes it "
            "earned, but not what it actually holds."
        ),
        "resolution": (
            "Closed in constitution 2.7: Ledger.reconcile_against_chain classifies "
            "recorded settlements via eth_getTransactionReceipt "
            "(tests/test_chain_reconcile.py::test_ledger_reconcile_against_chain). "
            "Routine compose is veritas.money_loop and veritas-ops reconcile-chain. "
            "Report-only: revenue is not rewritten. Mainnet still needs "
            "VERITAS_RPC_URL; testnet defaults apply otherwise."
        ),
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
