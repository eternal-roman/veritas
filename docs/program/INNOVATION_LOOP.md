# Agent Commerce Innovation Loop

A recursive build system for Veritas: stock the work honestly, ship one
autonomy-raising increment, prove it, learn, re-goal, and run again.

This is not a second roadmap. It is a **governing loop** (goals + scorecard +
cycle atom) and the **execution engine** that consumes `docs/program/STATE.md`,
`ROADMAP.md`, `ECOSYSTEM.md`, and the live tree, and emits PRs until the venue
is worth joining.

**Plane authority:** [`GOVERNING.md`](GOVERNING.md) elevates this loop (and
STATE NEXT) above agent chatter. [`GUARDIAN.md`](GUARDIAN.md) forbids failing
or fake code. The **Overseer** is the quality/vision/strategy gate; builders
ship only what is functioning, necessary, and pursuant to the north star.

---

## North star (L0 aspiration — never claim as proven)

The single full statement is [`VISION.md`](../../VISION.md) §1; this loop
consumes it, it does not restate it (MIND §5 — this section was one of four
diverging copies, one still saying "hub" while GUARDIAN names "hub ready" a
gate-failure phrase). What this loop adds: **cycles that grow the
substrate's public surface outrank cycles that polish the demo**
(`fable/REFOUNDING.md`). `skills/adversarial-code-truth.md` remains a locked
gate on every claim.

---

## What already makes Veritas excellent (pride, with evidence)

Hold these. Improve around them. Do not dilute them for speed.

| Strength | Why it matters for agent commerce | Evidence |
|----------|-----------------------------------|----------|
| Outcome taxonomy | Agents can refuse to pay for *our* failure | `unavailable` non-billable; harness + payment tests |
| One engine | No demo/production split to drift | `pipeline.run_research` only; packaging tests |
| Money path ordering | Buyer never charged for undeliverable work | ledger claim → deliver (fsync) → settle |
| Constitution L0/L1 discipline | Norms are enforceable or admitted aspirational | `veritas/constitution.py` + sync tests |
| Buyer payment gate | Policy before signature; L2 model on invariants | `payer.py` + `payment_model` (8,720 traces) |
| Dogfood that finds defects | Cycles 2–4 found real bugs and fixed them | `docs/dogfood/` |
| Self-provisioning | `veritas-agent up` removes setup friction | agent CLI + wallet tests |
| Honesty after audit | False claims were retracted, not papered over | STATUS.md, STATE.md |

## What still kills the product (honest landmass)

| Gap | Blocks |
|-----|--------|
| **Zero external buyers; zero public surface** (no deploy, no PyPI, no listing) | Any evidence of demand — the frontier (`fable/REFOUNDING.md` Stage 1). Settlement counts: STATE header; evidence `fable/settlement/` (a count restated here went stale within a day) |
| Snippet-grade retrieval / notary not built | Willingness to pay |
| Multi-instance prune still open | Scale beyond one process retention |
| Shared state across instances missing | Scale beyond one process |
| G9 reconcile not yet routine (run counts: STATE header) | "settled" at volume still means "facilitator said so" |

---

## Autonomy scorecard (what "better" means each cycle)

Score each axis **0–4** with evidence, never vibes. A cycle must raise at
least one axis by ≥1 *or* close a registered critical gap *or* produce a
measurable dogfood finding that changes the program.

| Axis | 0 | 2 | 4 |
|------|---|---|---|
| **A — Buy alone** | Human signs every payment | Offline policy + signer seam | Unattended testnet pay → 200 + verify |
| **B — Sell alone** | Human configures and restarts | `veritas-agent up` free mode | Paid serve + auto re-register + retention |
| **C — Money is real** | Fail-closed only | Testnet tx hash recorded | Mainnet + ledger↔chain reconcile (G9) |
| **D — Product worth** | Snippets / offline corpus | Full-text + honest provenance | Notary + graded quality table |
| **E — Found alone** | Must know the URL | Self-traversing well-known | Registry/Bazaar + ERC-8004 |
| **F — Lifecycle compounds** | Outcomes discarded | Trust + metering + ops CLI | Attestations + calibrator trained + routing |

Baseline (main @ program HEAD, 2026-08): see `docs/program/cycles/000-baseline.md`.

---

## One cycle (the atom)

```
STOCK → SCORE → SELECT → PLAN → BUILD → AUDIT → VERIFY → SHIP → LEARN → REFRAME
                                    ↑__________________________________|
```

| Phase | Inputs | Output | Fail closed means |
|-------|--------|--------|-------------------|
| **STOCK** | main, STATE, ROADMAP, ECOSYSTEM, dogfood, git log | inventory of excellence + gaps | Guessing without reading the tree |
| **SCORE** | inventory + scorecard | axis scores with evidence paths | Inflating scores without tests |
| **SELECT** | scores + STATE NEXT ACTION + vision | single bet + why-now + non-goals | Multi-feature laundry lists |
| **PLAN** | selected bet | step plan, tests first, risk | Spec without acceptance criteria |
| **BUILD** | plan | branch + code + tests | Untested behaviour claims |
| **AUDIT** | diff | adversarial findings; must fix blockers | Cheerleading the author's work |
| **VERIFY** | suite + harness + ruff | green local battery | Soft-fail / `|| true` |
| **SHIP** | green branch | PR; merge only when CI green | Merge with red CI or no audit |
| **LEARN** | PR + dogfood + scorecard delta | cycle report in `docs/program/cycles/` | Shipping without updating STATE |
| **REFRAME** | learnings + vision | next NEXT ACTION (may deviate) | Blind obedience to a stale ladder |

### Selection rules (how innovation stays honest)

1. **Program ladder wins by default.** If `STATE.md` NEXT ACTION is unblocked
   and load-bearing, take it.
2. **Deviate only with a written bet.** A cycle may leave the ladder when:
   - a dogfood or audit finding is more severe than the NEXT ACTION, or
   - an axis is stuck at 0 while lower-cost work can raise it, or
   - a new path better serves independence/commerce/lifecycle *and* names
     what it postpones.
3. **One shippable bet per cycle.** Prefer the smallest change that raises an
   axis or closes a critical gap.
4. **Never invent a parallel product.** One engine. One buyer payment path.
   One wire contract discipline.
5. **Human residues stay human — but ship with the prepared 90%.** Mainnet
   money, PyPI account, TLS/public DNS, and any change weakening an L1
   article remain human calls. Everything up to those minutes is agent work
   (MIND §3 rung 6): config written, workflows ready to fire, verification
   documented. Testnet funding is **not** a human residue (permissionless
   faucet — proven, `fable/settlement/`), and "blocked on human" without a
   ladder transcript is a gate failure.

### Ship rules

- Branch from current `main` (or stack on a green PR when intentionally stacked).
- PR description is 4C: comprehensive, concise, consistent, clean — and states
  PROPERTY / EVIDENCE LEVEL / NOT PROVEN.
- Merge only when CI is green on the head SHA.
- Update `docs/program/STATE.md` NEXT ACTION in the same PR or the immediate
  follow-up cycle (never leave the resume point lying).

---

## Continuous operation

### Mode A — Manual / session-driven (default)

```text
/workflow agent-commerce-flywheel
# or with args:
/workflow agent-commerce-flywheel {"max_cycles": 1, "auto_merge": false}
```

Each run performs one full cycle (or `max_cycles` if budget allows), writes a
cycle report, and stops. Humans re-invoke when ready.

### Mode B — Scheduled re-fire (true continuous)

See `docs/program/CONTINUOUS.md`, `GUARDIAN.md`, and **`AUTONOMOUS.md`**. Production
cadence is **25 minutes** (backup builder; Conductor also kicks at 15m), durable
scheduler, tick text in `FLYWHEEL_TICK_PROMPT.md`. Default **auto-merge on green
CI** — no human-in-the-loop workflow gates.

Between fires: skip if WIP clash or CI pending; continue the same bet rather
than inventing a parallel branch. A tick that cannot run the full battery is
a noop, not a doc rewrite.

### Mode C — Multi-cycle burst (session budget)

```text
args: { "max_cycles": 3, "auto_merge": false }
```

Runs up to N cycles in one session, pausing for user confirmation between
merges. Stops early on: red CI, audit blocker, no-progress (two cycles with
no axis movement and no gap closed), or agent budget exhaustion.

---

## Cycle ledger

Every completed cycle writes:

```text
docs/program/cycles/NNN-<slug>.md
```

Required sections: scores before/after, bet selected, deviation (if any),
evidence, PR link, what still kills the product, proposed next bet.

`docs/program/cycles/000-baseline.md` is the stock photo of main before the
loop began. Later cycles must cite it when claiming progress.

---

## Anti-patterns (reject these in AUDIT)

- Building Phase N product surface on unpaid money-path defects.
- Second retrieval or payment path "just for agents".
- Claiming on-chain success from local facilitator green.
- Score inflation ("we're basically ready") without scorecard movement.
- Infinite planning without a PR.
- Scope that cannot ship in one cycle — split and re-select.
- Invented stock/select defaults when agents fail (stop instead).
- Soft-fail battery ("if feasible", skip ruff, assumed green).
- Audit fail-open (default ship without explicit panel approval).
- Collapsing 410 Gone into 404 after retention prune.

Full anti-handwave charter: **`docs/program/GUARDIAN.md`**.

---

## How this compounds into a hub

From `ECOSYSTEM.md`, the growth loops are still mostly L0. This innovation
loop's job is to promote them, one L1 gate at a time:

```
serve honestly → durable outcomes → trust signal → discovery ranking
       ↑                                              |
       └──────── richer product ← paid demand ←───────┘
```

Agent independence is the on-ramp; product worth is the retention; money that
settles and reconciles is the trust floor; lifecycle signals are the network
effect. The loop does not skip the floor to decorate the network effect.

---

## Invocation contract for agents

When an agent is told to "run the innovation loop" or "continue the flywheel":

1. Read this file, `STATE.md`, and the latest cycle report.
2. Run battery green before building.
3. Execute one cycle end-to-end.
4. Leave the tree with an updated resume point.
5. State PROPERTY / EVIDENCE LEVEL / NOT PROVEN before any success claim.

If you only produce a plan, the cycle did not complete.
