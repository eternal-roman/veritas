# VISION + hooks registry: single north star, machine-readable integration surface

## Context

The directive: pull latest main, evaluate the org and every product surface, write the canonical VISION document for all agents/workers from first principles, solve onboarding/ingress/egress roadblocks, ensure hooks exist so other agents know where to engage, build it, and autonomously merge with CI green.

Exploration (3 agents + direct verification against origin/main `0eb4ac1`+) found:

- **No VISION.md exists anywhere.** The north star is stated in **four conflicting wordings** (GOVERNING.md §1, INNOVATION_LOOP.md, PRODUCT_ORG.md, CONTINUOUS.md — "hub" vs "substrate" vs "business model"), while GUARDIAN treats "hub ready" as gate-failure phrasing.
- **Settlement counts are restated contradictorily (0 vs 1 vs 2) in ≥8 places.** Verified live: GOVERNING §7 "Always restated landmass" says "**1**" directly under a sentence warning against rot; README says "Exactly one payment"; truth is 2 testnet chain-confirmed (evidence `docs/program/fable/settlement/`). A textbook MIND §5 violation.
- **STATE.md:226 still carries the stale "sandbox blocks egress / no on-chain settlement executable" section** contradicting its own header (2 settlements) — REFOUNDING's missed-issue #4, still live on main.
- **Integration surface is incompletely discoverable**: `GET /v1/payment-config` reachable from NO discovery doc; links dict lacks research/verify/receipts; llms.txt doesn't list itself; 7 MCP tools announced nowhere on HTTP; CLI exit-code taxonomies and payment headers machine-readable nowhere; `veritas_credit_refund_failed_total` incremented but undeclared in METRIC_HELP; custody.py:29 comment documents a wrong event-type set; self-traversal test covers only 7 of ~19 links; **no push/webhook machinery exists at all** (grep-confirmed) — a registry must state that honestly.
- **Org contradictions**: tick-prompt cadence titles disagree with ORG_LOOPS v5 for 5/7 watchers; 2 prompts cite "v4"; Architect role (landed #122) is an orphan (no inbound refs from GOVERNING/CONTINUOUS tables); Scout has a tick prompt but no charter card; the two authority orders (goal-setting vs conflict-resolution) are reconcilable but no text says so.
- Main state: #122 landed `veritas/money_loop.py` (0.1-R), #125 product_worth. Claim **free**, open product PRs **none**. G10 no-dual list: do NOT touch money_loop/A26/A27/N0/P7-C/M7/O.8/#98/#112/#122 surfaces.

**One PR** (per focus-build-merge): the canonical VISION.md + a sync-tested `/v1/hooks` integration registry + the pointer-truth pass that kills the duplication/contradiction defect class + minimal org-table reconciliation. Scorecard axis: discovery_density (E — Found alone) + kills the restated-facts defect class; net-negative lines on program docs (Pruner-friendly).

## Deliverable — one PR, two commits

Branch: `fable/vision-hooks-registry` off fresh `origin/main`, in worktree `C:/Users/elamj/Dev/veritas-fable` (currently on `fable/unblock-defaults` — fetch, then `git checkout -b … origin/main`).

### Commit 1 — code: `feat(hooks): machine-readable integration registry at /v1/hooks; constitution 2.5 (A28)`

1. **`veritas/hooks.py`** (NEW, ~200 lines) — mirrors `constitution.py` pattern. **Never imports server.py** (server imports hooks; paths are literals; tests reconcile against `app.routes`). Leaf imports only: `veritas.__version__`, `veritas.hashing.compute_content_hash`, `veritas.observability.METRIC_HELP`, `veritas.mcp_server.MCP_TOOL_NAMES` (new constant).
   - `HOOKS_VERSION = "1.0"`; `_hook(id, kind, name, description, interface, access)` constructor enforcing shape; kinds `{http, mcp-tool, cli, header, store}`; access `{free, payment-gated, session-gated, token-gated, local}`.
   - ~45 records: **26 http** (all routes incl. `/v1/hooks` itself, `/openapi.json`, `/v1/payment-config`; `/metrics` carries `access: token-gated` + `absent_without_config: true`), **7 mcp-tool** (research, verify, verify_attestation, verify_pack, verify_log_inclusion, trust, constitution), **8 cli** (all `[project.scripts]` incl. `veritas-money-loop`; machine-readable `exit_codes` — diligence `{0 pass,1 fail,2 unverifiable,3 bad_input}`, audit `{0 confirmed,1 diverged,2 unobserved,3 bad_input}`), **4 header** (X-PAYMENT, X-PAYMENT-RESPONSE, `Payment-Required: x402`, X-VERITAS-SESSION), **5 store** (custody receipts, settlement ledger, trust outcome log w/ UNPROVEN rule, Merkle evidence log, metrics with `names: sorted(METRIC_HELP)`).
   - Top-level honesty field: `"push": {"available": False, "note": "No webhook/subscription/callback machinery exists; every signal is pull — HTTP GET, CLI JSON on stdout, or files on disk."}`.
   - `build_hooks()`: hash stable body **then** add `generatedAt` (ordering discipline per constitution.py:563-566 / identity.py:73-77). `validate_hooks(doc) -> list[str]` (empty = conformant; checks shape, unique ids, per-kind interface keys, and `push.available is False` — flipping it requires shipping real push code + changing the validator).
   - No SQL-ish words (update/select/from/where) in f-strings (bandit B608); no exception text in served strings (CodeQL).
2. **`veritas/mcp_server.py`** — add module-level `MCP_TOOL_NAMES` tuple; `build_server` registers from it (FastMCP import stays lazy inside the function).
3. **`veritas/observability.py`** — METRIC_HELP += `veritas_credit_refund_failed_total` (fixes real "Undeclared metric." for server.py:660).
4. **`veritas/server.py`** — import `build_hooks` (mind ruff isort); `@app.get("/v1/hooks")` next to `/v1/constitution` (:1467); links dict (:1802) += `"hooks": "/v1/hooks"`, `"research": RESOURCE_PATH`, `"verify": "/v1/verify"`, `"receipts": "/v1/receipts/{request_id}"`, `"payment_config": "/v1/payment-config"` (house comment idiom per link).
5. **`veritas/identity.py`** — endpoints dict += `"hooks": f"{base}/v1/hooks"` (relative when PUBLIC_URL unset; hash change fine — only cross-call stability is tested).
6. **`veritas/discovery.py`** — LLMS_TXT += `- /v1/hooks: …`, `- /v1/payment-config: …`, `- /llms.txt: this index` (do NOT list /metrics — sync test asserts every listed path ≠404 and /metrics 404s by design; registry is its honest home). **`llms.txt` (repo root) — byte-identical mirror** (test is exact string equality).
7. **`veritas/custody.py`** :29 — replace the stale enumerated event-type comment with a pointer ("event names are defined at their emit sites in pipeline/notary").
8. **`veritas/constitution.py`** — `CONSTITUTION_VERSION = "2.5"`; A28 (service scope, L1): *"Integration surfaces are registered, not discovered by accident: every HTTP route the service mounts is either listed in the machine-readable hooks registry served at /v1/hooks or named in an explicit exclusion list, the registry never advertises a surface that does not exist, and the absence of push delivery is stated in the registry rather than left to be inferred."* Enforcement: `tests/test_hooks.py::test_every_app_route_is_registered_or_excluded`, `::test_registry_advertises_no_phantom_routes`, `::test_push_absence_is_honest` (POSIX node ids — validated by real pytest collection). **`CONSTITUTION.md`** — "version 2.5" string + A28 statement rendered verbatim.
9. **`tests/test_hooks.py`** (NEW) — copy `free_client` reload fixture verbatim (test_discovery.py:19-26, + delenv VERITAS_PUBLIC_URL); module top-level import-clean (test_constitution shells `pytest --collect-only`; any import error kills every pointer). Tests: (1) endpoint serves module registry + validates + hash matches fresh build; (2) hash stable across builds; (3) **every `app.routes` path registered or in exclusion tuple `("/docs", "/redoc", "/docs/oauth2-redirect")`** — the sync test the codebase lacks; (4) reverse: no phantom routes (templated paths compared literally); (5) every non-templated registered path GETs ≠404 (405 = exists); `/metrics` asserted ==404 unconfigured (pins documented absence); (6) every links value + every llms.txt `- /path` bullet ⊆ registry; (7) `push.available is False`; (8) regex `metrics.increment("…")` over server.py source — every name ∈ METRIC_HELP; (9) hooks mcp names == MCP_TOOL_NAMES; (10) CLI exit-code values string-checked against diligence_cli/audit_cli sources.
10. **`tests/test_discovery.py`** — generalize `test_well_known_is_self_traversing` (:29-34) to iterate ALL links (≠404; POST-only may 405), dropping the 7-name tuple. Net-negative.
11. **`.github/workflows/ci.yml`** — import line (:49) += `veritas.hooks`; structure checks += `test -f VISION.md`, `test -f llms.txt`.
12. **`tests/test_constitution.py`** :217 — banned-words tuple += `"VISION.md"`.
13. **`veritas/__init__.py`** — `0.8.1` → `0.9.0` (new public surface + constitution bump; single source, invariant 9).

### Commit 2 — docs: `docs(vision): single north star + pointer-truth pass; org table reconciliation`

14. **`VISION.md`** (NEW, root, ~150 lines). Sections: header (L0 direction binding all agents/workers; precedence unchanged GUARDIAN → MIND → GOVERNING loops → cards); **§1 North star** — the ONE full statement (absorbs GOVERNING wording: substrate for multi-billion-dollar agent-to-agent commerce, three pillars, dollar figure is direction not metric); **§2 Identity by pointer** to MIND §1 (no second identity statement); **§3 Strategy by pointer** to REFOUNDING §4 staged path + §5 kill criteria + STRATEGY_EVAL_AND_PLAN posture F; **§4 Three interfaces** (human→agent operator-minutes; agent→human evidence artifacts; agent→agent discovery chain `/.well-known/x402` → identity → hooks → constitution → paid x402 work, MCP local) with one "still needs" line each; **§5 Roadblock ledger** — 7 rows (agent onboarding, money ingress, money egress, human onboarding, business incorporation, discovery/trust cold-start, integration friction) × (first-principles resolution / exists-today w/ evidence pointer / L0 future); **§6 Structural draw** (receipts/warranties/standing compound per transaction; marginal verification cost falls while standing data appreciates — substrate-rent shape, pointer REFOUNDING §3); **§7 Revenue streams as L0 hypotheses w/ falsifiers** (per-query fees, credits, notarization, warranty premiums, attestation rent — no projections); **§8 What this document is not** (no proven claims; counts live at evidence); PROPERTY/EVIDENCE-LEVEL/NOT-PROVEN block. **Must pass the banned regex it joins** (`live-ready|revenue-ready|production-ready|ZK|is complete`) — paraphrase the gate rule, never quote the tokens.
15. **`docs/program/GOVERNING.md`** [-] — north star §1 → 3-line pointer to VISION; loop table += VISION row; §7 landmass: counts → pointers (STATE header + `fable/settlement/`), kills the stale "1"; role stack += Architect row (owns seam map; not implementation/merge/ship_ok); one sentence after §0 reconciling the two authority orders (conflict precedence vs goal-setting — different axes, both hold).
16. **`docs/program/INNOVATION_LOOP.md`** [-] — north star → pointer; landmass counts → pointers.
17. **`docs/program/PRODUCT_ORG.md`** [-] — L0 line → pointer; both count sites → pointers (kills internal 2-vs-0 contradiction).
18. **`docs/program/CONTINUOUS.md`** — objective line → pointer; counts → pointer; role-briefs table: Scout row gains `SCOUT.md` link, += Architect row (on-demand, no timer — L4 per ORG_LOOPS layer cake).
19. **`docs/program/STATE.md`** [-] — delete stale "Environment constraint" section (:226-233), replace with 3 dated pointer lines (egress re-proven 2026-08-09, `fable/settlement/` + unblock_probe; REFOUNDING missed-issue #4 retired); progress-log entry for this PR.
20. **`docs/program/MIND.md`** — §1 += one pointer line (full north star + roadblock ledger live in VISION.md; this section remains the identity kernel).
21. **`README.md`** — status paragraph: count-free honest phrasing pointing at `docs/program/fable/settlement/` (replaces stale "Exactly one payment"); endpoints table += `GET /v1/hooks`.
22. **`docs/program/GUARDIAN.md`** — landmass "zero on-chain settlements" → pointer phrasing (weakens nothing).
23. **`docs/program/ECOSYSTEM_ADVANCE.md`** — "remain **0**" → pointer phrasing.
24. **Tick prompts/cards cadence truth** — CONDUCTOR_TICK_PROMPT 12→6-minute; OVERSEER 8→12; STEWARD 15→30; FLYWHEEL 20→45 title + body reword (45m default, 20m conditional backup per ORG_LOOPS; Conductor 6m); RESEARCHER_TICK_PROMPT + PRUNER_TICK_PROMPT "v4"→"v5"; RESEARCHER.md cadence 12m→10m.
25. **`docs/program/SCOUT.md`** (NEW, ~14 lines) — minimal charter card w/ Mindset block (optimizes divergent pattern fuel; refuses approvals/NEXT/merges; rung-2 bias); SCOUT_TICK_PROMPT charter line → points at it. Closes the MIND §7 law violation (role without card).
26. **`AGENTS.md`** — conventions bullet += VISION.md in load order ("program docs point to it, never restate it"); consuming-the-service section += hooks bullet.
27. **`pyproject.toml`** — `[project.urls]` += `Vision = …`.
28. **`docs/program/flywheel-claim.md`** — landed row (after PR number known); claim stays `free` (free-on-merge, WORKFLOW_HYGIENE §8).

**Out of scope** (G10 no-dual): `money_loop.py`, A26/A27, `product_worth.py`, `ARCHITECTURE.md` content, `STRATEGY_EVAL_AND_PLAN.md`, N0/P7-C/M7/O.8/#98/#112/#122 surfaces.

## Verification (local, in the venv at scratchpad `venv-fable`)

1. `python -m pytest tests/ -q --tb=short` — full suite green.
2. **Teeth check**: temporarily add scratch `@app.get("/v1/_teeth_probe")` → `pytest tests/test_hooks.py` → route-coverage test MUST fail naming the property → revert → green. Never committed.
3. `ruff check veritas tests scripts`; `PYTHONIOENCODING=utf-8 bandit -r veritas scripts -ll -q`; `python -m veritas.evaluations.payment_model`; harness gates.
4. The exact ci.yml import line + `veritas.hooks`.
5. Grep VISION.md against the banned regex before committing.
6. PROPERTY / EVIDENCE LEVEL / NOT PROVEN block in the PR body (L1 registry+tests; L0 VISION direction; NOT PROVEN: demand, mainnet, push delivery, unsolicited buyers).

## Merge (autonomous, user-directed)

Push → `gh pr create` (body names axis + defect-class kill + constitution 2.4→2.5) → background wait-then-merge loop (repo forbids `--auto`; poll checks, on all-green `gh pr merge --squash`; BEHIND → `gh pr update-branch`; owner automation may merge first — "already merged" = success) → post-merge: fetch, confirm tip, run test_hooks + test_constitution on tip → update memory (veritas-innovation-loop / new vision-doc pointer note).

## Risks

- Concurrent agent merges docs mid-flight (active — steward ticks): keep program-doc diffs line-surgical; update-branch + re-apply on conflict; never force-push over peer work.
- llms.txt byte-identity (exact string equality test).
- Collection fragility: importorskip only inside test bodies.
- CONSTITUTION.md verbatim statement + "version 2.5" string discipline.
- VISION self-test trap: never quote banned tokens in VISION.md.
