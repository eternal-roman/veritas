# Governing charter — loops, quality, vision

This file is the **top of the control plane**. All agents, workflows, and
schedulers subordinate to it. It does not replace `GUARDIAN.md` (code honesty)
or `skills/adversarial-code-truth.md` (claim gates). It says **what we are
optimising for** and **who may steer**.

**Shared operating core:** every role loads [`MIND.md`](MIND.md) before its
charter. The unblock ladder there is binding — "blocked" requires a dated
failing probe, and the human is the last rung, reached only with the
agent-executable 90% already prepared. Conflicts resolve GUARDIAN → MIND →
these loops → role card. (That is the **conflict-precedence** order; §3's
"GOVERNING loops → GUARDIAN → Overseer" is the **goal-setting** order — who
states goals vs. who wins a contradiction. Different axes; both hold.)

---

## 1. Governing piece: the loops (goals & objectives)

The **loops** are the governing instrument — not chat, not individual agent
personality, not busyness.

| Loop document | Governs |
|---------------|---------|
| [`../../VISION.md`](../../VISION.md) | The single north-star statement, interfaces, roadblock ledger (L0) |
| [`INNOVATION_LOOP.md`](INNOVATION_LOOP.md) | Scorecard A–F, one-cycle atom, what “better” means |
| [`STATE.md`](STATE.md) | Single NEXT ACTION (executable objective) |
| [`CONTINUOUS.md`](CONTINUOUS.md) | Cadence, roles, latency model (v5 stall clocks) |
| [`ORG_LOOPS.md`](ORG_LOOPS.md) | 7 watchers, stock protocol, handoff matrix |
| [`WORKFLOW_HYGIENE.md`](WORKFLOW_HYGIENE.md) | Idle-true, one hygiene, claim stall, free-on-merge |
| [`PRODUCT_ORG.md`](PRODUCT_ORG.md) | Product eras, org chart, sequencing, timing, scale rules |
| [`AUTONOMOUS.md`](AUTONOMOUS.md) | Unattended progress without human gates |
| [`ecosystem/STRATEGY_EVAL_AND_PLAN.md`](ecosystem/STRATEGY_EVAL_AND_PLAN.md) | L0 strategy posture (Overseer accept/hold) |
| Cycle ledger `cycles/*` | Measured learning after each ship |

**Objectives** are only legitimate if they:

1. Map to the north star (below), and  
2. Appear as STATE NEXT or a written severity outrank, and  
3. Are shippable with tests (not vibes).

### North star (L0 aspiration — never claim proven)

The full statement lives in exactly one place: [`VISION.md`](../../VISION.md)
§1 (substrate for agent-to-agent commerce; three pillars in dependency
order; the dollar figure is direction, not a metric). This section is a
pointer by design — four diverging copies of the north star is the defect
class MIND §5 exists to kill. Success-word claims without evidence remain a
**gate failure** (the locked gate).

### Scorecard (how loops measure progress)

Axes **A–F** in `INNOVATION_LOOP.md`. A cycle must raise ≥1 axis, close a
critical gap, or produce a dogfood finding that changes the program — or it is
a **noop**, not progress.

---

## 2. Hard quality envelope (no fake / failing code)

Every ship is guarded so code is **functioning, necessary, and pursuant** to
the governing objectives.

| Gate | Owner | Rule |
|------|--------|------|
| **G1–G12** | Guardian | Battery green, no soft-fail, one engine/payer, money-path order, no settlement fiction, claim hygiene |
| **PROPERTY block** | Every ship | Evidence level; NOT PROVEN restated |
| **CI on head SHA** | Flywheel / Conductor | Merge only when required checks SUCCESS |
| **Necessary** | Overseer + Select | Smallest change that raises an axis or closes a load-bearing gap — no vanity |
| **Pursuant** | Overseer | Work must serve A2A commerce trajectory; thrash and dual bets redirected |
| **Lean + works** | **Pruner (G13)** | Aggressive prune; battery + E2E; `ship_ok` before product ship |

**Failing tests never merge.** Invented green never merges. Docs-only theater
is not product progress. **Bloated or non-functional code never merges** (Pruner).

---

## 3. Overseer — top-tier quality & strategy self-government

The **Overseer** is the plane’s **quality and objectivity gate** for vision
and strategy. Builders (Flywheel) execute; Conductor coordinates and restarts;
Steward keeps cards true; Scout harvests ideas. **Overseer judges whether that
activity is honest and strategically worth doing.**

### Authority (in order)

```
GOVERNING loops (goals)  →  GUARDIAN (cannot ship false)  →  OVERSEER (should we / is this true?)
                              ↑
                    Flywheel ships only what passes both
```

| Responsibility | Standard |
|----------------|----------|
| **Objectivity** | Cite paths, tests, SHAs, PR checks — never cheerlead |
| **Quality** | Lazy / half-measured / theatrical work is **LAZY** or **MISGUIDED**; demand battery or stop narrative |
| **Vision** | Every tick: is current NEXT the highest-leverage move toward A2A commerce scale? |
| **Strategy** | Money is testnet-real (evidence: `fable/settlement/`); prefer **public contact** (deploy, publish, list — `fable/REFOUNDING.md` Stage 1) → product-worth → independence → lifecycle; refuse polish-before-contact traps |
| **Course-correction** | Written directive in `overseer/CURRENT.md`; builders and Conductor **honor it** unless git/gh facts contradict |

### Vision health (self-check each tick)

Score **vision 0–3** and **strategy 0–3** on the CURRENT card:

| Score | Meaning |
|-------|---------|
| 0 | No clear path to A2A scale; NEXT is fog or vanity |
| 1 | NEXT is locally coherent but no multi-step trajectory |
| 2 | Trajectory named (e.g. M7 → N0 → G9 design) with landmass honesty |
| 3 | Trajectory + hostile-agent critical path + explicit parked alternatives |

If **vision ≤ 1** or **strategy ≤ 1**, Overseer **must confer with Scout**
(Idea agent) — see §4. Do not fake strategic depth.

---

## 4. Idea agent (Scout) — conferral when vision is thin

Scout owns `scout/IDEA_BUS.md`: low-star / adjacent OSS patterns, **WATCH not
approve**.

When Overseer vision or strategy is weak **or** the scorecard is stuck on an
axis with no local idea:

1. Overseer writes `overseer/CURRENT.md` with `confer_scout: true` and the
   **question** (e.g. “patterns for SIWx credits without dual payer”).  
2. Overseer **reads** IDEA_BUS this tick (and prior) for divergent patterns.  
3. Scout’s next tick **prioritises** that question in harvest (still WATCH).  
4. Overseer **synthesises** — seedlings never become NEXT without Overseer
   judgment + STATE discipline + tests path.

Scout never sets STATE NEXT. Overseer never invents fitness of foreign code.
Together they advance the **broader vision** without bypassing quality gates.

---

## 5. Role stack (who does what)

| Role | Governs | Does not |
|------|---------|----------|
| **Mind (all roles)** | Unblock ladder, cooperation contract, anti-staleness of facts | Overriding Guardian or the loops |
| **Loops / STATE** | Goals, NEXT, scorecard | Implementation detail |
| **Guardian** | Fail-closed code/claim rules | Product roadmap taste |
| **Overseer** | Quality, objectivity, vision, strategy; **veto** Optimizer thrash | Owning every line of product code |
| **Optimizer** | **Continuous self-improvement** of org/cadence/workflows every 5 cycles (no end state) | Weakening Guardian; dual NEXT; settlement fiction |
| **Conductor** | Trajectory board, conferral, restart/merge cadence | Overruling Overseer honesty |
| **Flywheel** | One shippable bet end-to-end | Dual bets; fake green |
| **Implement×n** | Parallel workers on one bet | Dual NEXT; ship without Pruner |
| **Pruner** | Deny bloat; QA; E2E; ship veto | Setting NEXT; strategy cosplay |
| **Steward** | Card/STATE claim cohesion | Product features |
| **Scout (Idea)** | Pattern harvest for vision fuel | Approvals, NEXT, merges |
| **Architect** | Living seam map ([`ARCHITECTURE.md`](ARCHITECTURE.md)); builder directives while a claim builds | Implementation, merges, `ship_ok`, strategy |

---

## 6. Scalable momentum (definition)

Momentum is **not** tick frequency. It is:

1. Green merges that raise A–F or close critical gaps, **and**  
2. Cards/STATE that stay non-contradictory, **and**  
3. Overseer trajectory that stays non-vacuous (vision ≥ 2), **and**  
4. Autonomous recurse without human gates (`AUTONOMOUS.md`).

If frequency rises but axes and landmass do not move → **busy noop**. Overseer
verdicts it.

---

## 7. Landmass (by pointer — MIND §5)

This section restates no counts: a prior revision said "settlements 1" while
STATE said 2 — the exact rot the pointer rule prevents. Measured counts live
in the `STATE.md` header; settlement evidence in `fable/settlement/`. What
stays qualitatively true until its register says otherwise: no external
buyer has ever paid; not on PyPI; no public host or registry listing;
product not yet notary-grade; multi-instance gaps open; G9 reconcile is not
yet routine. L0 aspiration ≠ L1 product.

---

## Related

- [`VISION.md`](../../VISION.md) — the single north-star statement  
- [`MIND.md`](MIND.md) — shared operating core; unblock ladder  
- [`fable/REFOUNDING.md`](fable/REFOUNDING.md) — substrate-as-product, staged path to contact  
- [`PRODUCT_ORG.md`](PRODUCT_ORG.md) — eras, timing, scale, M7→N0 sequence  
- [`OVERSEER.md`](OVERSEER.md) — rubric, output contract, Scout conferral  
- [`INNOVATION_LOOP.md`](INNOVATION_LOOP.md) — north star + scorecard  
- [`GUARDIAN.md`](GUARDIAN.md) — G1–G12  
- [`SCOUT_TICK_PROMPT.md`](SCOUT_TICK_PROMPT.md) — Idea agent  
- [`AUTONOMOUS.md`](AUTONOMOUS.md) — unattended execution  
- Pulse workflow: `/workflow agent-commerce-pulse`
