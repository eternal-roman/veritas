// Continuous autonomous momentum + Optimizer every 5 cycles (forever capable)
// Spec: AUTONOMOUS.md · OPTIMIZER.md · CONDUCTOR.md · PRODUCT_ORG.md
//
// Args:
//   max_cycles       int   product cycles per segment (default 5); hard-cap 32 per segment
//   forever          bool  default true — after segment + optimize, start another segment until budget dies
//   prefer_bet       string default "M7"
//   auto_merge       bool  default true
//   optimize_every   int   default 5
//   n_implementers   int   default 3 — when building, prefer implement path hint

let meta = #{
    name: "agent-commerce-continuous",
    description: "Forever-capable multi-cycle A2A delivery; Optimizer self-improves org every 5 cycles",
    when_to_use: "Unattended continuous commerce progress + continuous plane self-improvement",
    phases: [
        #{ title: "Deliver", detail: "Merge/build product cycles" },
        #{ title: "Optimize", detail: "Every N cycles: org/latency/momentum improvements" },
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

let opt_schema = #{
    "type": "object",
    "required": ["product_score", "latency_score", "momentum_score", "summary", "changes_applied", "next_experiment", "property_block"],
    "properties": #{
        "product_score": #{ "type": "integer" },
        "latency_score": #{ "type": "integer" },
        "momentum_score": #{ "type": "integer" },
        "summary": #{ "type": "string" },
        "changes_applied": #{ "type": "array", "maxItems": 16, "items": #{ "type": "string" } },
        "next_experiment": #{ "type": "string" },
        "property_block": #{ "type": "string" },
    },
};

let max_cycles = 5;
let forever = true;
let prefer_bet = "M7";
let auto_merge = true;
let optimize_every = 5;
let n_implementers = 3;
if args != () {
    if args.max_cycles != () { max_cycles = args.max_cycles; }
    if args.forever != () { forever = args.forever; }
    if args.prefer_bet != () { prefer_bet = args.prefer_bet; }
    if args.auto_merge != () { auto_merge = args.auto_merge; }
    if args.optimize_every != () { optimize_every = args.optimize_every; }
    if args.n_implementers != () { n_implementers = args.n_implementers; }
}
if max_cycles < 1 { max_cycles = 1; }
if max_cycles > 32 { max_cycles = 32; }
if optimize_every < 1 { optimize_every = 5; }
if optimize_every > 20 { optimize_every = 20; }
if n_implementers < 1 { n_implementers = 1; }
if n_implementers > 6 { n_implementers = 6; }

log("continuous forever=" + forever.to_string()
    + " max_cycles/segment=" + max_cycles.to_string()
    + " optimize_every=" + optimize_every.to_string()
    + " prefer=" + prefer_bet);

let results = [];
let optimize_logs = [];
let total = 0;
let since_opt = 0;
let segment = 0;
let keep_going = true;

while keep_going {
    segment += 1;
    let i = 0;
    log("=== segment " + segment.to_string() + " ===");

    while i < max_cycles {
        let n = total + 1;
        phase("Deliver");
        log("continuous product cycle " + n.to_string()
            + " (segment " + segment.to_string() + " local " + (i + 1).to_string() + ")");

        // Increment cycle counter file via agent (lightweight)
        let _cnt = agent(
            "Update docs/program/optimizer/CYCLE_COUNT.md: increment total_product_cycles and since_last_optimize by 1. Keep optimize_every="
                + optimize_every.to_string() + ". Do not run full optimize.",
            #{ label: "cont-count-" + n.to_string(), capability_mode: "all" }
        );

        let conf_p = "";
        conf_p += "### WINDOWS PWSH SAFETY.\n";
        conf_p += "CONDUCTOR continuous AUTONOMOUS cycle " + n.to_string() + ".\n";
        conf_p += "Read GOVERNING, PRODUCT_ORG, OPTIMIZER, AUTONOMOUS, CONDUCTOR, Overseer CURRENT, Pruner CURRENT, STATE.\n";
        conf_p += "prefer_bet=" + prefer_bet + " n_implementers=" + n_implementers.to_string() + "\n";
        conf_p += "Merge green product PRs. restart=true if safe to build. Honor Pruner G13 before ship.\n";
        conf_p += "Write conferral_md, trajectory_md, current_md. momentum 0-3.\n";

        let conf_r = agent(conf_p, #{
            label: "cont-confer-" + n.to_string(),
            capability_mode: "execute",
            output_schema: confer_schema,
        });
        if conf_r == () || !conf_r.success || conf_r.output == () {
            log("confer failed — skip pass");
            results.push(#{ pass: n, status: "confer_failed" });
            total += 1;
            since_opt += 1;
            i += 1;
        } else {
            let conf = conf_r.output;

            let _w = agent(
                "Write docs/program/conductor/{CONFERRAL,TRAJECTORY,CURRENT}.md from:\n"
                    + json_encode(conf) + "\nAppend log. Note continuous cycle " + n.to_string() + ".\n",
                #{ label: "cont-write-" + n.to_string(), capability_mode: "all" }
            );

            let merge_p = "";
            merge_p += "### WINDOWS PWSH.\n";
            merge_p += "AUTONOMOUS squash-merge green PRs (product first for "
                + conf.primary_bet + ", then docs). Never merge red.\n";
            merge_p += "Return success, status, summary, pr_url, merged.\n";
            let merge_r = agent(merge_p, #{
                label: "cont-merge-" + n.to_string(),
                capability_mode: "all",
                output_schema: cycle_schema,
            });

            let did_merge = false;
            if merge_r != () && merge_r.success && merge_r.output != () && merge_r.output.merged == true {
                did_merge = true;
                results.push(#{
                    pass: n,
                    status: "merged",
                    pr: merge_r.output.pr_url,
                    bet: conf.primary_bet,
                });
                let _lm = agent(
                    "Post-merge: STATE NEXT from origin/main; refresh conductor; clear claim if free.",
                    #{ label: "cont-learn-merge-" + n.to_string(), capability_mode: "all" }
                );
            }

            if !did_merge {
                if conf.restart != true {
                    results.push(#{ pass: n, status: "wait", reason: conf.restart_reason });
                    let _poll = agent(
                        "Poll CI for open product PR; squash-merge if green. Else noop.",
                        #{ label: "cont-poll-" + n.to_string(), capability_mode: "all", output_schema: cycle_schema }
                    );
                    if _poll != () && _poll.success && _poll.output != () && _poll.output.merged == true {
                        results.push(#{ pass: n, status: "merged_after_poll", pr: _poll.output.pr_url });
                    }
                } else {
                    let b_p = "";
                    b_p += "### WINDOWS PWSH.\n";
                    b_p += "AUTONOMOUS product delivery for bet: " + conf.primary_bet + "\n";
                    b_p += "Prefer implement-style: up to " + n_implementers.to_string()
                        + " non-overlapping packages OR single flywheel cycle.\n";
                    b_p += "MUST Pruner ship_ok (G13) before PR. tests first; full battery; auto_merge="
                        + auto_merge.to_string() + ".\n";
                    b_p += "G10 claim; GUARDIAN; no dual NEXT. Return success, status, summary, pr_url, branch, merged, blocked_reason.\n";

                    let b_r = agent(b_p, #{
                        label: "cont-build-" + n.to_string(),
                        capability_mode: "all",
                        output_schema: cycle_schema,
                    });

                    let st = "blocked";
                    let pr = "";
                    let sum = "";
                    let merged = false;
                    if b_r != () && b_r.success && b_r.output != () {
                        if b_r.output.status != () { st = b_r.output.status; }
                        if b_r.output.pr_url != () { pr = b_r.output.pr_url; }
                        if b_r.output.summary != () { sum = b_r.output.summary; }
                        if b_r.output.merged == true { merged = true; st = "merged"; }
                    }
                    results.push(#{
                        pass: n,
                        status: st,
                        pr: pr,
                        summary: sum,
                        merged: merged,
                        bet: conf.primary_bet,
                    });
                    if st == "blocked" {
                        log("blocked: " + sum + " — continue continuous loop");
                    }
                }
            }

            total += 1;
            since_opt += 1;
            i += 1;
        }

        // ===== OPTIMIZE every N product cycles =====
        if since_opt >= optimize_every {
            phase("Optimize");
            log("OPTIMIZER pass after " + total.to_string() + " product cycles (mandate: continuous self-improvement)");
            let op = "";
            op += "### WINDOWS PWSH SAFETY.\n\n";
            op += "OPTIMIZER AUTHORITY (OPTIMIZER.md). Continuous self-improvement — no end state.\n";
            op += "After " + total.to_string() + " product cycles. Results so far:\n";
            op += json_encode(results) + "\n\n";
            op += "Improve product outcomes, reduce latency, improve scalable momentum.\n";
            op += "EDIT CONTINUOUS.md, PRODUCT_ORG.md, .grok/workflows/* as warranted.\n";
            op += "Do not weaken Guardian/G13/one NEXT. Write optimizer/CURRENT + log; reset since_last_optimize=0 in CYCLE_COUNT.\n";
            op += "Return scores, summary, changes_applied[], next_experiment, property_block.\n";

            let op_r = agent(op, #{
                label: "cont-optimize-" + total.to_string(),
                capability_mode: "all",
                output_schema: opt_schema,
            });
            if op_r != () && op_r.success && op_r.output != () {
                optimize_logs.push(#{
                    after_cycle: total,
                    product_score: op_r.output.product_score,
                    latency_score: op_r.output.latency_score,
                    momentum_score: op_r.output.momentum_score,
                    summary: op_r.output.summary,
                    changes: op_r.output.changes_applied,
                    next_experiment: op_r.output.next_experiment,
                });
                log("optimize: " + op_r.output.summary);
            } else {
                optimize_logs.push(#{ after_cycle: total, status: "optimize_failed" });
            }
            since_opt = 0;
        }

        let bud = budget();
        if bud.remaining < 35 {
            log("budget low remaining=" + bud.remaining.to_string() + " — stop continuous");
            keep_going = false;
            break;
        }
    }

    if forever != true {
        keep_going = false;
    } else {
        // forever: another segment until budget death (checked inside loop too)
        let bud2 = budget();
        if bud2.remaining < 40 {
            log("forever stop: budget low after segment");
            keep_going = false;
        } else {
            log("forever: starting next segment (continuous self-improvement mandate)");
        }
    }
}

complete(#{
    path: write_scratch_file("continuous-report.json", json_encode(#{
        results: results,
        optimize_logs: optimize_logs,
        total_product_cycles: total,
        forever: forever,
        optimize_every: optimize_every,
        autonomous: true,
        human_gates: false,
        auto_merge: auto_merge,
        continuous_self_improvement: true,
        protocol: "docs/program/OPTIMIZER.md",
    })),
    report: #{
        summary: "continuous finished total_cycles=" + total.to_string(),
        results: results,
        optimize_logs: optimize_logs,
        forever: forever,
    },
});
