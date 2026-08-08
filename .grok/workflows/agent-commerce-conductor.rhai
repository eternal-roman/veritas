// Conductor — AUTONOMOUS confer, trajectory, recursive builder (no human gates)
// Spec: docs/program/CONDUCTOR.md · AUTONOMOUS.md
//
// Args:
//   continuous  bool  default true
//   max_cycles  int   default 3, hard-cap 6
//   prefer_bet  string optional
//   dry_run     bool  default false
//   auto_merge  bool  default true

let meta = #{
    name: "agent-commerce-conductor",
    description: "Autonomous review, conferral, trajectory, build+merge cycles — no human-in-the-loop",
    when_to_use: "Unattended A2A momentum; after merges; continuous recurse",
    phases: [
        #{ title: "Confer", detail: "Read cards + main + PRs; merge green if needed" },
        #{ title: "Trajectory", detail: "Update vision + conferral" },
        #{ title: "Cycle", detail: "Build or merge existing" },
        #{ title: "Recurse", detail: "Continue without human pause" },
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
        "merge_action": #{ "type": "string" },
        "product_pr": #{ "type": "string" },
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
        "merged": #{ "type": "boolean" },
    },
};

let continuous = true;
let max_cycles = 3;
let prefer_bet = "";
let dry_run = false;
let auto_merge = true;
if args != () {
    if args.continuous != () { continuous = args.continuous; }
    if args.max_cycles != () { max_cycles = args.max_cycles; }
    if args.prefer_bet != () { prefer_bet = args.prefer_bet; }
    if args.dry_run != () { dry_run = args.dry_run; }
    if args.auto_merge != () { auto_merge = args.auto_merge; }
}
if max_cycles < 1 { max_cycles = 1; }
if max_cycles > 6 { max_cycles = 6; }

log("conductor AUTONOMOUS continuous=" + continuous.to_string()
    + " max_cycles=" + max_cycles.to_string()
    + " auto_merge=" + auto_merge.to_string()
    + " prefer_bet=" + prefer_bet);

let cycle_i = 0;
let results = [];

while cycle_i < max_cycles {
    let n = cycle_i + 1;
    log("=== conductor cycle " + n.to_string() + " ===");

    phase("Confer");
    let conf_p = "";
    conf_p += "### WINDOWS PWSH: no bare head/grep/tail.\n\n";
    conf_p += "You are Veritas CONDUCTOR AUTONOMOUS (CONDUCTOR.md + AUTONOMOUS.md).\n";
    conf_p += "Stock: git fetch; origin/main; gh pr list --state open; read all CURRENT cards;\n";
    conf_p += "CONFERRAL/TRAJECTORY/STATE NEXT; flywheel-claim.md.\n";
    conf_p += "AUTONOMOUS rules:\n";
    conf_p += "- If product PR is CI green + mergeable: merge_action=merge (you may note URL); restart can be false for build but merge is required.\n";
    conf_p += "- If product PR CI pending: merge_action=wait_ci; restart=false.\n";
    conf_p += "- If no product PR and NEXT clear: restart=true.\n";
    conf_p += "- Docs-only PRs do not freeze product restart; merge them if green when convenient.\n";
    conf_p += "- Never dual product bets. prefer_bet=" + prefer_bet + "\n";
    conf_p += "Write conferral_md, trajectory_md, current_md. momentum 0-3.\n";
    conf_p += "Return main_sha, open_prs[], primary_bet, restart, restart_reason, momentum,\n";
    conf_p += "merge_action (none|merge|wait_ci), product_pr, markdown fields.\n";

    let conf_r = agent(conf_p, #{
        label: "conductor-confer-" + n.to_string(),
        capability_mode: "execute",
        output_schema: confer_schema,
    });

    if conf_r == () || !conf_r.success || conf_r.output == () {
        log("AUTONOMOUS: confer failed — skip cycle");
        results.push(#{ cycle: n, status: "confer_failed" });
        cycle_i += 1;
        continue;
    }
    let conf = conf_r.output;
    log("momentum=" + conf.momentum.to_string() + " restart=" + conf.restart.to_string()
        + " bet=" + conf.primary_bet);

    phase("Trajectory");
    let tr_p = "";
    tr_p += "### WINDOWS PWSH.\n";
    tr_p += "Write conductor artifacts:\n" + json_encode(conf) + "\n";
    tr_p += "1. docs/program/conductor/CONFERRAL.md\n";
    tr_p += "2. TRAJECTORY.md 3. CURRENT.md 4. append log/NNN.md\n";
    tr_p += "Note AUTONOMOUS mode (no human gates).\n";
    let _tr = agent(tr_p, #{
        label: "conductor-write-" + n.to_string(),
        capability_mode: "all",
    });

    if dry_run {
        results.push(#{ cycle: n, status: "dry_run", bet: conf.primary_bet });
        break;
    }

    phase("Cycle");

    // Merge green product PR first (autonomous)
    let merge_action = "";
    if conf.merge_action != () { merge_action = conf.merge_action; }
    let product_pr = "";
    if conf.product_pr != () { product_pr = conf.product_pr; }

    if merge_action == "merge" || (product_pr != "" && conf.restart != true) {
        let merge_p = "";
        merge_p += "### WINDOWS PWSH.\n";
        merge_p += "AUTONOMOUS merge gate. product_pr hint: " + product_pr + "\n";
        merge_p += "List open PRs. For each green product PR for STATE NEXT / primary bet "
            + conf.primary_bet + ": squash-merge if CI SUCCESS and mergeable.\n";
        merge_p += "Also squash-merge green docs PRs that only touch docs/program if they do not conflict.\n";
        merge_p += "Never merge red. Update STATE NEXT after product merge if tip advanced.\n";
        merge_p += "Return success, status (merged|wait_ci|noop|blocked), summary, pr_url, merged bool.\n";
        let merge_r = agent(merge_p, #{
            label: "conductor-merge-" + n.to_string(),
            capability_mode: "all",
            output_schema: cycle_schema,
        });
        let mst = "noop";
        let mpr = "";
        let mok = false;
        if merge_r != () && merge_r.success && merge_r.output != () {
            if merge_r.output.status != () { mst = merge_r.output.status; }
            if merge_r.output.pr_url != () { mpr = merge_r.output.pr_url; }
            mok = merge_r.output.success == true;
            if merge_r.output.merged == true { mst = "merged"; mok = true; }
        }
        results.push(#{ cycle: n, phase: "merge", status: mst, pr: mpr, success: mok, bet: conf.primary_bet });
        if mst == "merged" {
            // LEARN after merge then recurse
            let _lr = agent(
                "After autonomous merge of " + mpr + ": refresh conductor CURRENT, STATE NEXT, clear flywheel-claim if free.",
                #{ label: "conductor-learn-merge-" + n.to_string(), capability_mode: "all" }
            );
            let budm = budget();
            if continuous != true || budm.remaining < 25 { break; }
            cycle_i += 1;
            continue;
        }
        if mst == "wait_ci" {
            // Poll once more then next cycle — no human
            let poll = agent(
                "Poll CI for open product PR; squash-merge if green. Return cycle schema.",
                #{ label: "conductor-poll-" + n.to_string(), capability_mode: "all", output_schema: cycle_schema }
            );
            if poll != () && poll.success && poll.output != () && poll.output.merged == true {
                results.push(#{ cycle: n, phase: "poll_merge", status: "merged", pr: poll.output.pr_url });
                cycle_i += 1;
                continue;
            }
            log("still wait_ci — continue to next conductor cycle without human");
            cycle_i += 1;
            continue;
        }
    }

    if conf.restart != true {
        log("no restart: " + conf.restart_reason);
        results.push(#{
            cycle: n,
            status: "wait",
            reason: conf.restart_reason,
            bet: conf.primary_bet,
        });
        // Autonomous: do not break forever — next cycle may see merge or clear queue
        if continuous != true {
            break;
        }
        cycle_i += 1;
        continue;
    }

    let build_p = "";
    build_p += "### WINDOWS PWSH.\n\n";
    build_p += "ONE autonomous flywheel-style BUILD under Conductor for bet: " + conf.primary_bet + "\n";
    build_p += "Read GUARDIAN.md, AUTONOMOUS.md, STATE.md, CONFERRAL.md.\n";
    build_p += "If green product PR already open for this bet: merge it (do not dual build).\n";
    build_p += "Else: branch from main; tests first; battery; push; open PR; if auto_merge="
        + auto_merge.to_string() + " and CI green: squash-merge.\n";
    build_p += "Honor flywheel-claim.md (G10). Never force-push main. Never merge red.\n";
    build_p += "Return success, status (shipped|merged|noop|blocked), summary, pr_url, branch, merged, blocked_reason.\n";

    let build_r = agent(build_p, #{
        label: "conductor-build-" + n.to_string(),
        capability_mode: "all",
        output_schema: cycle_schema,
    });

    let st = "blocked";
    let summary = "build agent failed";
    let pr = "";
    let ok = false;
    let merged = false;
    if build_r != () && build_r.success && build_r.output != () {
        ok = build_r.output.success == true;
        if build_r.output.status != () { st = build_r.output.status; }
        if build_r.output.summary != () { summary = build_r.output.summary; }
        if build_r.output.pr_url != () { pr = build_r.output.pr_url; }
        if build_r.output.merged == true { merged = true; st = "merged"; ok = true; }
    }
    log("cycle status=" + st + " pr=" + pr + " merged=" + merged.to_string());
    results.push(#{
        cycle: n,
        status: st,
        success: ok,
        summary: summary,
        pr: pr,
        merged: merged,
        bet: conf.primary_bet,
    });

    if st == "blocked" || ok != true {
        log("AUTONOMOUS: build blocked — record and continue next cycle (no human)");
        cycle_i += 1;
        continue;
    }

    let learn_p = "";
    learn_p += "Update cycles/ if shipped/merged; refresh conductor CURRENT; honest STATE NEXT.\n";
    learn_p += "Bet " + conf.primary_bet + " status=" + st + " pr=" + pr + " merged=" + merged.to_string() + "\n";
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
    // NO await_user — if PR open unmerged, next cycle merge/poll handles it
    if pr != "" && !merged && (st == "shipped" || st == "completed_open") {
        log("PR open unmerged — next cycle will poll/merge (autonomous)");
    }
    cycle_i += 1;
}

let report = #{
    summary: "autonomous conductor finished " + results.len().to_string() + " cycle(s)",
    results: results,
    continuous: continuous,
    auto_merge: auto_merge,
    autonomous: true,
    human_gates: false,
    protocol: "docs/program/CONDUCTOR.md + AUTONOMOUS.md",
};
let path = write_scratch_file("conductor-report.json", json_encode(report));
complete(#{ path: path, report: report });
