# Veritas Vision — the single north-star statement

**Status: L0 direction — never claim proven.** This document binds every
agent and worker in this repository: program docs point here instead of
restating the north star (MIND §5), and nothing here overrides honesty law —
precedence stays GUARDIAN → MIND → GOVERNING loops → role cards
(`docs/program/GOVERNING.md` §0). Success-word claims without carried
evidence are gate failures under the locked gate
(`skills/adversarial-code-truth.md`); this file states direction, not
achievement.

## 1. North star

Build the substrate for a multi-billion-dollar agent-to-agent commerce
business with scalable momentum. Three pillars, in dependency order:

1. **Agent independence** — agents buy and sell without a human on the
   per-request path.
2. **Hyper-scalable commerce** — payment, delivery, ledger, and operations
   that hold under load, replay, and multiple instances.
3. **Product lifecycle enrichment** — every outcome improves trust,
   discovery, and the next agent's decision.

The dollar figure is direction, not a metric. Only measured numbers ship —
tests, dogfood transcripts, settlement hashes, request volume — and every
count lives at its evidence, never restated here.

## 2. Identity — by pointer

Who we are is defined once, in `docs/program/MIND.md` §1: the product is
**trust a stranger's agent can verify without trusting us** — receipts,
custody, settlement, reconciliation, diligence, standing. The research
payload is the first demonstration, not the product.

## 3. Strategy — by pointer

- **Staged falsifiable path** (Stage 0 rails → Stage 1 public existence →
  Stage 2 substrate-as-product → Stage 3 the venue), each stage carrying the
  falsifier that kills it: `docs/program/fable/REFOUNDING.md` §4.
- **Kill criteria** — the conditions under which this vision is wrong:
  REFOUNDING §5.
- **Current posture** — existence-first with a D0 wedge:
  `docs/program/ecosystem/STRATEGY_EVAL_AND_PLAN.md`.

## 4. The three interfaces

**Human → agent (operator).** Operator work is minutes, not projects: Stage-1
(PyPI trusted publisher, public TLS host, mainnet pay-to) lives in
`docs/program/STATE.md` NEXT with the agent-executable 90% already prepared
(MIND §3, rung 6). `veritas-agent enroll` / `up` is the local adopt path.
Still needs: those minutes spent.

**Agent → human (evidence).** An agent reports upward in artifacts a human
can check without trusting the agent: custody receipts, settlement JSON with
transaction hashes, dated probes, PROPERTY blocks. Evidence-directory
convention: `docs/program/fable/settlement/` and peers. Still needs: nothing
structural; the register is law.

**Agent → agent (the product).** A stranger's agent integrates by traversal,
not by reading prose: `/.well-known/x402` → `links` → `/v1/identity`,
`/v1/hooks` (every surface: HTTP, MCP tools, CLI exit-code contracts,
payment/session headers, signal stores, and the stated absence of push),
`/v1/constitution` (norms with enforcement pointers), `/v1/schema` +
`/v1/errors` (the contract), then paid work over x402 with receipts and
`/v1/verify`. Local tooling: `veritas-mcp` over stdio. Still needs: a public
host anyone can traverse to.

## 5. Roadblock ledger

First-principles resolutions to what blocks a commerce substrate. "Exists"
means shipped and tested in this repository; "L0 next" is direction.

| Roadblock | First-principles resolution | Exists today (evidence) | L0 next |
|---|---|---|---|
| Agent onboarding | Self-traversing discovery + zero-account payment: no signup, no API key, no human — find, verify, pay per request | discovery chain + hooks registry (`tests/test_discovery.py`, `tests/test_hooks.py`); 402→pay→deliver (`tests/test_money_path.py`) | registry listings; ERC-8004 identity (A16) |
| Money ingress | Per-request x402 (EIP-3009: the buyer needs no gas) or prepaid credits over SIWx sessions | settlement recipe + evidence in `docs/program/fable/settlement/`; credits (`tests/test_credits_api.py`) | mainnet (explicit env + human-owned pay-to only); unsolicited buyers |
| Money egress | Operator-held keys; the service never custodies buyer funds; ledger→chain reconcile is report-only and independent | `veritas-ops reconcile-chain` (gap G9's witness); `veritas-money-loop` | routine production reconcile (closes G9) |
| Human onboarding | One command to a serving instance; an honesty register instead of marketing | `veritas-agent enroll` / `up`; README "Known limitations" | hosted instance; PyPI wheel |
| Business incorporation | Legal-identity claims a counterparty can verify, not assert | nothing yet — `TRACK_LEGAL_IDENTITY` exploration only | entity, terms, compliance (human-rung work) |
| Trust cold-start | Never fake standing: `/v1/trust` reports UNPROVEN below 10 paid outcomes; falsifiable warranties substitute for reputation at n=0 — the seller stakes on a refutation experiment instead of asking for belief | UNPROVEN rule (`tests/test_api.py`); warranty/audit/standing A26/A27 (`tests/test_warranty.py`, `tests/test_audit.py`) | portable attestations (A16); dispute path (A17) |
| Integration friction | One machine-readable registry of every surface including what does **not** exist (no push) — absence stated beats absence inferred | `/v1/hooks` + A28 sync tests (`tests/test_hooks.py`) | SDKs; framework adapters |

## 6. Structural draw — why agents come, why scale compounds

An agent picks counterparties by expected value it can verify. Veritas is
built so verification artifacts — receipts, custody chains, survival
records, standing — are produced by the transaction itself and survive us.
Three compounding loops follow (mechanics in `ECOSYSTEM.md`; none yet
observed to compound — making them observable is Stage 1's job):

- **Evidence compounds.** Every exchange adds audit-grade records; standing
  is computed from third-party-signed records, never self-report (A26).
- **Verification gets cheaper with volume** while standing data appreciates —
  the unit economics of a substrate, not of a seller (REFOUNDING §3: the
  Stripe / Visa / Let's Encrypt shape).
- **Honesty is priced in.** Refusal and unavailability cost us less than
  lying would (the billable rules), so the incentive gradient points at
  truth even under load.

## 7. Revenue streams — L0 hypotheses with falsifiers

| Hypothesis | Falsifier |
|---|---|
| Per-request x402 fees for evidence-grounded work | no unsolicited paid request within REFOUNDING's Stage-1 window |
| Prepaid credit balances (session commerce) | buyers refuse prepayment to an UNPROVEN counterparty |
| Notarization fees (observe-once evidence) | no demand distinct from research |
| Warranty premiums (falsifiable commerce) | warranties do not move price (Stage-2 falsifier) |
| Standing / attestation rent (venue) | challenge volume ≈ 0 at equilibrium (Stage-3 falsifier) |

No projections. The kill criteria for the whole ambition are REFOUNDING §5.

## 8. The continuous improvement loop

Already owned; this section names it, it does not invent it:

1. **Merge** — green PR lands (Conductor; owner automation backs it).
2. **Measure** — `veritas-ops` (revenue, owed, reconcile-chain, Stage-1
   existence), `veritas-money-loop`, `/v1/trust`,
   `python -m veritas.evaluations.product_worth`,
   `python -m veritas.unblock_probe`.
3. **Judge** — Overseer names the next singular bet
   (`ecosystem/OVERSEER_CONFERRAL.md`); default hold beats invented work.
4. **Build** — Flywheel/Implementers ship it (`INNOVATION_LOOP.md`);
   Guardian/Pruner gate it.
5. **Learn** — `docs/program/cycles/` records what shipped; every 5 product
   cycles Optimizer adjusts the org, Overseer vetoes thrash.

Role cards must agree with `ORG_LOOPS.md`. Facts live at evidence (MIND §5).
The only human rung is unblock-ladder 6.

## 9. What this document is not

Not evidence, and not a claim of demand, revenue, or readiness. Every
measured number lives at its evidence (settlement counts:
`docs/program/STATE.md` header and `docs/program/fable/settlement/`); this
file deliberately carries none, so it cannot rot.

---

```
PROPERTY: single north-star statement + roadblock ledger, pointer-based (MIND §5)
EVIDENCE LEVEL: L0 (direction) with L1 pointers to cited artifacts
NOT PROVEN: demand, revenue, mainnet settlement, unsolicited buyers, any dollar figure
```
