# The Veritas Venue Constitution

A venue constitution is the set of norms a service commits to toward every
other participant in its venue — buyer agents, peer seller services,
facilitators, registries, and attesters — written so that a machine can read
it, cite it, and check it.

**The normative source is `veritas/constitution.py`, version 1.1.** This file
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

### A11 — Reputation is not self-attested (L1)

Trust is derived from recorded behaviour only, and below the sample floor the service reports UNPROVEN rather than a manufactured score.

Enforced by `tests/test_api.py::test_trust_is_unproven_without_data`.

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
