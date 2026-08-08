# The Veritas Venue Constitution

A venue constitution is the set of norms a service commits to toward every
other participant in its venue — buyer agents, peer seller services,
facilitators, registries, and attesters — written so that a machine can read
it, cite it, and check it.

**The normative source is `veritas/constitution.py`, version 2.3.** This file
is a rendering of that module; `tests/test_constitution.py` keeps the two in
sync, and the served document is available unpaid at `GET /v1/constitution`
and referenced from `GET /v1/identity`. If this file and the module ever
disagree, the module wins and the test suite fails.

Each article carries an evidence level in the repository's register:

- **L1** — enforced: the article points at a concrete artifact (a named test,
  a CI gate, or a schema invariant) that fails if the norm is broken. The
  claim shape is "holds on these cases", nothing stronger.
- **L0** — aspirational: not yet enforced. The article says so plainly and
  names the roadmap phase expected to promote it.

Pointer resolution is string-level: it proves the enforcement artifact exists,
not that it fully covers the article's meaning.

## Amendment discipline

Amending an article means editing `veritas/constitution.py`, bumping
`CONSTITUTION_VERSION`, and updating this rendering. Statements are matched
verbatim by the sync test, so an article cannot be quietly reworded in one
place. The constitution version is a document version; the package version
stays single-sourced in `veritas/__init__.py` (article A8).

---

## Service articles

These lift the eight invariants of `AGENTS.md` into citable form. Each was
already CI-gated or tested; the constitution adds a stable id another agent
can reference in an attestation or a dispute.

### A1 — One engine (L1)

Every surface routes research through veritas.pipeline.run_research; there is no second retrieval, custody, or belief path.

Enforced by `tests/test_integration.py::test_control_plane_uses_shared_engine`.

### A2 — Outage honesty (L1)

Absent evidence is never reported when retrieval failed: unavailable is not no_evidence.

Enforced by `tests/test_pipeline.py::test_outage_is_unavailable_not_no_evidence`
and the `unavailability_honesty` gate in CI.

### A3 — Never bill own failure (L1)

The service never bills for its own failure: an unavailable response is never billable.

Enforced by the schema invariant "unavailable response must not be billable"
(`veritas/schema.py`) and `tests/test_pipeline.py::test_outage_is_not_billable`.

### A4 — Verify before work, settle after (L1)

Payment is verified before work begins and settled only after deliverable work exists.

Enforced by `tests/test_integration.py::test_payment_is_checked_before_work_is_done`.

### A5 — Retrievers are untrusted (L1)

Retrievers may raise and may ignore max_results; the pipeline defends against both.

Enforced by `tests/test_pipeline.py::test_raising_retriever_becomes_unavailable_not_a_crash`
and `tests/test_pipeline.py::test_max_results_is_enforced_against_the_retriever`.

### A6 — Enforced wire contract (L1)

The wire contract is validated against real pipeline output, so contract and behaviour cannot silently diverge.

Enforced by `tests/test_pipeline.py::test_response_conforms_to_contract`.

### A7 — Misconfiguration is never free service (L1)

Invalid payment configuration is reported as misconfigured and never silently becomes free or live service.

Enforced by `tests/test_integration.py::test_invalid_pay_to_does_not_become_live`.

### A8 — Single-sourced version (L1)

The package version is single-sourced from veritas.__init__ and flows to every surface that reports it.

Enforced by the CI package job, which installs the built wheel and asserts on
`veritas.__version__`.

---

## Venue articles

The norms this service holds toward the wider venue: what a counterparty may
rely on before, during, and after paying.

### A9 — Discovery honesty (L1)

Discovery surfaces advertise only networks on which the service can actually construct a settlement.

Enforced by `tests/test_integration.py::test_every_supported_network_has_a_settlement_asset`
and `tests/test_payment.py::test_unknown_network_has_no_settlement_asset`.

### A10 — Pricing transparency (L1)

The price is disclosed before any work as a spec-shaped 402 challenge with exact atomic amounts, and discovery endpoints are free to read.

Enforced by `tests/test_payment.py::test_challenge_is_spec_shaped`
and `tests/test_api.py::test_missing_payment_returns_spec_shaped_402`.

### A11 — Reputation is earned, not manufactured (L1)

Trust is derived from recorded paid behaviour only; free traffic cannot move it, below the sample floor the service reports UNPROVEN rather than a manufactured score, and the score states that it is the seller's own report.

Enforced by `tests/test_api.py::test_trust_is_unproven_without_data`,
`tests/test_durability.py::test_free_traffic_does_not_establish_a_trust_score`,
and `tests/test_durability.py::test_the_score_states_that_it_counts_paid_requests_only`.
`/v1/trust` is free and unauthenticated, so counting unpaid requests let anyone
manufacture the service's reputation at no cost. Free outcomes are still
recorded and reported in the basis — they are real behaviour — and simply do
not score. The number remains the seller's own report: see G10.

### A12 — Refusal rights and independent verification (L1)

The seller may refuse honestly and bill for the refusal, and the buyer can verify every published hash and receipt without the seller's cooperation.

Enforced by `tests/test_pipeline.py::test_genuine_emptiness_is_billable_refusal`,
`tests/test_api.py::test_verify_endpoint_checks_hashes`, and
`tests/test_custody.py::test_ledger_detects_tampering`.

### A13 — Settlement fairness (L1)

A request whose retrieval failed is never billed and never settled.

Enforced by `tests/test_pipeline.py::test_outage_is_not_billable` and the
`unavailability_honesty` gate in CI.

### A14 — Simulators declare themselves (L1)

Simulated components label themselves as simulated, and known deviations from production strength are published in this document's known_gaps.

Enforced by `tests/test_payment.py::test_simulated_facilitator_labels_itself`
and `tests/test_constitution.py::test_known_gaps_shape`.

### A15 — Evidence-level register (L1)

Every article in this constitution carries an evidence level, and any unenforced article is explicitly marked aspirational.

Enforced by `tests/test_constitution.py::test_article_ids_unique_and_levels_consistent`,
which fails on any article that claims L1 without enforcement or L0 with it.

### A19 — Replay safety (L1)

A resubmitted payment authorization never consumes a second retrieval pass; where the work was already delivered it is re-delivered rather than refused, and an unusable replay guard refuses rather than waves through.

Enforced by `tests/test_replay.py::test_resubmitted_header_does_the_work_once`,
`tests/test_money_path.py::test_replayed_authorization_returns_the_deliverable_it_paid_for`,
and `tests/test_replay.py::test_an_unusable_ledger_refuses_rather_than_waving_through`.
The earlier wording of this article — "is refused" — described a defect, not a
norm: a single-use authorization the buyer cannot re-sign, refused after their
money moved, leaves them with nothing. See G6.

### A20 — Bounded buyer spending (L1)

A buyer-side payment is signed only after challenge validation and within declared spend caps, and a refused payment never reaches the signer.

Enforced by `tests/test_gated_payment.py::test_gated_payment_enforces_spend_caps`
and the `veritas.evaluations.payment_model` bounded model check gated in CI.

### A21 — Agent self-provisioning (L1)

An agent can provision this service — configuration, receiving keypair, and running server — without human input, with key material created locally and never transmitted, and with the steps that still require a human, funding and public deployment, stated rather than hidden.

Enforced by `tests/test_wallet.py::test_wallet_key_material_stays_on_disk`
and `tests/test_agent_cli.py::test_up_configures_server_from_bootstrap_config`.

### A22 — Observation limits (L1)

A record attests what this service received from a source at a time, not what that source served to any other party.

Enforced by `tests/test_truth_restoration.py::test_responses_state_what_they_attest`.
Proving what an origin served to *someone else* would need something like
TLSNotary, zkTLS, or a trusted execution environment. We have none of those, so
the limit is published in every response rather than left for a buyer to find.

### A23 — Provenance truthfulness (L1)

The provider named in a piece of evidence is the provider that was actually queried, and evidence carries the licence under which it may be reused.

Enforced by `tests/test_retrieval_honesty.py::test_no_metasearch_backend_is_used`
and `tests/test_retrieval_honesty.py::test_evidence_carries_licence_through_to_the_response`.

### A24 — Delivery is recorded before payment is captured (L1)

What was produced for a buyer is written durably before settlement is attempted, so a failure between the two leaves a record of what is owed rather than silence.

Enforced by `tests/test_money_path.py::test_delivery_is_durable_before_settlement_is_attempted`
and `tests/test_ledger.py::test_settlement_before_delivery_is_refused`.

### A25 — An unknown settlement is not reported as a failed one (L1)

A settlement whose facilitator never answered is recorded and reported as indeterminate, not as failure, and the buyer receives the work rather than having it withheld on an outcome we did not observe.

Enforced by `tests/test_money_path.py::test_indeterminate_settlement_delivers_and_says_so`
and `tests/test_ledger.py::test_indeterminate_settlement_is_not_recorded_as_failure`.
A facilitator that timed out may still have moved the funds. Recording that as
a failure would understate revenue and would tell a buyer their payment did not
go through when we do not know that.

### A26 — Standing is what survives independent audit (L1)

Counterparty standing is computed by the record holder from third-party-signed audit records, never by the audited party: an origin that could not be observed is never scored against a seller, a self-audit carries no independence, and any volume of records signed by one key counts as one auditor.

Enforced by `tests/test_audit.py::test_unobserved_never_counts_for_or_against_a_seller`,
`tests/test_audit.py::test_self_audit_is_excluded_from_independence_counts`, and
`tests/test_audit.py::test_record_volume_from_one_key_counts_as_one_auditor`.
This is the audit-layer form of the same three norms the service holds
elsewhere: `unavailable` is not `no_evidence`, a self-report is not evidence,
and independence is counted per witness, not per repetition (`veritas/audit.py`,
`docs/program/FABLE_INSIGHTS.md`). What it does not establish: that the records
a report was computed from are all the records that exist — that is G11.

---

## Aspirational articles

Named norms with no enforcement yet — **aspirational: not yet enforced** in
every case. Listing them here is a commitment to the honesty of the register,
not a claim that they hold.

### A16 — Portable reputation (L0)

Reputation should become portable through signed attestations and on-chain identity so buyers can carry trust across venues.

Aspirational: not yet enforced. Promotion path: ROADMAP Phase 4.3 (ERC-8004
registration) and 5.1 (signed attestations).

### A17 — Dispute path (L0)

Disputes should have a resolution path beyond independent hash verification.

Aspirational: not yet enforced. Promotion path: ROADMAP Phase 5 (reputation
and counterparty checks).

### A18 — Registry liveness honesty (L0)

Registry listings should reflect liveness: register on boot, deregister on shutdown.

Aspirational: not yet enforced. Promotion path: ROADMAP Phase 4.1 (registry
publication).

---

## Known gaps

Deviations between what an article claims and what the code does today. An
open gap must name a witness test that pins the current weak behaviour, so
fixing the code forces this register to be updated.

### G1 — Local simulator payment check was weaker than the HTTP path (closed, article A14)

`veritas/autonomous/local_facilitator.py` `verify_payment()` accepted any
non-empty payment header, and `control_plane.agent_research()` hardcoded the
$0.25 price instead of reading payment config.

Closed in constitution 1.1: the simulator now decodes headers via the shared
`veritas.x402.decode_payment_header` and requires the x402 structural shape,
and the control plane's recorded amounts follow payment config (both enforced
in `tests/test_autonomous_payment.py`). The remaining weakness is registered
as G2 — the register does not shrink by forgetting.

### G2 — Local simulator does not verify signatures (open, article A14)

The local simulator validates payment structure and configuration, not
signatures: a structurally valid payload with a forged signature passes. The
HTTP path's facilitator verification remains the strong gate, and the control
plane must not be exposed as a paid network surface while this gap is open.

Witness: `tests/test_autonomous_payment.py::test_known_gap_simulator_does_not_verify_signatures`.
If that test fails, the gap has been fixed — close G2 and delete the witness.

### G3 — Relevance gate absent from the served path (closed, article A2)

The gate was enforced only inside `StaticCorpusRetriever`, so on the served path
any source of 40 or more characters produced a billable `completed` answer
however unrelated to the query — and the evaluation harness certified a filter
production never applied.

Closed in constitution 2.0: the gate runs in the pipeline evidence loop and an
all-irrelevant result is an `irrelevant_evidence` refusal.

### G4 — Falsified provenance in the keyless tier (closed, article A23)

The keyless tier called a metasearch library that shuffles across Google, Bing,
Yandex, Brave and others, then labelled every result `duckduckgo`.

Closed in constitution 2.0: the dependency is removed and each provider is named
as the engine actually queried.

### G5 — Custody chain never delivered (closed, article A12)

Only the root hash and a self-asserted `custody_valid` were published, so a buyer
had nothing to check and A12 was false as written.

Closed in constitution 2.0: the chain ships in the response and the buyer re-runs
`verify_chain_records` over delivered data.

### G6 — A paid request is not idempotent (closed, article A13)

The nonce was burned before the work, so a buyer whose connection dropped after
settlement was charged and received nothing: retrying the same authorization
returned 409 rather than the deliverable already paid for.

Closed in constitution 2.1: `veritas/ledger.py` records the delivery before
settlement is attempted and keys a state machine on the authorization nonce, so
resubmitting it returns the stored deliverable and the retrieval pass still runs
exactly once. Bounded: single-instance scope — two instances behind a balancer
do not share the ledger, so a replay routed to the other one still fails; and a
settlement whose facilitator never answers stays indeterminate until
reconciliation, which G9 tracks.

### G7 — The trust score is movable with free traffic (closed, article A11)

`/v1/trust` derived from an outcome log that recorded every request including
unpaid ones, and the endpoint is unauthenticated, so anyone could move the
service's own reputation signal at no cost.

Closed in constitution 2.2: only paid requests are scored. Free outcomes are
still counted and reported in the basis but cannot manufacture a reputation,
and an instance nobody has paid reports UNPROVEN — the correct answer. This
closes the manipulation route only; the score is still self-reported, which
is G10.

### G10 — The trust score is self-reported (open, article A11)

The score is computed by the graded party from its own records. Nothing
external attests to it, and a seller that simply logged favourable outcomes
would produce an identical document. Restricting scoring to paid traffic (G7)
raises the cost of manipulation; it does not make the number verifiable by the
buyer relying on it.

Witness: `tests/test_known_gaps.py::test_known_gap_the_trust_score_is_self_reported`.

### G11 — Survival reports are bounded by what auditors share (open, article A26)

A survival report summarises the audit records provided to it, and nothing
forces an unfavourable record into that set: whoever assembles the records can
withhold divergence they observed. Divergence counts are therefore a floor,
never a ceiling, and a clean report from a curated set is not proof of a clean
history. Removing this requires auditor-side publication the seller cannot
filter (the Merkle/anchor axis named in later N1 work).

Witness: `tests/test_known_gaps.py::test_known_gap_survival_reports_are_bounded_by_what_auditors_share`.

### G8 — No financial ledger (closed, article A13)

The settlement result, including the on-chain transaction hash, was returned in a
response header and then discarded. An operator could not say how much was earned,
from whom, or for what, and no settlement could be reconciled.

Closed in constitution 2.1: `veritas/ledger.py` durably records every
authorization, delivery and settlement attempt, and revenue is answerable from
the ledger alone. Bounded: it records what this instance did, which is not proof
the chain agrees — see G9.

### G9 — Recorded settlements are never checked against the chain (open, article A13)

The ledger stores what the facilitator told us, including `indeterminate` entries
where it told us nothing, and no code re-checks any of it against an RPC
endpoint. An operator can say what this instance believes it earned, not what it
actually holds.

Witness: `tests/test_known_gaps.py::test_known_gap_settlements_are_never_checked_against_the_chain`.

---

## Adopting this pattern

Any seller service in the venue can publish a constitution in this shape.
The pattern is three commitments, none of which requires this codebase:

1. **Articles are data.** Publish a versioned, machine-readable document of
   `{id, statement, evidence_level, enforcement}` at a stable unpaid
   endpoint, and reference it from your identity document.
2. **Enforced or admitted.** Every article either points at an artifact that
   fails when the norm is broken, or is marked aspirational. A meta-test
   checks the pointers resolve.
3. **Gaps are registered, with teeth.** Known deviations get an id, an
   article reference, and a witness test that pins the current behaviour, so
   the register cannot silently rot.

A buyer agent evaluating any seller can then do what it does here: fetch the
constitution, check the enforcement pointers against the seller's published
test suite and CI configuration, and weigh aspirational articles at exactly
zero until promoted.
