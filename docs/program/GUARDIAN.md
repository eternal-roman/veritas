# Guardian charter — clean, sharp, end-to-end

This file is the **anti-handwave / no-fake-code gate** for every flywheel tick,
workflow cycle, PR, and agent session that touches
[eternal-roman/veritas](https://github.com/eternal-roman/veritas).

**Stack:** [`GOVERNING.md`](GOVERNING.md) sets goals (loops). This file ensures
code that ships is **functioning** (battery, no soft-fail) and **not false**
(settlement, dual engine, claim theater). The **Overseer** then judges whether
that code is **necessary** and **pursuant** to A2A commerce strategy.

It does not replace `skills/adversarial-code-truth.md` or `AGENTS.md`. It
applies them to autonomous loops that would otherwise optimise for looking
busy.

## Oath

1. **Respect what is already true.** Do not regress the honesty taxonomy,
   one-engine rule, money-path ordering, constitution L0/L1 discipline, or
   dogfood that found real defects. Read before you write.
2. **Advance the cause with one real bet.** Prefer `STATE.md` NEXT ACTION.
   Ship the smallest change that is true under tests.
3. **Never fake it.** No invented green, no dual pipelines, no local
   facilitator green sold as settlement, no score inflation, no "basically
   ready".
4. **Never handwave it.** Missing evidence is a stop, not a story. Soft-fail
   (`|| true`, "if feasible", "should pass", assumed CI) is forbidden.
5. **End-to-end or incomplete.** Structural tests are L1 only. Application
   success requires a path a hostile external agent can actually use for the
   stated purpose — or an explicit NOT PROVEN.

## Hard fail-closed rules (non-negotiable)

| # | Rule | Violation looks like |
|---|------|----------------------|
| G1 | **Battery before ship.** `pytest tests/ -q` must exit 0 on the branch. Ruff, harness, and payment_model when those entry points exist in the tree — not "if convenient". | Shipping after skipped tests |
| G2 | **No soft-fail.** No `\|\| true`, no `continue-on-error`, no treating "command not found" as green. | CI or agent scripts that hide red |
| G3 | **One engine / one payer.** All research through `pipeline.run_research`; all buyer signing through `veritas.payer` + Signer seam. | Second path "for agents" |
| G4 | **Unavailable stays non-billable.** Never map retrieval failure to `no_evidence` or `billable: true`. | Outage sold as empty result |
| G5 | **Money path order.** Verify → claim nonce → work → fsync delivery → settle. Indeterminate ≠ failed. | Settle before delivery; invent costs |
| G6 | **Settlement claims need a tx hash.** Local facilitator green is not on-chain. Gap G9 remains until chain reconcile exists. | "Live payments work" from unit tests |
| G7 | **Stock from the tree, not from defaults.** If stock/select cannot read STATE + code, **stop**. Do not invent NEXT ACTION or scorecard. | Silent O.6 default while STATE says otherwise |
| G8 | **Audit fail-closed on blocker/major.** Ship only when required panels have no **blocker/major** honesty/safety issues and a PROPERTY block exists. **Minor findings are advisory** (do not veto alone). Failed/missing panel = do not ship that cycle. | Cheerleading empty findings; OR minor-nit human stalls |
| G9 | **410 ≠ 404** for pruned receipts (and any analogous "we deleted it"). | Collapsing retention into not-found |
| G10 | **Do not clobber WIP.** Concurrent tick skips if another honest branch is mid-flight. Use `docs/program/flywheel-claim.md`. Continue same bet; never parallel rewrite. | Second agent overwriting O.8 |
| G11 | **Docs match code.** STATUS/STATE/cycle reports must not claim what tests do not pin. Banned words without evidence: complete, live-ready, ZK, revenue-ready. | Marketing in cycle ledger |
| G12 | **Merge only on green CI head SHA.** **Autonomous default `auto_merge: true`** (squash when required checks SUCCESS). Never merge red. Humans still own mainnet funding, TLS, PyPI publisher identity — not routine green product merges. See `AUTONOMOUS.md`. | Merge red; block forever on human for green CI |
| G13 | **Pruner before ship.** Product PR/ship only when Pruner `ship_ok` (lean + battery + no broken E2E claims). Blocks useless, non-functional, or bloated code/docs. See `PRUNER.md`. | Ship after lazy green; bloat merged; unrun paths claimed working |

## Evidence levels (repeat for agents)

| Level | Allowed claim |
|-------|----------------|
| L0 | Intended / designed |
| L1 | Holds on these cases (tests) |
| L2 | Holds for stated bounds (model) |
| L3–L4 | Proof — rare here |

Hourly "we improved the hub" without axis evidence = **L0 cosplay**. Reject.

## What already must not be broken (pride list)

Cite `docs/program/cycles/000-baseline.md` and main HEAD. At minimum:

- Outcome taxonomy + non-billable `unavailable`
- Custody chain delivered; path-safe receipt ids (O17 closed)
- Ledger claim/delivery/settlement durability
- Constitution enforcement pointers resolve
- Buyer `SpendPolicy` + payment model gate
- Dogfood cycles 2–4 stay meaningful (do not delete their pins)

## Before any success claim

Emit:

```
PROPERTY: ...
EVIDENCE LEVEL: L0|L1|L2|L3|L4
CHECKED ARTIFACT: ...
ASSUMPTIONS: ...
NOT PROVEN: ...
```

Missing block on a success claim = **gate failure**. The flywheel must treat
gate failure as ship-blocker.

## Landmass (always restate after a win)

After every cycle, name what still blocks a hostile agent in the wild. Until
proven otherwise, that list includes: no unsolicited buyer has ever paid
(settlement counts live at STATE header / `fable/settlement/` — a count
restated here went stale), snippet or unbuilt notary product, no public
discovery host, multi-instance gaps, G9.

## Relationship to continuous operation

Hourly ticks are **not** proof of progress. A tick that only rephrases docs
is a noop. A tick that lands a PR without G1–G12 is a regression risk and
must be reverted or blocked — not celebrated.
