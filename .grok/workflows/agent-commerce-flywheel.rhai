// Agent Commerce Innovation Flywheel — one full cycle (or max_cycles) of
// stock → score → select → plan → build → audit → verify → ship → learn → reframe.
// Spec: docs/program/INNOVATION_LOOP.md
//
// Args (all optional):
//   max_cycles   int   default 1, hard-capped at 3 per run
//   auto_merge   bool  default false — only merge when true AND CI green AND audit clean
//   prefer_bet   string optional forced selection (e.g. "O.6")
//   dry_run      bool  default false — stock+score+select+plan only, no build/ship

let meta = #{
    name: "agent-commerce-flywheel",
    description: "Recursive autonomy/commerce innovation cycle: stock main, select one bet, build, adversarially audit, verify, PR, learn, reframe",
    when_to_use: "Continuous agent-commerce improvement; after a merge; when told to run the flywheel or innovation loop",
    phases: [
        #{ title: "Stock", detail: "Inventory excellence, gaps, STATE, scorecard" },
        #{ title: "Select", detail: "One bet; ladder default; written deviation" },
        #{ title: "Build", detail: "Plan, implement, tests first" },
        #{ title: "Audit", detail: "Adversarial truth + over-engineering pass" },
        #{ title: "Ship", detail: "Verify, PR, optional merge after CI" },
        #{ title: "Learn", detail: "Cycle report, STATE update, reframe next" },
    ],
};

// --- schemas ---

let stock_schema = #{
    "type": "object",
    "required": ["excellence", "killers", "next_action", "scorecard", "head_sha"],
    "properties": #{
        "head_sha": #{ "type": "string" },
        "next_action": #{ "type": "string" },
        "excellence": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
        "killers": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
        "scorecard": #{
            "type": "object",
            "required": ["A", "B", "C", "D", "E", "F"],
            "properties": #{
                "A": #{ "type": "integer" },
                "B": #{ "type": "integer" },
                "C": #{ "type": "integer" },
                "D": #{ "type": "integer" },
                "E": #{ "type": "integer" },
                "F": #{ "type": "integer" },
            },
        },
        "open_critical": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
    },
};

let select_schema = #{
    "type": "object",
    "required": ["bet_id", "title", "why_now", "axis_raised", "acceptance", "non_goals", "deviates_from_ladder", "deviation_reason"],
    "properties": #{
        "bet_id": #{ "type": "string" },
        "title": #{ "type": "string" },
        "why_now": #{ "type": "string" },
        "axis_raised": #{ "type": "string" },
        "acceptance": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
        "non_goals": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
        "deviates_from_ladder": #{ "type": "boolean" },
        "deviation_reason": #{ "type": "string" },
        "files_likely": #{ "type": "array", "maxItems": 16, "items": #{ "type": "string" } },
    },
};

let plan_schema = #{
    "type": "object",
    "required": ["steps", "tests_first", "risks"],
    "properties": #{
        "steps": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
        "tests_first": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
        "risks": #{ "type": "array", "maxItems": 6, "items": #{ "type": "string" } },
        "branch_name": #{ "type": "string" },
    },
};

let build_schema = #{
    "type": "object",
    "required": ["success", "branch", "summary", "tests_added", "files_changed"],
    "properties": #{
        "success": #{ "type": "boolean" },
        "branch": #{ "type": "string" },
        "summary": #{ "type": "string" },
        "tests_added": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
        "files_changed": #{ "type": "array", "maxItems": 40, "items": #{ "type": "string" } },
        "blocked_reason": #{ "type": "string" },
    },
};

let audit_schema = #{
    "type": "object",
    "required": ["ship_blockers", "should_ship", "findings", "property_block"],
    "properties": #{
        "should_ship": #{ "type": "boolean" },
        "ship_blockers": #{ "type": "array", "maxItems": 10, "items": #{ "type": "string" } },
        "findings": #{ "type": "array", "maxItems": 12, "items": #{
            "type": "object",
            "required": ["severity", "issue"],
            "properties": #{
                "severity": #{ "type": "string" },
                "issue": #{ "type": "string" },
                "file": #{ "type": "string" },
            },
        }},
        "property_block": #{ "type": "string" },
        "overengineering": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
    },
};

let verify_schema = #{
    "type": "object",
    "required": ["green", "commands", "notes"],
    "properties": #{
        "green": #{ "type": "boolean" },
        "commands": #{ "type": "array", "maxItems": 10, "items": #{ "type": "string" } },
        "notes": #{ "type": "string" },
        "failures": #{ "type": "array", "maxItems": 10, "items": #{ "type": "string" } },
    },
};

let ship_schema = #{
    "type": "object",
    "required": ["pr_url", "pr_number", "merged", "ci_green"],
    "properties": #{
        "pr_url": #{ "type": "string" },
        "pr_number": #{ "type": "integer" },
        "merged": #{ "type": "boolean" },
        "ci_green": #{ "type": "boolean" },
        "notes": #{ "type": "string" },
    },
};

let learn_schema = #{
    "type": "object",
    "required": ["cycle_path", "scorecard_after", "next_bet", "still_kills"],
    "properties": #{
        "cycle_path": #{ "type": "string" },
        "scorecard_after": #{
            "type": "object",
            "required": ["A", "B", "C", "D", "E", "F"],
            "properties": #{
                "A": #{ "type": "integer" },
                "B": #{ "type": "integer" },
                "C": #{ "type": "integer" },
                "D": #{ "type": "integer" },
                "E": #{ "type": "integer" },
                "F": #{ "type": "integer" },
            },
        },
        "next_bet": #{ "type": "string" },
        "still_kills": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
        "axis_delta": #{ "type": "string" },
    },
};

// --- helpers (defensive: live schema outputs are full; canned validate_only is sparse) ---

fn axis_num(sc, key, fallback) {
    if sc == () { return fallback; }
    let v = ();
    if key == "A" { v = sc.A; }
    else if key == "B" { v = sc.B; }
    else if key == "C" { v = sc.C; }
    else if key == "D" { v = sc.D; }
    else if key == "E" { v = sc.E; }
    else if key == "F" { v = sc.F; }
    if v == () { return fallback; }
    v
}

fn normalize_scorecard(sc) {
    #{
        A: axis_num(sc, "A", 0),
        B: axis_num(sc, "B", 0),
        C: axis_num(sc, "C", 0),
        D: axis_num(sc, "D", 0),
        E: axis_num(sc, "E", 0),
        F: axis_num(sc, "F", 0),
    }
}

fn as_str(v, fallback) {
    if v == () { return fallback; }
    if type_of(v) == "string" { return v; }
    v.to_string()
}

fn as_bool(v, fallback) {
    if v == () { return fallback; }
    if v == true { return true; }
    if v == false { return false; }
    fallback
}

fn as_list(v) {
    if v == () { return []; }
    if type_of(v) == "array" { return v; }
    []
}

fn normalize_stock(raw) {
    if raw == () {
        return #{
            head_sha: "unknown",
            next_action: "O.6 retention 410 Gone",
            excellence: [],
            killers: [],
            open_critical: [],
            scorecard: normalize_scorecard(()),
        };
    }
    let sc = ();
    if raw.scorecard != () { sc = raw.scorecard; }
    #{
        head_sha: as_str(raw.head_sha, "unknown"),
        next_action: as_str(raw.next_action, "O.6 retention 410 Gone"),
        excellence: as_list(raw.excellence),
        killers: as_list(raw.killers),
        open_critical: as_list(raw.open_critical),
        scorecard: normalize_scorecard(sc),
    }
}

fn normalize_selected(raw, prefer) {
    if raw == () {
        let bid = prefer;
        if bid == "" { bid = "O.6"; }
        return #{
            bet_id: bid,
            title: "default ladder bet",
            why_now: "STATE NEXT ACTION / prefer_bet",
            axis_raised: "B",
            acceptance: [],
            non_goals: [],
            deviates_from_ladder: false,
            deviation_reason: "",
            files_likely: [],
        };
    }
    let bid = as_str(raw.bet_id, "");
    if bid == "" {
        bid = prefer;
        if bid == "" { bid = "O.6"; }
    }
    #{
        bet_id: bid,
        title: as_str(raw.title, bid),
        why_now: as_str(raw.why_now, ""),
        axis_raised: as_str(raw.axis_raised, "B"),
        acceptance: as_list(raw.acceptance),
        non_goals: as_list(raw.non_goals),
        deviates_from_ladder: as_bool(raw.deviates_from_ladder, false),
        deviation_reason: as_str(raw.deviation_reason, ""),
        files_likely: as_list(raw.files_likely),
    }
}

fn normalize_plan(raw) {
    if raw == () {
        return #{
            steps: ["implement selected bet"],
            tests_first: ["add failing test for acceptance"],
            risks: [],
            branch_name: "fix/flywheel-bet",
        };
    }
    let bn = as_str(raw.branch_name, "fix/flywheel-bet");
    #{
        steps: as_list(raw.steps),
        tests_first: as_list(raw.tests_first),
        risks: as_list(raw.risks),
        branch_name: bn,
    }
}

// --- args ---

let max_cycles = 1;
let auto_merge = false;
let prefer_bet = "";
let dry_run = false;

if args != () {
    if args.max_cycles != () {
        max_cycles = args.max_cycles;
    }
    if args.auto_merge != () {
        auto_merge = args.auto_merge;
    }
    if args.prefer_bet != () {
        prefer_bet = args.prefer_bet;
    }
    if args.dry_run != () {
        dry_run = args.dry_run;
    }
}

if max_cycles < 1 { max_cycles = 1; }
if max_cycles > 3 { max_cycles = 3; }

log("flywheel start max_cycles=" + max_cycles.to_string()
    + " auto_merge=" + auto_merge.to_string()
    + " dry_run=" + dry_run.to_string()
    + " prefer_bet=" + prefer_bet);

let cycle_results = [];
let cycle_i = 0;
let stall_count = 0;

while cycle_i < max_cycles {
    let cycle_num = cycle_i + 1;
    log("=== cycle " + cycle_num.to_string() + " of " + max_cycles.to_string() + " ===");

    // ========== STOCK ==========
    phase("Stock");
    let stock_prompt = "";
    stock_prompt += "### WINDOWS PWSH SHELL SAFETY\n";
    stock_prompt += "You run under Windows PowerShell. Never use bare Unix pipes (head/grep/tail/find). ";
    stock_prompt += "For git bash-like ops use .\\scripts\\with-git-bash.cmd \"...\" if present. ";
    stock_prompt += "Truncate with | Out-String -Stream | Select-Object -First N.\n\n";
    stock_prompt += "You are the STOCK phase of the Veritas agent-commerce flywheel.\n";
    stock_prompt += "Read docs/program/GUARDIAN.md first. Then read with tools (do not invent):\n";
    stock_prompt += "1. docs/program/INNOVATION_LOOP.md\n";
    stock_prompt += "2. docs/program/STATE.md (especially NEXT ACTION)\n";
    stock_prompt += "3. docs/program/cycles/000-baseline.md and the latest cycle file if any\n";
    stock_prompt += "4. STATUS.md, ECOSYSTEM.md (growth loops), ROADMAP.md relevant phases\n";
    stock_prompt += "5. git log --oneline -15 and git status\n";
    stock_prompt += "6. Skim veritas/autonomous/, veritas/payer.py, veritas/ledger.py, veritas/agent_cli.py\n\n";
    stock_prompt += "Return JSON matching the schema:\n";
    stock_prompt += "- head_sha: short git SHA of HEAD from git, not guessed\n";
    stock_prompt += "- next_action: exact NEXT ACTION text from STATE.md\n";
    stock_prompt += "- excellence: up to 12 strengths that must not regress\n";
    stock_prompt += "- killers: product-killing gaps\n";
    stock_prompt += "- open_critical: open critical defect ids if any\n";
    stock_prompt += "- scorecard: integers 0-4 for axes A-F per INNOVATION_LOOP.md\n";
    stock_prompt += "Be adversarially honest. Money is real (C) stays 0 until a tx hash exists.\n";
    stock_prompt += "If you cannot read the files, fail the schema rather than inventing stock.\n";

    let stock_r = agent(stock_prompt, #{
        label: "stock-c" + cycle_num.to_string(),
        capability_mode: "read-only",
        output_schema: stock_schema,
    });

    // Guardian G7: stock from the tree. Defaults only for dry_run smoke/canned paths —
    // live build must not invent NEXT ACTION or scorecard.
    let stock_ok = stock_r != () && stock_r.success && stock_r.output != ()
        && stock_r.output.next_action != () && stock_r.output.next_action != ""
        && stock_r.output.scorecard != ();
    if !stock_ok {
        if dry_run {
            log("stock sparse — dry_run only: normalize for smoke path (not a real stock)");
        } else {
            pause("infra", "Guardian G7: stock failed or incomplete. Refuse invented defaults. Resume after agents can read STATE.md.");
        }
    }
    let stock_raw = ();
    if stock_r != () && stock_r.success && stock_r.output != () {
        stock_raw = stock_r.output;
    }
    let stock = normalize_stock(stock_raw);
    if !dry_run && (stock.head_sha == "unknown" || stock.next_action == "") {
        pause("infra", "Guardian G7: stock unusable after normalize — stop.");
    }
    log("stock next_action=" + stock.next_action);
    log("scorecard A=" + stock.scorecard.A.to_string()
        + " B=" + stock.scorecard.B.to_string()
        + " C=" + stock.scorecard.C.to_string()
        + " D=" + stock.scorecard.D.to_string()
        + " E=" + stock.scorecard.E.to_string()
        + " F=" + stock.scorecard.F.to_string());
    // Guardian: axis C must stay 0 unless stock explicitly provides a tx-hash claim (it must not).
    if stock.scorecard.C > 0 {
        log("WARNING: scorecard C>0 without on-chain proof is usually handwave — auditors must reject unless tx hash cited in stock.excellence/killers");
    }

    // ========== SELECT ==========
    phase("Select");
    let select_prompt = "";
    select_prompt += "### WINDOWS PWSH SHELL SAFETY: no bare head/grep/tail; use pwsh Select-Object.\n\n";
    select_prompt += "Read docs/program/GUARDIAN.md. SELECT one shippable bet.\n\n";
    select_prompt += "STOCK JSON (authoritative — do not invent):\n";
    select_prompt += json_encode(stock) + "\n\n";
    select_prompt += "Rules from docs/program/INNOVATION_LOOP.md + GUARDIAN:\n";
    select_prompt += "1. Prefer STATE NEXT ACTION when unblocked and load-bearing.\n";
    select_prompt += "2. Deviate only with written reason (security > money path > ladder).\n";
    select_prompt += "3. One bet only. Smallest change that raises an axis or closes a critical gap.\n";
    select_prompt += "4. Never second engine / second payment path.\n";
    select_prompt += "5. North star: agent independence, scalable commerce, lifecycle enrichment.\n";
    select_prompt += "6. Do NOT select on-chain settlement work that this sandbox cannot prove without egress;\n";
    select_prompt += "   you may select runbook/harness work that fails closed and documents the gap.\n";
    select_prompt += "7. acceptance[] must be observable tests/behaviours, not vibes.\n";
    if prefer_bet != "" {
        select_prompt += "\nOperator prefer_bet=" + prefer_bet + " — honour it if it is still valid after stock.\n";
    }
    select_prompt += "\nReturn bet_id, title, why_now, axis_raised (letter), acceptance[], non_goals[],\n";
    select_prompt += "deviates_from_ladder (bool), deviation_reason (string, empty if not), files_likely[].\n";
    select_prompt += "Read STATE.md and ROADMAP.md before choosing.\n";

    let select_r = agent(select_prompt, #{
        label: "select-c" + cycle_num.to_string(),
        capability_mode: "read-only",
        output_schema: select_schema,
    });

    let select_ok = select_r != () && select_r.success && select_r.output != ()
        && select_r.output.bet_id != () && select_r.output.bet_id != "";
    if !select_ok {
        if dry_run {
            log("select sparse — dry_run only: prefer_bet/ladder placeholder (not a real select)");
        } else {
            pause("verification", "Guardian G7: select failed. Refuse default bet invent. Resume when select works.");
        }
    }
    let select_raw = ();
    if select_r != () && select_r.success && select_r.output != () {
        select_raw = select_r.output;
    }
    let selected = normalize_selected(select_raw, prefer_bet);
    if !dry_run && selected.acceptance.len() == 0 {
        pause("verification", "Guardian: empty acceptance criteria — handwave refused. Select must name tests.");
    }
    log("selected " + selected.bet_id + ": " + selected.title);
    if selected.deviates_from_ladder {
        log("DEVIATION: " + selected.deviation_reason);
    }

    // ========== PLAN + BUILD ==========
    phase("Build");
    let plan_prompt = "";
    plan_prompt += "### WINDOWS PWSH SHELL SAFETY: no bare Unix filters; pwsh Select-Object for truncate.\n\n";
    plan_prompt += "Read docs/program/GUARDIAN.md. Write a tight implementation PLAN. Read the real code first.\n";
    plan_prompt += "BET:\n" + json_encode(selected) + "\n\n";
    plan_prompt += "Constraints:\n";
    plan_prompt += "- Tests first (TDD). CI has no soft-fail. No || true.\n";
    plan_prompt += "- skills/adversarial-code-truth.md + GUARDIAN.md: narrow claims only.\n";
    plan_prompt += "- One engine; one buyer payment path; wire contract if surface changes.\n";
    plan_prompt += "- 410 Gone must not become 404 for pruned receipts if this is O.6.\n";
    plan_prompt += "- Do not regress dogfood pins, custody path safety, or billable gates.\n";
    plan_prompt += "- Branch name suggestion: fix/<bet> or feat/<bet> kebab-case.\n";
    plan_prompt += "Return steps[], tests_first[] (non-empty), risks[], branch_name.\n";

    let plan_r = agent(plan_prompt, #{
        label: "plan-c" + cycle_num.to_string(),
        capability_mode: "read-only",
        output_schema: plan_schema,
    });

    let plan_ok = plan_r != () && plan_r.success && plan_r.output != ()
        && plan_r.output.tests_first != ();
    if !plan_ok && !dry_run {
        pause("verification", "Guardian: plan missing tests_first — refuse plan-free build.");
    }
    let plan_raw = ();
    if plan_r != () && plan_r.success && plan_r.output != () {
        plan_raw = plan_r.output;
    }
    let plan = normalize_plan(plan_raw);
    if !dry_run && plan.tests_first.len() == 0 {
        pause("verification", "Guardian: empty tests_first after normalize — stop.");
    }
    log("plan steps=" + plan.steps.len().to_string());

    if dry_run {
        let dry_path = write_scratch_file(
            "cycle-" + cycle_num.to_string() + "-dry-run.json",
            json_encode(#{
                stock: stock,
                selected: selected,
                plan: plan,
            })
        );
        cycle_results.push(#{
            cycle: cycle_num,
            dry_run: true,
            bet: selected.bet_id,
            path: dry_path,
        });
        log("dry_run complete for cycle " + cycle_num.to_string());
        cycle_i += 1;
        continue;
    }

    let build_prompt = "";
    build_prompt += "### WINDOWS PWSH SHELL SAFETY (NON-NEGOTIABLE)\n";
    build_prompt += "Shell is pwsh. Never use | head, | tail, | grep, find, ls -la at top level.\n";
    build_prompt += "Use | Out-String -Stream | Select-Object -First N for truncation.\n";
    build_prompt += "Git complex ops: .\\scripts\\with-git-bash.cmd \"single-line cmd\" if helper exists.\n\n";
    build_prompt += "You are BUILD for the Veritas agent-commerce flywheel. Guardian: docs/program/GUARDIAN.md.\n";
    build_prompt += "Implement exactly this bet and plan. Do not expand scope. Do not fake green.\n\n";
    build_prompt += "BET:\n" + json_encode(selected) + "\n\n";
    build_prompt += "PLAN:\n" + json_encode(plan) + "\n\n";
    build_prompt += "Required process:\n";
    build_prompt += "1. Prefer continuing an existing branch for this bet; do not clobber unrelated WIP (G10).\n";
    build_prompt += "2. Write failing tests first; then implement until those tests pass.\n";
    build_prompt += "3. Respect invariants: one engine, unavailable non-billable, money-path order, path-safe ids.\n";
    build_prompt += "4. Do NOT push or open PR — later phase does that.\n";
    build_prompt += "5. Do NOT claim on-chain settlement, live-ready, revenue-ready, or ZK.\n";
    build_prompt += "6. Run full: python -m pytest tests/ -q — success=false if red. No soft-fail.\n";
    build_prompt += "7. ruff check veritas tests when ruff is importable; if missing, success=false with blocked_reason (G1/G2).\n\n";
    build_prompt += "Return success bool, branch, summary, tests_added[] (must be non-empty on success), files_changed[], blocked_reason if failed.\n";
    build_prompt += "Commit locally with a clear message when the flywheel needs a shippable branch.\n";

    let build_r = agent(build_prompt, #{
        label: "build-c" + cycle_num.to_string(),
        capability_mode: "all",
        output_schema: build_schema,
    });

    if build_r == () || !build_r.success || build_r.output == () {
        pause("infra", "Build agent failed to return. Resume to retry build.");
    }
    let built = build_r.output;
    if !built.success {
        log("build blocked: " + built.blocked_reason);
        await_user("user", "Build blocked on cycle " + cycle_num.to_string()
            + " (" + selected.bet_id + "): " + built.blocked_reason
            + ". Fix or adjust, then resume.");
        // After resume, still record and continue to next cycle rather than infinite rebuild
        cycle_results.push(#{
            cycle: cycle_num,
            bet: selected.bet_id,
            status: "build_blocked",
            reason: built.blocked_reason,
        });
        cycle_i += 1;
        continue;
    }
    log("build ok branch=" + built.branch);

    // ========== AUDIT ==========
    phase("Audit");
    let audit_jobs = [
        #{
            prompt: "### WINDOWS PWSH SAFETY: no bare head/grep/tail.\n\n"
                + "Adversarial code-truth AUDIT of the uncommitted/branch diff for bet "
                + selected.bet_id + " (" + selected.title + ").\n"
                + "Read skills/adversarial-code-truth.md. Inspect git diff and changed files with tools.\n"
                + "Acceptance criteria were:\n" + json_encode(selected.acceptance) + "\n"
                + "Find real bugs, honesty violations, second-engine risks, billing mistakes, path issues.\n"
                + "should_ship=true only if no ship_blockers remain.\n"
                + "property_block must be the formal gate block text (PROPERTY/EVIDENCE LEVEL/...).\n"
                + "Severity: blocker | major | minor.\n",
            label: "audit-truth-c" + cycle_num.to_string(),
            capability_mode: "read-only",
            output_schema: audit_schema,
        },
        #{
            prompt: "### WINDOWS PWSH SAFETY: no bare head/grep/tail.\n\n"
                + "Over-engineering AUDIT of the branch for bet " + selected.bet_id + ".\n"
                + "Read docs/program/GUARDIAN.md. List what to delete/simplify.\n"
                + "should_ship=true only if you read the diff AND no safety/honesty risk from bloat.\n"
                + "Default to should_ship=false if you did not inspect files with tools.\n"
                + "property_block required (formal gate). overengineering[] for delete candidates.\n",
            label: "audit-pony-c" + cycle_num.to_string(),
            capability_mode: "read-only",
            output_schema: audit_schema,
        },
    ];
    let audits = parallel(audit_jobs);

    // Guardian G8: fail-closed — require every panel to explicitly should_ship=true.
    let ship_blockers = [];
    let all_findings = [];
    let property_block = "";
    let panels_ok = 0;
    let panels_needed = audits.len();
    let ai = 0;
    for a in audits {
        if a == () || !a.success || a.output == () {
            ship_blockers.push("audit_panel_failed_slot_" + ai.to_string());
        } else {
            if a.output.should_ship == true {
                panels_ok += 1;
            } else {
                ship_blockers.push("panel_" + ai.to_string() + "_should_ship_false");
            }
            if a.output.ship_blockers != () {
                for b in a.output.ship_blockers {
                    ship_blockers.push(b);
                }
            }
            if a.output.findings != () {
                for f in a.output.findings {
                    all_findings.push(f);
                }
            }
            if property_block == "" && a.output.property_block != () {
                property_block = a.output.property_block;
            }
        }
        ai += 1;
    }

    // Any blocker-severity finding fails closed
    for f in all_findings {
        if f.severity == "blocker" {
            ship_blockers.push(f.issue);
        }
    }

    let should_ship = panels_ok == panels_needed && panels_needed > 0 && ship_blockers.len() == 0;
    if property_block == "" {
        should_ship = false;
        ship_blockers.push("missing_property_gate_block");
    }

    log("audit should_ship=" + should_ship.to_string()
        + " panels_ok=" + panels_ok.to_string() + "/" + panels_needed.to_string()
        + " blockers=" + ship_blockers.len().to_string());

    if !should_ship {
        let fix_prompt = "";
        fix_prompt += "### WINDOWS PWSH SAFETY: no bare head/grep/tail.\n\n";
        fix_prompt += "Fix ship_blockers on branch " + built.branch + " for bet " + selected.bet_id + ".\n";
        fix_prompt += "Blockers:\n" + json_encode(ship_blockers) + "\n";
        fix_prompt += "Findings:\n" + json_encode(all_findings) + "\n";
        fix_prompt += "Do not expand scope. Re-run relevant tests. Commit fix if appropriate.\n";
        fix_prompt += "Return success, branch, summary, tests_added, files_changed.\n";

        let fix_r = agent(fix_prompt, #{
            label: "fix-c" + cycle_num.to_string(),
            capability_mode: "all",
            output_schema: build_schema,
        });

        if fix_r == () || !fix_r.success || fix_r.output == () || fix_r.output.success != true {
            await_user("verification", "Audit blockers remain after fix attempt on "
                + selected.bet_id + ". Resolve manually, then resume to continue cycles.");
            cycle_results.push(#{
                cycle: cycle_num,
                bet: selected.bet_id,
                status: "audit_blocked",
                blockers: ship_blockers,
            });
            cycle_i += 1;
            continue;
        }
        // re-audit once
        let re_audit = agent(
            "### WINDOWS PWSH SAFETY.\nRe-audit after fixes. Diff on branch "
                + built.branch + ". should_ship only if clean of blockers.\n"
                + "Prior blockers were: " + json_encode(ship_blockers),
            #{
                label: "reaudit-c" + cycle_num.to_string(),
                capability_mode: "read-only",
                output_schema: audit_schema,
            }
        );
        if re_audit == () || !re_audit.success || re_audit.output == () || re_audit.output.should_ship != true {
            await_user("verification", "Re-audit still not clean. Human gate.");
            cycle_results.push(#{
                cycle: cycle_num,
                bet: selected.bet_id,
                status: "audit_blocked",
            });
            cycle_i += 1;
            continue;
        }
        should_ship = true;
        if re_audit.output.property_block != () {
            property_block = re_audit.output.property_block;
        }
    }

    // ========== VERIFY ==========
    phase("Ship");
    let verify_prompt = "";
    verify_prompt += "### WINDOWS PWSH SAFETY: no bare head/grep/tail.\n\n";
    verify_prompt += "Guardian G1/G2: Run the FULL Veritas verification battery. No soft-fail.\n";
    verify_prompt += "ALL of these are required; missing tool or non-zero exit => green=false:\n";
    verify_prompt += "1. python -m pytest tests/ -q\n";
    verify_prompt += "2. ruff check veritas tests\n";
    verify_prompt += "3. python -m veritas.evaluations.harness  (exit 0)\n";
    verify_prompt += "4. python -m veritas.evaluations.payment_model  (exit 0)\n";
    verify_prompt += "green=true ONLY if all four exit 0. Do not invent green. List exact failures.\n";

    let verify_r = agent(verify_prompt, #{
        label: "verify-c" + cycle_num.to_string(),
        capability_mode: "execute",
        output_schema: verify_schema,
    });

    if verify_r == () || !verify_r.success || verify_r.output == () || verify_r.output.green != true {
        let fail_notes = "verify failed";
        if verify_r != () && verify_r.success && verify_r.output != () {
            fail_notes = verify_r.output.notes;
        }
        await_user("verification", "Local verify not green: " + fail_notes + ". Fix and resume.");
        cycle_results.push(#{
            cycle: cycle_num,
            bet: selected.bet_id,
            status: "verify_failed",
        });
        cycle_i += 1;
        continue;
    }
    log("local verify green");

    // SHIP: PR (+ optional merge)
    let ship_prompt = "";
    ship_prompt += "### WINDOWS PWSH SAFETY: use .\\scripts\\with-git-bash.cmd for complex git if needed.\n\n";
    ship_prompt += "SHIP the branch for bet " + selected.bet_id + ".\n";
    ship_prompt += "Branch: " + built.branch + "\n";
    ship_prompt += "Summary: " + built.summary + "\n";
    ship_prompt += "Property block to include in PR body:\n" + property_block + "\n\n";
    ship_prompt += "Steps:\n";
    ship_prompt += "1. git fetch origin; ensure branch pushed to origin.\n";
    ship_prompt += "2. Open a PR against main via gh or GitHub MCP. 4C description.\n";
    ship_prompt += "3. Wait for CI on the head SHA (poll checks). Do not claim green without reading checks.\n";
    ship_prompt += "4. auto_merge flag is " + auto_merge.to_string() + ".\n";
    ship_prompt += "   - If auto_merge true AND CI green AND no failing required checks: merge (squash or repo default).\n";
    ship_prompt += "   - Otherwise leave PR open; merged=false.\n";
    ship_prompt += "5. Never force-push main. Never merge red CI.\n";
    ship_prompt += "Return pr_url, pr_number, merged, ci_green, notes.\n";

    let ship_r = agent(ship_prompt, #{
        label: "ship-c" + cycle_num.to_string(),
        capability_mode: "all",
        output_schema: ship_schema,
    });

    let shipped = #{
        pr_url: "",
        pr_number: 0,
        merged: false,
        ci_green: false,
        notes: "ship agent failed",
    };
    if ship_r != () && ship_r.success && ship_r.output != () {
        shipped = ship_r.output;
    } else {
        await_user("infra", "Ship phase failed to open/check PR. Resume after fixing auth/network.");
    }
    log("PR " + shipped.pr_url + " ci_green=" + shipped.ci_green.to_string()
        + " merged=" + shipped.merged.to_string());

    if !shipped.merged {
        await_user("user", "PR ready (or needs attention): " + shipped.pr_url
            + " ci_green=" + shipped.ci_green.to_string()
            + ". Merge when satisfied, then resume for LEARN + next cycle.");
    }

    // ========== LEARN ==========
    phase("Learn");
    let learn_prompt = "";
    learn_prompt += "### WINDOWS PWSH SAFETY.\n\n";
    learn_prompt += "LEARN phase: write the cycle report and update the program resume point.\n";
    learn_prompt += "Create docs/program/cycles/ with next NNN after existing files (001 if only 000-baseline).\n";
    learn_prompt += "Filename: NNN-<slug>.md for bet " + selected.bet_id + ".\n\n";
    learn_prompt += "Include: scores before (from stock) and after, bet, deviation, PR link, evidence,\n";
    learn_prompt += "what still kills the product, proposed next bet, PROPERTY block.\n\n";
    learn_prompt += "Also update docs/program/STATE.md NEXT ACTION to the real next step.\n";
    learn_prompt += "Commit these doc updates on the same branch or follow-up commit on main if already merged.\n\n";
    learn_prompt += "STOCK was:\n" + json_encode(stock) + "\n";
    learn_prompt += "SELECTED:\n" + json_encode(selected) + "\n";
    learn_prompt += "BUILT:\n" + json_encode(built) + "\n";
    learn_prompt += "SHIPPED:\n" + json_encode(shipped) + "\n";
    learn_prompt += "Return cycle_path, scorecard_after, next_bet, still_kills[], axis_delta.\n";
    learn_prompt += "Be honest: if no axis moved, say so — stall detection depends on it.\n";

    let learn_r = agent(learn_prompt, #{
        label: "learn-c" + cycle_num.to_string(),
        capability_mode: "all",
        output_schema: learn_schema,
    });

    let learned = #{
        cycle_path: "",
        scorecard_after: stock.scorecard,
        next_bet: "unknown",
        still_kills: stock.killers,
        axis_delta: "unknown",
    };
    if learn_r != () && learn_r.success && learn_r.output != () {
        learned = learn_r.output;
    }

    let moved = learned.axis_delta != "none" && learned.axis_delta != "0" && learned.axis_delta != "unknown";
    // crude stall: if delta string explicitly says no movement
    if learned.axis_delta == "none" || learned.axis_delta == "0" || learned.axis_delta == "no change" {
        stall_count += 1;
    } else {
        stall_count = 0;
    }

    cycle_results.push(#{
        cycle: cycle_num,
        bet: selected.bet_id,
        status: "completed",
        pr: shipped.pr_url,
        merged: shipped.merged,
        cycle_path: learned.cycle_path,
        next_bet: learned.next_bet,
        axis_delta: learned.axis_delta,
    });

    log("learn path=" + learned.cycle_path + " next=" + learned.next_bet
        + " delta=" + learned.axis_delta);

    if stall_count >= 2 {
        await_user("no_progress", "Two consecutive cycles without axis movement. Reframe vision or pause flywheel.");
        stall_count = 0;
    }

    // budget check before another cycle
    let bud = budget();
    if bud.remaining < 20 {
        log("agent budget low remaining=" + bud.remaining.to_string() + " — stopping cycle loop");
        break;
    }

    cycle_i += 1;
}

let report = #{
    summary: "flywheel finished " + cycle_results.len().to_string() + " cycle record(s)",
    cycles: cycle_results,
    auto_merge: auto_merge,
    dry_run: dry_run,
    north_star: "agent independence + scalable commerce + lifecycle enrichment (L0 hub aspiration)",
    protocol: "docs/program/INNOVATION_LOOP.md",
};

let report_path = write_scratch_file("flywheel-report.json", json_encode(report));
log("wrote " + report_path);
complete(#{
    path: report_path,
    report: report,
});
