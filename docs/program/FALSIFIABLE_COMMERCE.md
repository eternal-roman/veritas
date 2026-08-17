# Falsifiable Commerce — the methodology that makes Veritas an ecosystem

> **ATTENTION — AGENTS WORKING IN THIS REPOSITORY**
> This document is the load-bearing methodology for the venue's economic
> layer, derived on `fable/survival-records` and maintained with the code.
> Read it together with `docs/program/FABLE_INSIGHTS.md` before touching
> warranties, challenges, pricing, reputation, or Phase 5+ work. The mandate
> that produced it is recorded in §0 so its intent survives handoff. Nothing
> below claims more than its evidence carries (`skills/adversarial-code-truth.md`);
> §8 states exactly what is implemented versus proposed.

## 0. Mandate (recorded verbatim intent, 2026-08-08)

Continuing goal: carry the survival-records result toward building an
agent-to-agent autonomous commerce ecosystem. Rethink from first principles —
through novel innovation — a methodology that transitions Veritas from a cool
idea to an ecosystem evolution for agent-to-agent commerce. Do not lead on
already-solved problems; arrive at a methodology that does not currently
exist in the agent-to-agent commerce space. Commit all learnings and this
mandate to documentation other agents can see. Continue until the goal is
objectively achieved (§9 defines the objective criteria this branch commits
to).

## 1. What is already solved — and therefore not led on

Machine-native payment exists (x402: 402-challenge → sign → verify → settle).
Discovery exists (registries, `/.well-known/x402`). Custody and transport
integrity exist (this repo: hash chains, notarized observation, delivered
verifiability). Retrospective reputation now exists here too (survival
records: standing computed by the record holder from third-party-signed
audits). Budgets, diligence, spend policies, self-provisioning: solved in
this repo. Identity rails (ERC-8004 etc.) are being solved elsewhere.

None of that produces an economy. It produces **pipes**.

## 2. The unsolved problem, stated from first principles

Strip commerce to its irreducible requirements: money, delivery, and a way
for a buyer to act on quality it cannot yet see. For information goods the
third requirement is structurally hard — Arrow's information paradox: the
buyer cannot evaluate the good without consuming it, and having consumed it,
has no reason to pay. Human markets patch this with brands, refunds, courts,
review sites — all human-speed, all uneconomic at $0.005 per query.

Every current agent-commerce design handles this one of three ways:

1. **Verification as arithmetic** — hashes, custody, re-fetch. Proves the
   bytes are the bytes. Says nothing about whether the answer is any good.
2. **Verification as altruism** — audits, reviews, attestations. Public
   goods. Public goods are underprovided at equilibrium; nobody's job is to
   check, so mostly nobody checks. (Survival records made audits *possible*
   and *portable*; they did not make anyone *want* to audit. G11 registered
   the omission half of this.)
3. **Verification as escalation** — optimistic oracles, juries, courts.
   Bonded assertions with challenge windows exist (UMA's optimistic oracle);
   they terminate in human or tokenholder voting, which neither operates at
   machine speed nor prices per-transaction service quality.

So the actual frontier of agent-to-agent commerce is not payments, identity,
or provenance. It is this: **verification has no economics.** In every
existing design, checking a counterparty's work is a cost center — free,
charitable, or escalated to humans. An ecosystem needs verification to be a
**profitable niche**, the way evolution builds it: stable ecologies do not
run on pairwise goodwill, they run on policing as a specialization —
cleaner fish, immune systems, predators of cheaters. Markets that work do
the same: the short seller is *paid* to find the fraud.

## 3. The methodology: falsifiable commerce

One sentence: **every claim sold carries, inside the deliverable, the
executable experiment that would refute it, a bonded stake behind that
experiment, and a challenge window — so that hunting bad answers is a
paid occupation, honesty is the cheapest strategy, and disputes terminate
in deterministic re-execution rather than in anyone's judgment.**

The Popperian inversion is the core novelty: the seller does not certify
that it is right. **The seller authors the procedure by which it may be
proven wrong**, and prices its own confidence by staking on it. A claim
that ships without a falsification procedure is, by construction, a
different — cheaper — grade of good, and is labeled as such.

### 3.1 The warranty

A deliverable's warranty is machine-readable metadata bound into the signed
response:

- `predicate`: a falsification predicate from a **registered, versioned
  predicate registry** — executable, deterministic, total. Not prose. The
  predicate's inputs are the delivered bytes plus, at most, re-observation
  through the same notary engine every party can run.
- `bond`: the stake the seller forfeits if the predicate fires within the
  window. The bond is a *price signal of self-assessed confidence* — a
  credible signal precisely because it is costly (the lemons problem's
  classical resolution, mechanized per-transaction).
- `window`: the challenge period.
- `falsifiability_class`: see §3.3 — the honest boundary of what the
  warranty can promise.

### 3.2 The challenge

Anyone — buyer, competitor, dedicated verifier agent — may challenge within
the window by staking `challenge_stake` and submitting the predicate's
required evidence. Evaluation is a **pure function**: both parties (and any
third party) compute `predicate(deliverable, evidence) → fired | not_fired`
and get the same answer. Predicate fires → challenger receives the bond
(minus a venue cut); predicate does not fire → the challenger's stake goes
to the seller. No arbiter, no vote, no reputation weighing, no human. This
is the property that makes it viable at machine speed and sub-dollar
prices: the dispute *is* a computation.

The equilibrium this buys: verifier agents profit exactly in proportion to
the dishonesty available to find. An honest venue starves its own
predators, which is the desired steady state — the cost of the system
falls toward zero as it succeeds, unlike audit/compliance regimes whose
cost is constant regardless of honesty.

### 3.3 Falsifiability classes — the epistemic tiering of goods

Not every true claim is refutable by a decidable procedure, and pretending
otherwise would rebuild dishonesty one layer up. Every deliverable
therefore carries a class, and the class is priced:

| Class | Refutation decidable by | Warrantable | Status here |
|-------|--------------------------|-------------|-------------|
| D0 | The delivered bytes alone (custody chain broken, cited hash absent from delivered evidence, forged attestation, status/evidence contradiction) | Yes | **Implemented** (`veritas/warranty.py`) |
| D1 | One re-observation through the notary engine, restricted to time-invariant commitments (an attested record that was never validly signed; a pack whose own arithmetic fails) | Yes | Partially implemented (attestation/pack checks are D0-shaped once delivered); origin-divergence is **excluded by design** — pages change; the P7 boundary means "the origin differs now" must never forfeit a bond |
| D2 | A pinned, versioned model run (entailment of a synthesized claim by its cited passage) | Yes, once the model is pinned and its run is reproducible | Not implemented; the honest gate for ROADMAP 1.3 — synthesis should ship **only** as warranted-D2 or labeled-U |
| U | Nothing decidable | **No — and saying so is the product** | Implemented as a label |

The refusal taxonomy (`completed` / `refused` / `unavailable`) was the
epistemically honest *status* layer; falsifiability classes are the same
honesty applied to the *economic* layer. A service that marks a claim `U`
is saying "I will not pretend this is refutable" — the exact move that made
`unavailable` ≠ `no_evidence` the product. Buyers pay more for D-class
claims than U-class claims, and the price gap is the market's measurement
of epistemic quality — a measurement no current agent-commerce protocol
provides at all.

### 3.4 Closing the reputation loop — forfeits are unomittable

Survival records left one structural asymmetry, registered as G11: whoever
assembles audit records can omit the unfavourable ones. Falsifiable
commerce closes it: a forfeited bond is a **settlement event on payment
rails**, not a record in someone's curated set. Negative reputation stops
being a document a seller can suppress and becomes a money movement the
seller itself signed. The reputation hierarchy, strongest evidence first:

1. **Forfeited bond** — self-authenticating, unomittable once settled on-chain
2. **Survived challenge** — an adversary paid to refute and failed
3. **Survival-record audit** (`confirmed`/`diverged` per distinct auditor)
4. **Expired unchallenged warranty** — weak: silence, not scrutiny
5. **Self-reported trust** (`/v1/trust`) — floor of the hierarchy, G10, says so itself

Note what this hierarchy does to the sybil bound stated in
FABLE_INSIGHTS §6: fake *positive* history now has a hard cost (a seller
self-challenging to farm "survived challenges" burns the venue cut every
time), and *negative* history cannot be laundered at any cost.

## 4. Why this is not something that already exists

Checked against the adjacent designs rather than asserted
(sweep 2026-08-08; see also the liability gap named publicly in x402
analyses — the space discusses agent-commerce liability as unsolved):

- **UMA-style optimistic oracles**: bonded assertion + challenge window,
  but resolution escalates to tokenholder voting (a human quorum), targets
  oracle facts rather than per-deliverable service quality, and has no
  falsifiability taxonomy — everything is assumed assertable. Here,
  resolution is a pure function and *what cannot be decided is labeled and
  priced as such*.
- **PoS slashing / rollup fraud proofs / opML**: deterministic refutation
  exists there, but the refutable statements are protocol-defined (state
  transitions, computation traces), identical for every participant.
  Here the seller **authors its own refutation experiment per deliverable**
  — the unit of falsifiability is the individual good, and authoring it is
  the act that prices the good.
- **Web2 SLAs / marketplace warranties**: human-enforced, court-backed,
  batch-granularity. Not machine-decidable, not per-claim, not composable
  by agents.
- **Prediction markets**: price claims, but are venues *about* claims, not
  claims bundled *into delivered goods* with the seller as the bonded
  counterparty.

The composition — seller-authored decidable refutation per good, bonded,
window-scoped, deterministic termination, epistemic tiering as market
metadata, forfeits as unomittable reputation — does not, to the best of a
verified sweep, exist in the agent-to-agent commerce space. That sentence
is an L2-style claim about absence and is held accordingly: absence of
evidence of prior art, checked, not proof.

## 5. Why an ecosystem follows, not just a feature

- **Quality discrimination without consumption** (the Arrow paradox
  exit): the bond size and falsifiability class are visible *before*
  purchase; a buyer discriminates on the seller's own priced confidence,
  not on consumed goods or prior reputation alone. New entrants without
  history can buy credibility with bond size — reputation stops being an
  incumbency moat, which is what makes the venue *evolvable*.
- **A native second species**: verifier agents — the first economic role
  in agent commerce that exists *because* other agents transact. A
  protocol with predators is an ecology; a protocol without them is a
  billing system.
- **Honest pricing of the unknowable**: the D/U price gap creates the
  first market measurement of epistemic quality; services compete on how
  much of their output they dare make refutable — competition on
  falsifiability is competition on truthfulness, mechanized.
- **Sequencing inversion for this repo**: ROADMAP 1.3 (claim synthesis)
  is currently gated on an entailment threshold measured on a benchmark.
  Under this methodology it gates on *warrantability*: synthesis ships
  when it can ship as D2-warranted or honestly U-labeled. Quality gates
  move from "we measured 95% once" to "we stake on every instance."

## 6. Honesty boundaries of the methodology itself

- Deterministic predicates cover a **subset** of quality. "Technically
  unfalsified yet useless" answers survive unwarranted on dimensions the
  predicate does not bind; the U-class label is load-bearing, and buyers
  must treat bond size as confidence *about the predicate*, nothing more.
- Predicate authorship is adversarial: sellers will author weak predicates.
  The counter-force is the market (a weak predicate is visible metadata —
  a competitor's stronger predicate at equal price wins the buyer), not a
  central reviewer. Whether that force suffices is an open empirical
  question and is stated as such.
- Bond settlement requires the payment rail this repo has not yet proven
  on mainnet (operator-run testnet only). Constitution 2.8 closes G12 at
  the library/HTTP layer: an EIP-3009 authorization is the lock
  (`veritas.escrow`); `settle_forfeit` claims the lock (`locked` →
  `settling`) then submits it through the existing facilitator after a
  fired challenge. Two collects cannot both submit. A facilitator
  refusal reverts to `locked`. Warranties that omit a lock stay
  `signed_commitment_not_escrow`. Not a deployed vault. Local facilitator
  still G2. Mainnet collect is unproven.
- Collusion between a seller and friendly challengers can farm "survived
  challenges" at the cost of the venue cut; the cut parameterization that
  makes this uneconomic is future calibration work, stated, not solved.

## 7. Deployment path (dependency-ordered)

- **W0 — this branch.** Warranty schema, D0 predicate registry,
  deterministic challenge evaluation, warranty outcome records feeding the
  reputation hierarchy, falsifiability-class labels on responses.
  Constitution: enforce-or-admit (A27 L1; G12 closed in 2.8).
- **W1 — escrowed bonds over x402 rails.** VCAE: the EIP-3009
  authorization *is* the lock (Lightning/HTLC timeout + x402 exact).
  `settle_forfeit` claims then submits; that is a settlement event. Implemented in
  `veritas/escrow.py`. Mainnet collect unproven; G2 still open.
- **W2 — with ROADMAP 1.1/1.3.** D2 predicates: pinned-model entailment
  warranties on synthesized claims; synthesis ships only warranted-or-
  labeled.
- **W3 — venue growth.** Standalone verifier agents (the vendored-verifier
  precedent, applied to challenge hunting); registry advertising of
  warranty terms alongside price in the 402 challenge; cut calibration
  against collusion economics.

## 8. What is implemented on this branch versus proposed

Implemented and tested (L1, `tests/test_warranty.py`): warranty
construction and EIP-191 seller signature over canonical warranty terms;
the D0 predicate registry (custody-chain validity, citation presence,
attestation recovery, status/evidence coherence) as pure functions;
deterministic challenge evaluation returning `fired` / `not_fired` /
`undecidable` with stable reasons; outcome records; `warranty_report`
counts in the survival-record tradition; falsifiability-class labeling
with U-class refusing warranty construction. Also implemented
(`veritas/standing.py`, `tests/test_standing.py`): the §3.4 evidence
hierarchy composed into one recomputable standing document — forfeits
dominate, one warranty counts once, survived challenges upgrade the audit
verdict, the self-report is carried only as the labeled floor. Escrow
(`veritas/escrow.py`, `tests/test_escrow.py`): EIP-3009 lock, settle_forfeit
submits through the facilitator, commitment-only warranties stay labeled.
Proposed, not implemented: D2 predicates, venue-cut calibration, registry
advertisement of warranty terms, mainnet collect.

## 9. Objective completion criteria for the mandate (§0)

1. Methodology derived from first principles, differentiated against
   checked prior art, recorded here with the mandate — **done**.
2. Core mechanism implemented, not vaporware: D0 warranties + challenges
   decidable end-to-end by any party, tested — **done** (`veritas/warranty.py`).
3. Every claim registered under the repo's enforce-or-admit discipline
   (constitution 2.4: A27, G12 witnessed) — **done**.
4. Full suite green, lint clean, committed to `fable/survival-records` —
   **done at commit time**.
5. Live-market validation (bonds escrowed, real challenges, cut
   calibration) — **not achievable from this environment** and stated so;
   tracked by W1–W3 above. Objectivity here means the boundary is written
   down, not that the boundary does not exist.

---
*Maintained on `fable/survival-records` with `veritas/warranty.py` and
`docs/program/FABLE_INSIGHTS.md`. Update all three together.*
