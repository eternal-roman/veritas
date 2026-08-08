// Continuous recurse wrapper — Conductor with multi-cycle momentum
// Prefer: /workflow agent-commerce-continuous {"max_cycles": 3}
//
// This is the "keep going after finish" entrypoint. It runs the conductor
// loop (confer → trajectory → build cycle → reframe → again).

let meta = #{
    name: "agent-commerce-continuous",
    description: "Recursive agent-commerce momentum: confer all agents, update trajectory, ship cycles until max or block",
    when_to_use: "Keep Veritas flywheel recursing after each finished cycle; organized multi-agent advance",
    phases: [
        #{ title: "Continuous", detail: "Delegate to conductor continuous loop" },
    ],
};

// Inline the conductor continuous path by running confer+build agents in a loop
// (duplicated lightly so this name is discoverable as the "always on" workflow).

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

let max_cycles = 3;
let prefer_bet = "O.8";
if args != () {
    if args.max_cycles != () { max_cycles = args.max_cycles; }
    if args.prefer_bet != () { prefer_bet = args.prefer_bet; }
}
if max_cycles < 1 { max_cycles = 1; }
if max_cycles > 4 { max_cycles = 4; }

log("continuous momentum max_cycles=" + max_cycles.to_string() + " prefer=" + prefer_bet);

let results = [];
let i = 0;
while i < max_cycles {
    let n = i + 1;
    phase("Continuous");
    log("continuous pass " + n.to_string());

    let conf_p = "";
    conf_p += "### WINDOWS PWSH SAFETY.\n";
    conf_p += "CONDUCTOR continuous pass " + n.to_string() + ". Read CONDUCTOR.md.\n";
    conf_p += "Stock git/gh; read steward/overseer/scout/peer/STATE/cycles/conductor cards.\n";
    conf_p += "prefer_bet=" + prefer_bet + ". restart=true only if no open product PR and tree safe.\n";
    conf_p += "Write conferral_md, trajectory_md, current_md. momentum 0-3.\n";

    let conf_r = agent(conf_p, #{
        label: "cont-confer-" + n.to_string(),
        capability_mode: "execute",
        output_schema: confer_schema,
    });
    if conf_r == () || !conf_r.success || conf_r.output == () {
        pause("infra", "Continuous confer failed.");
    }
    let conf = conf_r.output;

    let w_p = "Write docs/program/conductor/{CONFERRAL,TRAJECTORY,CURRENT}.md from:\n"
        + json_encode(conf) + "\nAppend conductor/log/NNN.md. GUARDIAN holds.\n";
    let _w = agent(w_p, #{ label: "cont-write-" + n.to_string(), capability_mode: "all" });

    if conf.restart != true {
        results.push(#{ pass: n, status: "wait", reason: conf.restart_reason });
        await_user("user", "Continuous wait: " + conf.restart_reason
            + ". Merge open PR or clear WIP, then resume to recurse.");
        // after resume, continue loop
        i += 1;
        continue;
    }

    let b_p = "";
    b_p += "### WINDOWS PWSH SAFETY.\n";
    b_p += "ONE flywheel cycle for bet: " + conf.primary_bet + "\n";
    b_p += "tests first; battery; PR no merge; one engine; GUARDIAN.\n";
    b_p += "Return success, status, summary, pr_url, branch, blocked_reason.\n";

    let b_r = agent(b_p, #{
        label: "cont-build-" + n.to_string(),
        capability_mode: "all",
        output_schema: cycle_schema,
    });

    let st = "blocked";
    let pr = "";
    let sum = "";
    if b_r != () && b_r.success && b_r.output != () {
        if b_r.output.status != () { st = b_r.output.status; }
        if b_r.output.pr_url != () { pr = b_r.output.pr_url; }
        if b_r.output.summary != () { sum = b_r.output.summary; }
    }
    results.push(#{ pass: n, status: st, pr: pr, summary: sum, bet: conf.primary_bet });

    if st == "shipped" && pr != "" {
        await_user("user", "Continuous opened " + pr + ". Merge when CI green, resume for next cycle.");
    } else if st == "blocked" {
        await_user("verification", "Continuous blocked: " + sum);
        break;
    }

    let bud = budget();
    if bud.remaining < 30 { break; }
    i += 1;
}

complete(#{
    path: write_scratch_file("continuous-report.json", json_encode(#{ results: results })),
    report: #{ summary: "continuous passes done", results: results },
});
