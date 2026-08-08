// Conductor — confer, trajectory, recursive builder restart
// Spec: docs/program/CONDUCTOR.md
//
// Args:
//   continuous  bool  default true  — after one cycle, loop if budget remains
//   max_cycles  int   default 2, hard-cap 4
//   prefer_bet  string optional (e.g. "O.8")
//   dry_run     bool  default false — confer only, no build

let meta = #{
    name: "agent-commerce-conductor",
    description: "Review all work, confer with agents, maintain trajectory, recurse flywheel cycles for momentum",
    when_to_use: "After merges, when flywheel idle, continuous A2A momentum, or /conductor",
    phases: [
        #{ title: "Confer", detail: "Read all agent cards + main + PRs" },
        #{ title: "Trajectory", detail: "Update vision board and conferral" },
        #{ title: "Cycle", detail: "One build cycle if restart allowed" },
        #{ title: "Recurse", detail: "Reframe and continue if continuous" },
    ],
};

let confer_schema = #{
    "type": "object",
    "required": ["main_sha", "open_prs", "primary_bet", "restart", "momentum", "conferral_md", "trajectory_md"],
    "properties": #{
        "main_sha": #{ "type": "string" },
        "open_prs": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
        "primary_bet": #{ "type": "string" },
        "restart": #{ "type": "boolean" },
        "restart_reason": #{ "type": "string" },
        "momentum": #{ "type": "integer" },
        "steward_summary": #{ "type": "string" },
        "overseer_summary": #{ "type": "string" },
        "scout_summary": #{ "type": "string" },
        "conferral_md": #{ "type": "string" },
        "trajectory_md": #{ "type": "string" },
        "current_md": #{ "type": "string" },
    },
};

let cycle_schema = #{
    "type": "object",
    "required": ["success", "status", "summary"],
    "properties": #{
        "success": #{ "type": "boolean" },
        "status": #{ "type": "string" },
        "summary": #{ "type": "string" },
        "pr_url": #{ "type": "string" },
        "branch": #{ "type": "string" },
        "blocked_reason": #{ "type": "string" },
    },
};

// --- args ---
let continuous = true;
let max_cycles = 2;
let prefer_bet = "";
let dry_run = false;
if args != () {
    if args.continuous != () { continuous = args.continuous; }
    if args.max_cycles != () { max_cycles = args.max_cycles; }
    if args.prefer_bet != () { prefer_bet = args.prefer_bet; }
    if args.dry_run != () { dry_run = args.dry_run; }
}
if max_cycles < 1 { max_cycles = 1; }
if max_cycles > 4 { max_cycles = 4; }

log("conductor start continuous=" + continuous.to_string()
    + " max_cycles=" + max_cycles.to_string()
    + " prefer_bet=" + prefer_bet);

let cycle_i = 0;
let results = [];

while cycle_i < max_cycles {
    let n = cycle_i + 1;
    log("=== conductor cycle " + n.to_string() + " ===");

    // ===== CONFER =====
    phase("Confer");
    let conf_p = "";
    conf_p += "### WINDOWS PWSH: no bare head/grep/tail.\n\n";
    conf_p += "You are Veritas CONDUCTOR (docs/program/CONDUCTOR.md).\n";
    conf_p += "Stock with tools: git fetch; origin/main log; gh pr list; retention.py on main?\n";
    conf_p += "Read and summarize: steward/CURRENT.md, overseer/CURRENT.md, peer/CURRENT.md,\n";
    conf_p += "scout/IDEA_BUS.md, STATE.md NEXT, cycles/*, conductor/* if present.\n";
    conf_p += "Decide restart (true if no open product PR, NEXT clear, no hostile WIP clash).\n";
    conf_p += "If open green unmerged PR: restart=false, name it.\n";
    conf_p += "Primary bet: STATE NEXT or prefer_bet=" + prefer_bet + " if valid.\n";
    conf_p += "Write full markdown for conferral_md, trajectory_md, current_md.\n";
    conf_p += "Momentum 0-3. GUARDIAN: no dual bets, no fake settlement.\n";

    let conf_r = agent(conf_p, #{
        label: "conductor-confer-" + n.to_string(),
        capability_mode: "execute",
        output_schema: confer_schema,
    });

    if conf_r == () || !conf_r.success || conf_r.output == () {
        pause("infra", "Conductor confer failed.");
    }
    let conf = conf_r.output;
    log("momentum=" + conf.momentum.to_string() + " restart=" + conf.restart.to_string()
        + " bet=" + conf.primary_bet);

    // ===== TRAJECTORY WRITE =====
    phase("Trajectory");
    let tr_p = "";
    tr_p += "### WINDOWS PWSH SAFETY.\n\n";
    tr_p += "Write conductor artifacts from this conferral (do not soften):\n";
    tr_p += json_encode(conf) + "\n\n";
    tr_p += "1. docs/program/conductor/CONFERRAL.md from conferral_md\n";
    tr_p += "2. docs/program/conductor/TRAJECTORY.md from trajectory_md\n";
    tr_p += "3. docs/program/conductor/CURRENT.md from current_md\n";
    tr_p += "4. Append conductor/log/NNN.md\n";
    tr_p += "Return one line: ok or error reason.\n";

    let tr_r = agent(tr_p, #{
        label: "conductor-write-" + n.to_string(),
        capability_mode: "all",
    });
    if tr_r == () || !tr_r.success {
        log("WARNING: trajectory write weak");
    }

    if dry_run {
        results.push(#{ cycle: n, status: "dry_run", bet: conf.primary_bet });
        break;
    }

    // ===== CYCLE (restart builder) =====
    phase("Cycle");
    if conf.restart != true {
        log("no restart: " + conf.restart_reason);
        results.push(#{
            cycle: n,
            status: "wait",
            reason: conf.restart_reason,
            bet: conf.primary_bet,
        });
        // Still may continue loop only if continuous and waiting is temporary — break
        break;
    }

    let build_p = "";
    build_p += "### WINDOWS PWSH: no bare head/grep/tail; Select-Object for truncate.\n\n";
    build_p += "You execute ONE Veritas flywheel BUILD cycle under Conductor.\n";
    build_p += "Bet: " + conf.primary_bet + "\n";
    build_p += "Read GUARDIAN.md, STATE.md, conductor/CONFERRAL.md, steward/CURRENT.md.\n";
    build_p += "Process: branch from main; tests first; minimal diff; full battery before PR:\n";
    build_p += "pytest tests/ -q; ruff check veritas tests; harness; payment_model.\n";
    build_p += "Push branch; open PR to main with PROPERTY block. Do NOT merge.\n";
    build_p += "One engine; one payer; no soft-fail; no settlement claims without tx hash.\n";
    build_p += "If work already on main for this bet, status=noop with reason.\n";
    build_p += "Return success, status (shipped|noop|blocked), summary, pr_url, branch, blocked_reason.\n";

    let build_r = agent(build_p, #{
        label: "conductor-build-" + n.to_string(),
        capability_mode: "all",
        output_schema: cycle_schema,
    });

    let st = "blocked";
    let summary = "build agent failed";
    let pr = "";
    let ok = false;
    if build_r != () && build_r.success && build_r.output != () {
        ok = build_r.output.success == true;
        if build_r.output.status != () { st = build_r.output.status; }
        if build_r.output.summary != () { summary = build_r.output.summary; }
        if build_r.output.pr_url != () { pr = build_r.output.pr_url; }
    }
    log("cycle status=" + st + " pr=" + pr);
    results.push(#{
        cycle: n,
        status: st,
        success: ok,
        summary: summary,
        pr: pr,
        bet: conf.primary_bet,
    });

    if st == "blocked" || ok != true {
        if continuous {
            await_user("verification", "Conductor cycle blocked: " + summary + ". Fix or resume.");
        }
        break;
    }

    // LEARN snippet
    let learn_p = "";
    learn_p += "Update docs/program/cycles/ if a PR shipped; refresh conductor/CURRENT.md momentum;\n";
    learn_p += "honest STATE NEXT if bet landed only after merge (do not claim merged if PR open).\n";
    learn_p += "Bet was " + conf.primary_bet + " status=" + st + " pr=" + pr + "\n";
    let _lr = agent(learn_p, #{
        label: "conductor-learn-" + n.to_string(),
        capability_mode: "all",
    });

    phase("Recurse");
    if continuous != true {
        break;
    }
    let bud = budget();
    if bud.remaining < 25 {
        log("budget low — stop recurse");
        break;
    }
    // If PR open unmerged, stop recurse to avoid dual bets
    if pr != "" && st == "shipped" {
        log("PR open — pause recurse until merge (human or next conductor tick)");
        await_user("user", "Conductor opened " + pr + ". Merge when CI green, then resume to recurse.");
    }
    cycle_i += 1;
}

let report = #{
    summary: "conductor finished " + results.len().to_string() + " cycle(s)",
    results: results,
    continuous: continuous,
    protocol: "docs/program/CONDUCTOR.md",
};
let path = write_scratch_file("conductor-report.json", json_encode(report));
complete(#{ path: path, report: report });
