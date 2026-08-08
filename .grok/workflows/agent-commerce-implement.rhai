// Scalable N implementers under ONE product bet → integrate → Pruner → ship
// Spec: docs/program/IMPLEMENTERS.md · PRODUCT_ORG.md · PRUNER.md · AUTONOMOUS.md
//
// Args:
//   n           int    default 3, hard-cap 6
//   prefer_bet  string default "M7"
//   auto_merge  bool   default true
//   dry_run     bool   default false

let meta = #{
    name: "agent-commerce-implement",
    description: "Scale N code workers on one STATE NEXT bet; integrate; Pruner QA; auto-merge green",
    when_to_use: "Larger bets (M7/N0); parallel implementation without dual NEXT; self-organized delivery",
    phases: [
        #{ title: "Plan", detail: "Shard one bet into n non-overlapping packages" },
        #{ title: "Implement", detail: "Parallel workers" },
        #{ title: "Integrate", detail: "Reconcile + battery" },
        #{ title: "Prune", detail: "Aggressive QA ship gate" },
        #{ title: "Ship", detail: "PR + auto-merge on green" },
    ],
};

let plan_schema = #{
    "type": "object",
    "required": ["bet_id", "branch_name", "packages", "acceptance"],
    "properties": #{
        "bet_id": #{ "type": "string" },
        "branch_name": #{ "type": "string" },
        "acceptance": #{ "type": "array", "maxItems": 10, "items": #{ "type": "string" } },
        "packages": #{
            "type": "array",
            "maxItems": 6,
            "items": #{
                "type": "object",
                "required": ["id", "title", "files", "tests"],
                "properties": #{
                    "id": #{ "type": "string" },
                    "title": #{ "type": "string" },
                    "files": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
                    "tests": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
                },
            },
        },
    },
};

let worker_schema = #{
    "type": "object",
    "required": ["package_id", "success", "summary", "files_touched"],
    "properties": #{
        "package_id": #{ "type": "string" },
        "success": #{ "type": "boolean" },
        "summary": #{ "type": "string" },
        "files_touched": #{ "type": "array", "maxItems": 20, "items": #{ "type": "string" } },
        "tests_added": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
        "blocked_reason": #{ "type": "string" },
    },
};

let integ_schema = #{
    "type": "object",
    "required": ["success", "branch", "summary", "battery_green"],
    "properties": #{
        "success": #{ "type": "boolean" },
        "branch": #{ "type": "string" },
        "summary": #{ "type": "string" },
        "battery_green": #{ "type": "boolean" },
        "blocked_reason": #{ "type": "string" },
    },
};

let prune_schema = #{
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

let n = 3;
let prefer_bet = "M7";
let auto_merge = true;
let dry_run = false;
if args != () {
    if args.n != () { n = args.n; }
    if args.prefer_bet != () { prefer_bet = args.prefer_bet; }
    if args.auto_merge != () { auto_merge = args.auto_merge; }
    if args.dry_run != () { dry_run = args.dry_run; }
}
if n < 1 { n = 1; }
if n > 6 { n = 6; }

log("implement n=" + n.to_string() + " bet=" + prefer_bet + " auto_merge=" + auto_merge.to_string());

// ===== PLAN =====
phase("Plan");
let plan_p = "";
plan_p += "### WINDOWS PWSH SAFETY.\n\n";
plan_p += "PLAN for scalable implementers. ONE bet only. Read STATE.md, GUARDIAN.md, PRODUCT_ORG.md, PRUNER.md.\n";
plan_p += "prefer_bet=" + prefer_bet + " worker_count=" + n.to_string() + "\n";
plan_p += "Shard into exactly " + n.to_string() + " packages with NON-OVERLAPPING files arrays.\n";
plan_p += "Each package: id, title, files[], tests[] (tests-first). Acceptance for whole bet.\n";
plan_p += "branch_name feat/ or fix/ kebab. No second engine/payer. Necessary slices only.\n";
plan_p += "If prefer_bet already on main, still plan only remaining gap or empty packages with note.\n";
plan_p += "Return bet_id, branch_name, acceptance[], packages[n].\n";

let plan_r = agent(plan_p, #{
    label: "impl-plan",
    capability_mode: "read-only",
    output_schema: plan_schema,
});

if plan_r == () || !plan_r.success || plan_r.output == () {
    complete(#{
        path: write_scratch_file("implement-report.json", json_encode(#{ success: false, reason: "plan_failed" })),
        report: #{ success: false, reason: "plan_failed" },
    });
}
let plan = plan_r.output;
let packages = plan.packages;
if packages == () || packages.len() == 0 {
    complete(#{
        path: write_scratch_file("implement-report.json", json_encode(#{ success: false, reason: "no_packages" })),
        report: #{ success: false, reason: "no_packages" },
    });
}
// Cap to n
let pkg_count = packages.len();
if pkg_count > n { pkg_count = n; }
log("packages=" + pkg_count.to_string() + " branch=" + plan.branch_name);

if dry_run {
    complete(#{
        path: write_scratch_file("implement-report.json", json_encode(#{ dry_run: true, plan: plan })),
        report: #{ dry_run: true, bet: plan.bet_id, packages: pkg_count },
    });
}

// Claim
let _cl = agent(
    "Write docs/program/flywheel-claim.md: bet=" + plan.bet_id
        + " branch=" + plan.branch_name + " holder=agent-commerce-implement status=building n="
        + n.to_string(),
    #{ label: "impl-claim", capability_mode: "all" }
);

// ===== IMPLEMENT (parallel N) =====
phase("Implement");
let jobs = [];
let wi = 0;
while wi < pkg_count {
    let pkg = packages[wi];
    let wp = "";
    wp += "### WINDOWS PWSH SAFETY.\n\n";
    wp += "IMPLEMENTER worker " + (wi + 1).to_string() + "/" + pkg_count.to_string() + "\n";
    wp += "Single bet " + plan.bet_id + " branch " + plan.branch_name + "\n";
    wp += "PACKAGE:\n" + json_encode(pkg) + "\n";
    wp += "Whole-bet acceptance:\n" + json_encode(plan.acceptance) + "\n";
    wp += "Rules: ONLY touch package.files (and their tests). Tests first. GUARDIAN one engine/payer.\n";
    wp += "No soft-fail. No dual NEXT. No bloat — Pruner will delete junk.\n";
    wp += "Checkout/create branch if needed; commit locally. Do not open PR.\n";
    wp += "Return package_id, success, summary, files_touched[], tests_added[], blocked_reason.\n";
    jobs.push(#{
        prompt: wp,
        label: "impl-worker-" + (wi + 1).to_string(),
        capability_mode: "all",
        output_schema: worker_schema,
    });
    wi += 1;
}

let worker_results = parallel(jobs);
let ok_workers = 0;
let fail_workers = 0;
let worker_summaries = [];
for wr in worker_results {
    if wr == () || !wr.success || wr.output == () {
        fail_workers += 1;
        worker_summaries.push("slot_failed");
    } else {
        if wr.output.success == true {
            ok_workers += 1;
        } else {
            fail_workers += 1;
        }
        worker_summaries.push(wr.output.package_id + ":" + wr.output.summary);
    }
}
log("workers ok=" + ok_workers.to_string() + " fail=" + fail_workers.to_string());

if ok_workers == 0 {
    complete(#{
        path: write_scratch_file("implement-report.json", json_encode(#{
            success: false,
            reason: "all_workers_failed",
            workers: worker_summaries,
        })),
        report: #{ success: false, reason: "all_workers_failed", workers: worker_summaries },
    });
}

// ===== INTEGRATE =====
phase("Integrate");
let ig = "";
ig += "### WINDOWS PWSH SAFETY.\n\n";
ig += "INTEGRATOR for bet " + plan.bet_id + " branch " + plan.branch_name + "\n";
ig += "Worker results:\n" + json_encode(worker_summaries) + "\n";
ig += "Plan:\n" + json_encode(plan) + "\n";
ig += "Reconcile conflicts; wire cross-file; remove duplicate helpers; keep one engine.\n";
ig += "Run full battery. success=false if red. Commit integrate.\n";
ig += "Return success, branch, summary, battery_green, blocked_reason.\n";

let ig_r = agent(ig, #{
    label: "impl-integrate",
    capability_mode: "all",
    output_schema: integ_schema,
});

if ig_r == () || !ig_r.success || ig_r.output == () || ig_r.output.success != true {
    complete(#{
        path: write_scratch_file("implement-report.json", json_encode(#{
            success: false,
            reason: "integrate_failed",
            workers: worker_summaries,
        })),
        report: #{ success: false, reason: "integrate_failed", workers: worker_summaries },
    });
}
let branch = ig_r.output.branch;
if branch == () || branch == "" { branch = plan.branch_name; }

// ===== PRUNER GATE =====
phase("Prune");
let prp = "";
prp += "### WINDOWS PWSH SAFETY.\n\n";
prp += "PRUNER gate (PRUNER.md) on branch " + branch + " bet " + plan.bet_id + "\n";
prp += "AGGRESSIVE: delete bloat from multi-worker residue; refine; full battery; E2E claims.\n";
prp += "ship_ok=true only if LEAN and battery_green and no broken claims.\n";
prp += "Write pruner/CURRENT.md + log. Return verdict, ship_ok, summary, battery_green, property_block, pruned[].\n";

let pr_r = agent(prp, #{
    label: "impl-pruner",
    capability_mode: "all",
    output_schema: prune_schema,
});

if pr_r == () || !pr_r.success || pr_r.output == () || pr_r.output.ship_ok != true {
    let why = "pruner_blocked";
    if pr_r != () && pr_r.success && pr_r.output != () {
        why = pr_r.output.summary;
    }
    complete(#{
        path: write_scratch_file("implement-report.json", json_encode(#{
            success: false,
            reason: "pruner_blocked",
            detail: why,
            branch: branch,
            workers: worker_summaries,
        })),
        report: #{ success: false, reason: "pruner_blocked", branch: branch },
    });
}
let property_block = pr_r.output.property_block;

// ===== SHIP =====
phase("Ship");
let sp = "";
sp += "### WINDOWS PWSH SAFETY.\n\n";
sp += "SHIP branch " + branch + " bet " + plan.bet_id + " after Pruner ship_ok.\n";
sp += "PROPERTY:\n" + property_block + "\n";
sp += "Push; open PR; poll CI; auto_merge=" + auto_merge.to_string() + " squash if green.\n";
sp += "Never merge red. Clear flywheel-claim on merge. Return pr_url, pr_number, merged, ci_green, notes.\n";

let sh_r = agent(sp, #{
    label: "impl-ship",
    capability_mode: "all",
    output_schema: ship_schema,
});

let shipped = #{ pr_url: "", pr_number: 0, merged: false, ci_green: false, notes: "ship_failed" };
if sh_r != () && sh_r.success && sh_r.output != () {
    shipped = sh_r.output;
}

// LEARN light
let _ln = agent(
    "If merged, update STATE NEXT honestly and cycles/ note for " + plan.bet_id
        + " pr=" + shipped.pr_url + ". Clear claim if free.",
    #{ label: "impl-learn", capability_mode: "all" }
);

let report = #{
    success: true,
    bet: plan.bet_id,
    n: n,
    workers_ok: ok_workers,
    workers_fail: fail_workers,
    worker_summaries: worker_summaries,
    branch: branch,
    pr: shipped.pr_url,
    merged: shipped.merged == true,
    ci_green: shipped.ci_green == true,
    pruner_ship_ok: true,
    autonomous: true,
    protocol: "docs/program/IMPLEMENTERS.md",
};
let path = write_scratch_file("implement-report.json", json_encode(report));
complete(#{ path: path, report: report });
