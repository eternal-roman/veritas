// Agent Commerce Innovation Flywheel — AUTONOMOUS (no human-in-the-loop)
// Spec: docs/program/INNOVATION_LOOP.md · GUARDIAN.md · AUTONOMOUS.md
//
// Args (all optional):
//   max_cycles   int   default 3, hard-capped at 6
//   auto_merge   bool  default true  — merge when CI green + audits clean
//   prefer_bet   string optional forced selection (e.g. "M7")
//   dry_run      bool  default false — stock+score+select+plan only
//   max_audit_rounds int default 3, hard-capped at 4

let meta = #{
    name: "agent-commerce-flywheel",
    description: "Autonomous commerce innovation cycle: stock, short-circuit open PRs, build, bounded audit, verify, PR+auto-merge, learn, recurse — no human gates",
    when_to_use: "Unattended multi-cycle agent-commerce improvement; after a merge; scheduled builder",
    phases: [
        #{ title: "Stock", detail: "Inventory + open-PR short-circuit + claim" },
        #{ title: "Select", detail: "One bet; ladder default" },
        #{ title: "Build", detail: "Plan, implement, tests first" },
        #{ title: "Audit", detail: "Bounded adversarial + over-engineering (minors advisory)" },
        #{ title: "Ship", detail: "Verify, PR, auto-merge on green CI" },
        #{ title: "Learn", detail: "Cycle report, STATE, reframe next" },
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

let gate_schema = #{
    "type": "object",
    "required": ["action", "reason"],
    "properties": #{
        "action": #{ "type": "string" },
        "reason": #{ "type": "string" },
        "pr_url": #{ "type": "string" },
        "pr_number": #{ "type": "integer" },
        "ci_green": #{ "type": "boolean" },
        "merged": #{ "type": "boolean" },
        "claim_holder": #{ "type": "string" },
        "same_bet_branch": #{ "type": "string" },
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

// --- helpers ---

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
            next_action: "",
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
        next_action: as_str(raw.next_action, ""),
        excellence: as_list(raw.excellence),
        killers: as_list(raw.killers),
        open_critical: as_list(raw.open_critical),
        scorecard: normalize_scorecard(sc),
    }
}

fn normalize_selected(raw, prefer) {
    if raw == () {
        let bid = prefer;
        if bid == "" { bid = "NEXT"; }
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
        if bid == "" { bid = "NEXT"; }
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

fn is_blocking_severity(sev) {
    let s = as_str(sev, "minor");
    if s == "blocker" { return true; }
    if s == "major" { return true; }
    if s == "BLOCKER" { return true; }
    if s == "MAJOR" { return true; }
    false
}

// --- args ---

let max_cycles = 3;
let auto_merge = true;
let prefer_bet = "";
let dry_run = false;
let max_audit_rounds = 3;

if args != () {
    if args.max_cycles != () { max_cycles = args.max_cycles; }
    if args.auto_merge != () { auto_merge = args.auto_merge; }
    if args.prefer_bet != () { prefer_bet = args.prefer_bet; }
    if args.dry_run != () { dry_run = args.dry_run; }
    if args.max_audit_rounds != () { max_audit_rounds = args.max_audit_rounds; }
}

if max_cycles < 1 { max_cycles = 1; }
if max_cycles > 6 { max_cycles = 6; }
if max_audit_rounds < 1 { max_audit_rounds = 1; }
if max_audit_rounds > 4 { max_audit_rounds = 4; }

log("flywheel AUTONOMOUS max_cycles=" + max_cycles.to_string()
    + " auto_merge=" + auto_merge.to_string()
    + " max_audit_rounds=" + max_audit_rounds.to_string()
    + " dry_run=" + dry_run.to_string()
    + " prefer_bet=" + prefer_bet);

let cycle_results = [];
let cycle_i = 0;
let stall_count = 0;

while cycle_i < max_cycles {
    let cycle_num = cycle_i + 1;
    log("=== autonomous cycle " + cycle_num.to_string() + " of " + max_cycles.to_string() + " ===");

    // ========== STOCK ==========
    phase("Stock");
    let stock_prompt = "";
    stock_prompt += "### WINDOWS PWSH: no bare head/grep/tail/find. Truncate with Select-Object.\n\n";
    stock_prompt += "STOCK phase — Veritas agent-commerce flywheel (AUTONOMOUS).\n";
    stock_prompt += "Read docs/program/GUARDIAN.md and docs/program/AUTONOMOUS.md.\n";
    stock_prompt += "With tools (do not invent):\n";
    stock_prompt += "1. docs/program/STATE.md NEXT ACTION\n";
    stock_prompt += "2. docs/program/INNOVATION_LOOP.md scorecard axes\n";
    stock_prompt += "3. docs/program/cycles/* latest + 000-baseline\n";
    stock_prompt += "4. git fetch; git log origin/main --oneline -12; git status\n";
    stock_prompt += "5. docs/program/flywheel-claim.md if present\n\n";
    stock_prompt += "Return head_sha, next_action (exact from STATE), excellence[], killers[], open_critical[],\n";
    stock_prompt += "scorecard A-F integers. Axis C stays 0 without a tx hash.\n";

    let stock_r = agent(stock_prompt, #{
        label: "stock-c" + cycle_num.to_string(),
        capability_mode: "read-only",
        output_schema: stock_schema,
    });

    let stock_ok = stock_r != () && stock_r.success && stock_r.output != ()
        && stock_r.output.next_action != () && stock_r.output.next_action != ""
        && stock_r.output.scorecard != ();
    if !stock_ok {
        if dry_run {
            log("stock sparse — dry_run only");
        } else {
            log("AUTONOMOUS: stock failed — skip cycle (no human pause)");
            cycle_results.push(#{ cycle: cycle_num, status: "stock_failed" });
            cycle_i += 1;
            continue;
        }
    }
    let stock_raw = ();
    if stock_r != () && stock_r.success && stock_r.output != () {
        stock_raw = stock_r.output;
    }
    let stock = normalize_stock(stock_raw);
    if !dry_run && (stock.head_sha == "unknown" || stock.next_action == "") {
        log("AUTONOMOUS: stock unusable — skip cycle");
        cycle_results.push(#{ cycle: cycle_num, status: "stock_unusable" });
        cycle_i += 1;
        continue;
    }
    log("stock next_action=" + stock.next_action);

    // ========== GATE: open PR / claim short-circuit ==========
    if !dry_run {
        let gate_prompt = "";
        gate_prompt += "### WINDOWS PWSH SAFETY.\n\n";
        gate_prompt += "PREFLIGHT GATE for autonomous flywheel. NEXT ACTION stock:\n";
        gate_prompt += json_encode(stock) + "\n\n";
        gate_prompt += "Use gh pr list --state open and gh pr view/checks. Read docs/program/flywheel-claim.md if any.\n";
        gate_prompt += "Decide action (exactly one):\n";
        gate_prompt += "- merge_existing: open PRODUCT PR for same NEXT/bet, CI all SUCCESS, mergeable → squash-merge it NOW (auto_merge autonomous).\n";
        gate_prompt += "  Docs-only PRs are not product; still may merge docs PR if green and labeled docs.\n";
        gate_prompt += "- wait_ci: product PR open, CI pending/in progress → do not start second bet; return pr_url.\n";
        gate_prompt += "- continue_same: same-bet branch exists with WIP, claim is ours or free → continue build (do not dual).\n";
        gate_prompt += "- claim_blocked: flywheel-claim.md holds a different live builder on same bet → skip.\n";
        gate_prompt += "- proceed: no product PR, claim free → new/continue build ok.\n";
        gate_prompt += "If merge_existing: actually merge with gh pr merge --squash when green; set merged=true.\n";
        gate_prompt += "Never force-push main. Never merge red CI. Never open a second product PR for same NEXT.\n";
        gate_prompt += "Return action, reason, pr_url, pr_number, ci_green, merged, claim_holder, same_bet_branch.\n";

        let gate_r = agent(gate_prompt, #{
            label: "gate-c" + cycle_num.to_string(),
            capability_mode: "all",
            output_schema: gate_schema,
        });

        let gate_action = "proceed";
        let gate_reason = "";
        let gate_pr = "";
        let gate_merged = false;
        if gate_r != () && gate_r.success && gate_r.output != () {
            gate_action = as_str(gate_r.output.action, "proceed");
            gate_reason = as_str(gate_r.output.reason, "");
            gate_pr = as_str(gate_r.output.pr_url, "");
            gate_merged = as_bool(gate_r.output.merged, false);
        }
        log("gate action=" + gate_action + " reason=" + gate_reason);

        if gate_action == "claim_blocked" {
            cycle_results.push(#{
                cycle: cycle_num,
                status: "claim_blocked",
                reason: gate_reason,
            });
            cycle_i += 1;
            continue;
        }

        if gate_action == "wait_ci" {
            // Autonomous: poll/merge agent once more instead of human wait
            let poll_p = "";
            poll_p += "### WINDOWS PWSH.\n";
            poll_p += "Product PR may be mid-CI: " + gate_pr + "\n";
            poll_p += "Poll gh pr checks until all complete (reasonable wait) or still pending.\n";
            poll_p += "If all SUCCESS and mergeable: squash-merge. Return action merge_existing or wait_ci.\n";
            poll_p += "Never merge red.\n";
            let poll_r = agent(poll_p, #{
                label: "poll-ci-c" + cycle_num.to_string(),
                capability_mode: "all",
                output_schema: gate_schema,
            });
            if poll_r != () && poll_r.success && poll_r.output != () {
                gate_action = as_str(poll_r.output.action, "wait_ci");
                gate_merged = as_bool(poll_r.output.merged, false);
                gate_pr = as_str(poll_r.output.pr_url, gate_pr);
            }
            if gate_action == "wait_ci" && !gate_merged {
                log("CI still pending — skip cycle (no human); next cycle will retry");
                cycle_results.push(#{
                    cycle: cycle_num,
                    status: "wait_ci",
                    pr: gate_pr,
                    reason: gate_reason,
                });
                cycle_i += 1;
                continue;
            }
        }

        if gate_action == "merge_existing" || gate_merged {
            // LEARN-lite after autonomous merge of existing PR
            let lm = "";
            lm += "### WINDOWS PWSH.\n";
            lm += "Existing product PR was merged or ready. AUTONOMOUS learn.\n";
            lm += "PR: " + gate_pr + " stock NEXT was: " + stock.next_action + "\n";
            lm += "Confirm origin/main tip; update STATE.md NEXT to real next (e.g. M7 after O.8);\n";
            lm += "write cycle file if missing; clear docs/program/flywheel-claim.md (claim free).\n";
            lm += "Return cycle_path, scorecard_after, next_bet, still_kills[], axis_delta.\n";
            let lm_r = agent(lm, #{
                label: "learn-merge-c" + cycle_num.to_string(),
                capability_mode: "all",
                output_schema: learn_schema,
            });
            let nb = "unknown";
            if lm_r != () && lm_r.success && lm_r.output != () {
                nb = as_str(lm_r.output.next_bet, "unknown");
            }
            cycle_results.push(#{
                cycle: cycle_num,
                status: "merged_existing",
                pr: gate_pr,
                next_bet: nb,
            });
            stall_count = 0;
            let bud0 = budget();
            if bud0.remaining < 20 { break; }
            cycle_i += 1;
            continue;
        }
        // proceed or continue_same → fall through to select/build
    }

    // ========== SELECT ==========
    phase("Select");
    let select_prompt = "";
    select_prompt += "### WINDOWS PWSH SAFETY.\n\n";
    select_prompt += "Read GUARDIAN.md + AUTONOMOUS.md. SELECT one shippable bet.\n";
    select_prompt += "STOCK:\n" + json_encode(stock) + "\n\n";
    select_prompt += "Rules: prefer STATE NEXT; one bet; testable acceptance[]; no second engine/payer;\n";
    select_prompt += "no on-chain work this sandbox cannot prove without egress.\n";
    if prefer_bet != "" {
        select_prompt += "prefer_bet=" + prefer_bet + " if still valid.\n";
    }
    if stall_count >= 1 {
        select_prompt += "Prior cycle had weak axis movement — prefer a different shippable gap if NEXT is blocked.\n";
    }
    select_prompt += "Return full select schema fields.\n";

    let select_r = agent(select_prompt, #{
        label: "select-c" + cycle_num.to_string(),
        capability_mode: "read-only",
        output_schema: select_schema,
    });

    let select_ok = select_r != () && select_r.success && select_r.output != ()
        && select_r.output.bet_id != () && select_r.output.bet_id != "";
    if !select_ok {
        if dry_run {
            log("select sparse — dry_run");
        } else {
            log("AUTONOMOUS: select failed — skip cycle");
            cycle_results.push(#{ cycle: cycle_num, status: "select_failed" });
            cycle_i += 1;
            continue;
        }
    }
    let select_raw = ();
    if select_r != () && select_r.success && select_r.output != () {
        select_raw = select_r.output;
    }
    let selected = normalize_selected(select_raw, prefer_bet);
    if !dry_run && selected.acceptance.len() == 0 {
        log("AUTONOMOUS: empty acceptance — skip cycle (no handwave)");
        cycle_results.push(#{ cycle: cycle_num, status: "empty_acceptance", bet: selected.bet_id });
        cycle_i += 1;
        continue;
    }
    log("selected " + selected.bet_id + ": " + selected.title);

    // ========== PLAN + BUILD ==========
    phase("Build");
    let plan_prompt = "";
    plan_prompt += "### WINDOWS PWSH SAFETY.\n\n";
    plan_prompt += "Write tight PLAN. Read real code. BET:\n" + json_encode(selected) + "\n";
    plan_prompt += "Tests first. No soft-fail. One engine. Return steps, tests_first, risks, branch_name.\n";

    let plan_r = agent(plan_prompt, #{
        label: "plan-c" + cycle_num.to_string(),
        capability_mode: "read-only",
        output_schema: plan_schema,
    });

    let plan_ok = plan_r != () && plan_r.success && plan_r.output != ()
        && plan_r.output.tests_first != ();
    if !plan_ok && !dry_run {
        log("AUTONOMOUS: plan failed — skip cycle");
        cycle_results.push(#{ cycle: cycle_num, status: "plan_failed", bet: selected.bet_id });
        cycle_i += 1;
        continue;
    }
    let plan_raw = ();
    if plan_r != () && plan_r.success && plan_r.output != () {
        plan_raw = plan_r.output;
    }
    let plan = normalize_plan(plan_raw);
    if !dry_run && plan.tests_first.len() == 0 {
        log("AUTONOMOUS: empty tests_first — skip cycle");
        cycle_results.push(#{ cycle: cycle_num, status: "plan_empty_tests", bet: selected.bet_id });
        cycle_i += 1;
        continue;
    }

    if dry_run {
        let dry_path = write_scratch_file(
            "cycle-" + cycle_num.to_string() + "-dry-run.json",
            json_encode(#{ stock: stock, selected: selected, plan: plan })
        );
        cycle_results.push(#{ cycle: cycle_num, dry_run: true, bet: selected.bet_id, path: dry_path });
        cycle_i += 1;
        continue;
    }

    // Claim surface (G10) — write before build
    let claim_p = "";
    claim_p += "### WINDOWS PWSH.\n";
    claim_p += "Write docs/program/flywheel-claim.md claiming this bet for autonomous flywheel:\n";
    claim_p += "bet_id=" + selected.bet_id + " branch=" + plan.branch_name + " cycle=" + cycle_num.to_string() + "\n";
    claim_p += "holder=agent-commerce-flywheel status=building\n";
    claim_p += "If claim file shows another holder actively building different branch for same bet within recent stamp, do not overwrite — report conflict in one line.\n";
    claim_p += "Otherwise write claim and return ok.\n";
    let _claim = agent(claim_p, #{
        label: "claim-c" + cycle_num.to_string(),
        capability_mode: "all",
    });

    let build_prompt = "";
    build_prompt += "### WINDOWS PWSH SAFETY (NON-NEGOTIABLE)\n";
    build_prompt += "No bare head/grep/tail/find. Truncate with Select-Object.\n\n";
    build_prompt += "BUILD for Veritas flywheel AUTONOMOUS. GUARDIAN.md.\n";
    build_prompt += "BET:\n" + json_encode(selected) + "\nPLAN:\n" + json_encode(plan) + "\n";
    build_prompt += "1. Continue existing same-bet branch if present; never dual product branch (G10).\n";
    build_prompt += "2. Tests first; implement until pass. No soft-fail.\n";
    build_prompt += "3. One engine; unavailable non-billable; money-path order.\n";
    build_prompt += "4. Do NOT open PR (ship phase does). Commit locally.\n";
    build_prompt += "5. pytest tests/ -q must pass; ruff if available.\n";
    build_prompt += "Return success, branch, summary, tests_added, files_changed, blocked_reason.\n";

    let build_r = agent(build_prompt, #{
        label: "build-c" + cycle_num.to_string(),
        capability_mode: "all",
        output_schema: build_schema,
    });

    if build_r == () || !build_r.success || build_r.output == () {
        log("AUTONOMOUS: build agent failed — skip cycle");
        cycle_results.push(#{ cycle: cycle_num, status: "build_infra_fail", bet: selected.bet_id });
        cycle_i += 1;
        continue;
    }
    let built = build_r.output;
    if !built.success {
        log("build blocked: " + as_str(built.blocked_reason, ""));
        // One autonomous rebuild attempt
        let rebuild_p = "";
        rebuild_p += "### WINDOWS PWSH.\n";
        rebuild_p += "Prior build failed: " + as_str(built.blocked_reason, "") + "\n";
        rebuild_p += "BET:\n" + json_encode(selected) + "\nPLAN:\n" + json_encode(plan) + "\n";
        rebuild_p += "Fix and complete build. Same schema return.\n";
        let rebuild_r = agent(rebuild_p, #{
            label: "rebuild-c" + cycle_num.to_string(),
            capability_mode: "all",
            output_schema: build_schema,
        });
        if rebuild_r == () || !rebuild_r.success || rebuild_r.output == () || rebuild_r.output.success != true {
            cycle_results.push(#{
                cycle: cycle_num,
                bet: selected.bet_id,
                status: "build_blocked",
                reason: as_str(built.blocked_reason, "rebuild_failed"),
            });
            cycle_i += 1;
            continue;
        }
        built = rebuild_r.output;
    }
    log("build ok branch=" + built.branch);

    // ========== AUDIT (bounded rounds; minor = advisory) ==========
    phase("Audit");
    let should_ship = false;
    let property_block = "";
    let audit_round = 0;
    let last_blockers = [];

    while audit_round < max_audit_rounds {
        audit_round += 1;
        log("audit round " + audit_round.to_string() + "/" + max_audit_rounds.to_string());

        let audit_jobs = [
            #{
                prompt: "### WINDOWS PWSH SAFETY.\n\n"
                    + "Adversarial code-truth AUDIT branch " + built.branch
                    + " bet " + selected.bet_id + ".\n"
                    + "Read skills/adversarial-code-truth.md. Inspect git diff with tools.\n"
                    + "Acceptance:\n" + json_encode(selected.acceptance) + "\n"
                    + "Severity: blocker | major | minor.\n"
                    + "CRITICAL AUTONOMOUS RULE: only severity blocker or major may populate ship_blockers.\n"
                    + "minor findings go in findings[] only — they MUST NOT set should_ship=false alone.\n"
                    + "should_ship=true if no blocker/major honesty/safety issues remain.\n"
                    + "property_block required (PROPERTY/EVIDENCE LEVEL/...). \n",
                label: "audit-truth-c" + cycle_num.to_string() + "-r" + audit_round.to_string(),
                capability_mode: "read-only",
                output_schema: audit_schema,
            },
            #{
                prompt: "### WINDOWS PWSH SAFETY.\n\n"
                    + "Over-engineering AUDIT branch " + built.branch + " bet " + selected.bet_id + ".\n"
                    + "Read GUARDIAN.md. List delete candidates in overengineering[].\n"
                    + "AUTONOMOUS: minor nits and style are NOT ship blockers.\n"
                    + "should_ship=false only for real safety/honesty/bloat that breaks maintainability of money path or dual-engine risk.\n"
                    + "You MUST inspect the diff with tools. property_block required.\n",
                label: "audit-pony-c" + cycle_num.to_string() + "-r" + audit_round.to_string(),
                capability_mode: "read-only",
                output_schema: audit_schema,
            },
        ];
        let audits = parallel(audit_jobs);

        let ship_blockers = [];
        let all_findings = [];
        let panels_ok = 0;
        let panels_needed = audits.len();
        let ai = 0;
        property_block = "";

        for a in audits {
            if a == () || !a.success || a.output == () {
                ship_blockers.push("audit_panel_failed_slot_" + ai.to_string());
            } else {
                if a.output.findings != () {
                    for f in a.output.findings {
                        all_findings.push(f);
                        if is_blocking_severity(f.severity) {
                            ship_blockers.push(f.issue);
                        }
                    }
                }
                // Only honor should_ship=false if there are real blocking findings
                // or explicit ship_blockers that are not empty
                let panel_blockers = [];
                if a.output.ship_blockers != () {
                    for b in a.output.ship_blockers {
                        panel_blockers.push(b);
                    }
                }
                // Filter empty strings
                let hard = 0;
                for b in panel_blockers {
                    if b != "" {
                        hard += 1;
                        ship_blockers.push(b);
                    }
                }
                if a.output.should_ship == true || hard == 0 {
                    // if panel said false only due to minors, still count ok when no hard blockers added from findings
                    let hard_findings = 0;
                    if a.output.findings != () {
                        for f in a.output.findings {
                            if is_blocking_severity(f.severity) {
                                hard_findings += 1;
                            }
                        }
                    }
                    if a.output.should_ship == true || (hard == 0 && hard_findings == 0) {
                        panels_ok += 1;
                    } else {
                        ship_blockers.push("panel_" + ai.to_string() + "_should_ship_false");
                    }
                } else {
                    if hard > 0 {
                        ship_blockers.push("panel_" + ai.to_string() + "_should_ship_false");
                    } else {
                        panels_ok += 1;
                    }
                }
                if property_block == "" && a.output.property_block != () {
                    property_block = a.output.property_block;
                }
            }
            ai += 1;
        }

        // Dedup-ish: empty property is soft — synthesize minimal if panels otherwise clean
        should_ship = panels_ok == panels_needed && panels_needed > 0 && ship_blockers.len() == 0;
        if property_block == "" && should_ship {
            property_block = "PROPERTY: autonomous ship for " + selected.bet_id
                + "\nEVIDENCE LEVEL: L1\nNOT PROVEN: on-chain settlement; wild install";
        }
        if property_block == "" {
            should_ship = false;
            ship_blockers.push("missing_property_gate_block");
        }

        log("audit round=" + audit_round.to_string()
            + " should_ship=" + should_ship.to_string()
            + " blockers=" + ship_blockers.len().to_string());

        last_blockers = ship_blockers;
        if should_ship {
            break;
        }

        // Fix attempt then loop
        let fix_prompt = "";
        fix_prompt += "### WINDOWS PWSH SAFETY.\n\n";
        fix_prompt += "Fix ship_blockers on branch " + built.branch + " bet " + selected.bet_id + ".\n";
        fix_prompt += "Blockers:\n" + json_encode(ship_blockers) + "\n";
        fix_prompt += "Findings:\n" + json_encode(all_findings) + "\n";
        fix_prompt += "Do not expand scope. Re-run relevant tests. Commit fix.\n";
        fix_prompt += "Return success, branch, summary, tests_added, files_changed.\n";

        let fix_r = agent(fix_prompt, #{
            label: "fix-c" + cycle_num.to_string() + "-r" + audit_round.to_string(),
            capability_mode: "all",
            output_schema: build_schema,
        });

        if fix_r == () || !fix_r.success || fix_r.output == () || fix_r.output.success != true {
            log("fix attempt failed round " + audit_round.to_string());
        } else if fix_r.output.branch != () && fix_r.output.branch != "" {
            // rebuild map with updated branch for subsequent audit/ship prompts
            built = #{
                success: true,
                branch: fix_r.output.branch,
                summary: as_str(fix_r.output.summary, built.summary),
                tests_added: as_list(fix_r.output.tests_added),
                files_changed: as_list(fix_r.output.files_changed),
                blocked_reason: "",
            };
        }
    }

    if !should_ship {
        log("AUTONOMOUS: audit exhausted — skip ship this cycle (no human gate)");
        cycle_results.push(#{
            cycle: cycle_num,
            bet: selected.bet_id,
            status: "audit_exhausted",
            blockers: last_blockers,
            branch: built.branch,
        });
        // Clear claim so another cycle can try
        let _clr = agent(
            "If docs/program/flywheel-claim.md exists for this bet, mark status=audit_exhausted or delete claim free.",
            #{ label: "claim-clear-c" + cycle_num.to_string(), capability_mode: "all" }
        );
        cycle_i += 1;
        continue;
    }

    // ========== VERIFY ==========
    phase("Ship");
    let verify_prompt = "";
    verify_prompt += "### WINDOWS PWSH SAFETY.\n\n";
    verify_prompt += "G1/G2: FULL battery. green=true ONLY if all exit 0:\n";
    verify_prompt += "1. python -m pytest tests/ -q\n";
    verify_prompt += "2. ruff check veritas tests\n";
    verify_prompt += "3. python -m veritas.evaluations.harness\n";
    verify_prompt += "4. python -m veritas.evaluations.payment_model\n";
    verify_prompt += "Do not invent green. List failures.\n";

    let verify_r = agent(verify_prompt, #{
        label: "verify-c" + cycle_num.to_string(),
        capability_mode: "execute",
        output_schema: verify_schema,
    });

    if verify_r == () || !verify_r.success || verify_r.output == () || verify_r.output.green != true {
        // One fix-verify loop autonomous
        let vf = "";
        vf += "### WINDOWS PWSH.\n";
        vf += "Verify failed. Fix tests on branch " + built.branch + " then re-run full battery.\n";
        if verify_r != () && verify_r.success && verify_r.output != () {
            vf += "Notes: " + as_str(verify_r.output.notes, "") + "\n";
        }
        vf += "Return green, commands, notes.\n";
        let verify2 = agent(vf, #{
            label: "verify2-c" + cycle_num.to_string(),
            capability_mode: "all",
            output_schema: verify_schema,
        });
        if verify2 == () || !verify2.success || verify2.output == () || verify2.output.green != true {
            log("AUTONOMOUS: verify not green — skip ship");
            cycle_results.push(#{
                cycle: cycle_num,
                bet: selected.bet_id,
                status: "verify_failed",
                branch: built.branch,
            });
            cycle_i += 1;
            continue;
        }
    }
    log("local verify green");

    // PRUNER GATE (G13) — deny bloat / non-functional before ship
    let prune_schema_fw = #{
        "type": "object",
        "required": ["verdict", "ship_ok", "summary", "battery_green", "property_block"],
        "properties": #{
            "verdict": #{ "type": "string" },
            "ship_ok": #{ "type": "boolean" },
            "summary": #{ "type": "string" },
            "battery_green": #{ "type": "boolean" },
            "property_block": #{ "type": "string" },
            "pruned": #{ "type": "array", "maxItems": 20, "items": #{ "type": "string" } },
        },
    };
    let prune_p = "";
    prune_p += "### WINDOWS PWSH SAFETY.\n\n";
    prune_p += "PRUNER gate (docs/program/PRUNER.md) before ship. Branch " + built.branch
        + " bet " + selected.bet_id + "\n";
    prune_p += "AGGRESSIVE: delete useless/bloated code/docs; refine; re-run full battery; E2E claims.\n";
    prune_p += "ship_ok=true ONLY if lean + battery_green + no broken claims. Write pruner/CURRENT.md.\n";
    prune_p += "Return verdict, ship_ok, summary, battery_green, property_block, pruned[].\n";
    let prune_r = agent(prune_p, #{
        label: "pruner-c" + cycle_num.to_string(),
        capability_mode: "all",
        output_schema: prune_schema_fw,
    });
    if prune_r == () || !prune_r.success || prune_r.output == () || prune_r.output.ship_ok != true {
        log("AUTONOMOUS: pruner blocked ship — skip cycle");
        cycle_results.push(#{
            cycle: cycle_num,
            bet: selected.bet_id,
            status: "pruner_blocked",
            branch: built.branch,
        });
        cycle_i += 1;
        continue;
    }
    if prune_r.output.property_block != () && prune_r.output.property_block != "" {
        property_block = prune_r.output.property_block;
    }
    log("pruner ship_ok");

    // SHIP + AUTO MERGE
    let ship_prompt = "";
    ship_prompt += "### WINDOWS PWSH SAFETY.\n\n";
    ship_prompt += "SHIP bet " + selected.bet_id + " branch " + built.branch + " AUTONOMOUS (Pruner ship_ok).\n";
    ship_prompt += "Summary: " + built.summary + "\n";
    ship_prompt += "PR body must include:\n" + property_block + "\n\n";
    ship_prompt += "Steps:\n";
    ship_prompt += "1. git fetch; push branch to origin.\n";
    ship_prompt += "2. Open PR to main if none exists for this branch (gh or GitHub MCP). 4C body.\n";
    ship_prompt += "3. Poll CI checks on head SHA until complete (or timeout ~15-20m of polling).\n";
    ship_prompt += "4. auto_merge=" + auto_merge.to_string() + ".\n";
    ship_prompt += "   If auto_merge true AND all required checks SUCCESS AND mergeable: squash-merge immediately.\n";
    ship_prompt += "   If CI red: push fix commits and re-poll once; if still red, merged=false.\n";
    ship_prompt += "5. Never force-push main. Never merge red. Never dual open PRs for same bet.\n";
    ship_prompt += "6. After merge: clear docs/program/flywheel-claim.md.\n";
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
        // One ship retry
        let ship2 = agent(ship_prompt, #{
            label: "ship2-c" + cycle_num.to_string(),
            capability_mode: "all",
            output_schema: ship_schema,
        });
        if ship2 != () && ship2.success && ship2.output != () {
            shipped = ship2.output;
        } else {
            log("AUTONOMOUS: ship failed — skip to next cycle");
            cycle_results.push(#{
                cycle: cycle_num,
                bet: selected.bet_id,
                status: "ship_failed",
                branch: built.branch,
            });
            cycle_i += 1;
            continue;
        }
    }
    log("PR " + as_str(shipped.pr_url, "")
        + " ci_green=" + as_bool(shipped.ci_green, false).to_string()
        + " merged=" + as_bool(shipped.merged, false).to_string());

    // If open but not merged and CI green, force merge agent
    if auto_merge && !as_bool(shipped.merged, false) && as_bool(shipped.ci_green, false) {
        let mrg = "";
        mrg += "### WINDOWS PWSH.\n";
        mrg += "PR " + as_str(shipped.pr_url, "") + " is CI green but not merged. Squash-merge now.\n";
        mrg += "Return pr_url, pr_number, merged=true if done, ci_green, notes.\n";
        let mrg_r = agent(mrg, #{
            label: "merge-c" + cycle_num.to_string(),
            capability_mode: "all",
            output_schema: ship_schema,
        });
        if mrg_r != () && mrg_r.success && mrg_r.output != () {
            shipped = mrg_r.output;
        }
    }

    // If still waiting CI, one more poll-merge then continue (no human)
    if auto_merge && !as_bool(shipped.merged, false) && as_str(shipped.pr_url, "") != "" {
        let pollm = "";
        pollm += "### WINDOWS PWSH.\n";
        pollm += "Poll CI for " + as_str(shipped.pr_url, "") + " until complete; squash-merge if green.\n";
        pollm += "Return ship schema.\n";
        let pollm_r = agent(pollm, #{
            label: "poll-merge-c" + cycle_num.to_string(),
            capability_mode: "all",
            output_schema: ship_schema,
        });
        if pollm_r != () && pollm_r.success && pollm_r.output != () {
            shipped = pollm_r.output;
        }
    }

    // ========== LEARN ==========
    phase("Learn");
    let learn_prompt = "";
    learn_prompt += "### WINDOWS PWSH.\n\n";
    learn_prompt += "LEARN autonomous: write docs/program/cycles/NNN-slug.md; update STATE.md NEXT honestly.\n";
    learn_prompt += "If PR merged, NEXT advances; if only open, say so (do not claim main tip moved).\n";
    learn_prompt += "Clear flywheel-claim if merged.\n";
    learn_prompt += "STOCK:\n" + json_encode(stock) + "\nSELECTED:\n" + json_encode(selected) + "\n";
    learn_prompt += "BUILT:\n" + json_encode(built) + "\nSHIPPED:\n" + json_encode(shipped) + "\n";
    learn_prompt += "Return cycle_path, scorecard_after, next_bet, still_kills[], axis_delta.\n";

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

    if learned.axis_delta == "none" || learned.axis_delta == "0" || learned.axis_delta == "no change" {
        stall_count += 1;
    } else if as_bool(shipped.merged, false) {
        stall_count = 0;
    } else {
        stall_count += 1;
    }

    let st_done = "completed_open";
    if as_bool(shipped.merged, false) {
        st_done = "completed_merged";
    }

    cycle_results.push(#{
        cycle: cycle_num,
        bet: selected.bet_id,
        status: st_done,
        pr: as_str(shipped.pr_url, ""),
        merged: as_bool(shipped.merged, false),
        cycle_path: as_str(learned.cycle_path, ""),
        next_bet: as_str(learned.next_bet, ""),
        axis_delta: as_str(learned.axis_delta, ""),
    });

    log("learn next=" + as_str(learned.next_bet, "") + " delta=" + as_str(learned.axis_delta, ""));

    // No human on stall — reframe next cycle via select hint
    if stall_count >= 2 {
        log("AUTONOMOUS: stall_count>=2 — next cycle will reframe (no human)");
        stall_count = 0;
    }

    // Only recurse multi-cycle when merged OR dry path; if PR open unmerged, still continue
    // so next cycle gate can merge_existing — do NOT await_user
    let bud = budget();
    if bud.remaining < 20 {
        log("budget low remaining=" + bud.remaining.to_string() + " — stop");
        break;
    }

    cycle_i += 1;
}

let report = #{
    summary: "autonomous flywheel finished " + cycle_results.len().to_string() + " cycle record(s)",
    cycles: cycle_results,
    auto_merge: auto_merge,
    dry_run: dry_run,
    autonomous: true,
    human_gates: false,
    north_star: "agent independence + scalable commerce + lifecycle enrichment (L0 hub aspiration)",
    protocol: "docs/program/INNOVATION_LOOP.md + AUTONOMOUS.md",
};

let report_path = write_scratch_file("flywheel-report.json", json_encode(report));
log("wrote " + report_path);
complete(#{
    path: report_path,
    report: report,
});
