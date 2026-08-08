// Scaled org pulse — parallel support gates → serial Conductor kick
// Spec: docs/program/PRODUCT_ORG.md · GOVERNING.md · AUTONOMOUS.md
//
// Args:
//   prefer_bet  string  default "" (Conductor uses STATE NEXT)
//   skip_scout  bool    default false — still run scout if Overseer needs confer
//   dry_run     bool    default false

let meta = #{
    name: "agent-commerce-pulse",
    description: "Scaled A2A org heartbeat: parallel Overseer+Steward+Scout skim, then Conductor merge/build for STATE NEXT",
    when_to_use: "Default interactive org run; after merge; when scaling support agents without dual product bets",
    phases: [
        #{ title: "Support", detail: "Parallel quality, cohesion, ideas" },
        #{ title: "Orchestrate", detail: "Conductor merge or single-bet kick" },
    ],
};

let support_schema = #{
    "type": "object",
    "required": ["role", "ok", "summary"],
    "properties": #{
        "role": #{ "type": "string" },
        "ok": #{ "type": "boolean" },
        "summary": #{ "type": "string" },
        "vision": #{ "type": "integer" },
        "strategy": #{ "type": "integer" },
        "confer_scout": #{ "type": "boolean" },
        "directive": #{ "type": "string" },
        "cohesion": #{ "type": "integer" },
        "primary_bet": #{ "type": "string" },
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
        "merged": #{ "type": "boolean" },
        "blocked_reason": #{ "type": "string" },
    },
};

let prefer_bet = "";
let skip_scout = false;
let dry_run = false;
if args != () {
    if args.prefer_bet != () { prefer_bet = args.prefer_bet; }
    if args.skip_scout != () { skip_scout = args.skip_scout; }
    if args.dry_run != () { dry_run = args.dry_run; }
}

log("pulse start prefer_bet=" + prefer_bet + " dry_run=" + dry_run.to_string());

// ===== SUPPORT FAN-OUT (scale agents here, not dual product) =====
phase("Support");

let jobs = [];

let over_p = "";
over_p += "### WINDOWS PWSH SAFETY.\n";
over_p += "OVERSEER pulse (GOVERNING + OVERSEER.md). Stock main, STATE NEXT, open PRs, IDEA_BUS.\n";
over_p += "Score honesty + vision + strategy. Quality: functioning/necessary/pursuant.\n";
over_p += "Write overseer/CURRENT.md + log brief. Prefer single NEXT (M7 era unless STATE says else).\n";
over_p += "Return role=overseer, ok, summary, vision, strategy, confer_scout, directive, primary_bet.\n";
jobs.push(#{
    prompt: over_p,
    label: "pulse-overseer",
    capability_mode: "all",
    output_schema: support_schema,
});

let ste_p = "";
ste_p += "### WINDOWS PWSH SAFETY.\n";
ste_p += "STEWARD pulse. Stock git/gh. Fix card contradictions vs origin/main. STATE claim hygiene only.\n";
ste_p += "Do not implement product. Write steward/CURRENT + log. cohesion 0-3.\n";
ste_p += "Return role=steward, ok, summary, cohesion, primary_bet from STATE.\n";
jobs.push(#{
    prompt: ste_p,
    label: "pulse-steward",
    capability_mode: "all",
    output_schema: support_schema,
});

if skip_scout != true {
    let sc_p = "";
    sc_p += "### WINDOWS PWSH SAFETY.\n";
    sc_p += "SCOUT/IDEA pulse skim. Read overseer/CURRENT if present for scout_question.\n";
    sc_p += "If question or thin harvest: refresh IDEA_BUS top WATCH for A2A commerce (M7 credits, N0, G9 measure).\n";
    sc_p += "Never set NEXT. Return role=scout, ok, summary.\n";
    jobs.push(#{
        prompt: sc_p,
        label: "pulse-scout",
        capability_mode: "all",
        output_schema: support_schema,
    });
}

// Pruner skim — flag bloat on open product PR (apply light; full gate on implement/flywheel)
let pr_p = "";
pr_p += "### WINDOWS PWSH SAFETY.\n";
pr_p += "PRUNER pulse skim (PRUNER.md). Inspect open product PR or claim branch.\n";
pr_p += "If obvious bloat/broken claims: apply safe deletes or comment; write pruner/CURRENT.\n";
pr_p += "ship_ok only if surface is lean+green or no product surface. Return role=pruner, ok, summary, directive.\n";
jobs.push(#{
    prompt: pr_p,
    label: "pulse-pruner",
    capability_mode: "all",
    output_schema: support_schema,
});

let support = parallel(jobs);
let support_notes = [];
let confer = false;
let directive = "";
let bet = prefer_bet;
for s in support {
    if s == () || !s.success || s.output == () {
        support_notes.push("support_slot_failed");
    } else {
        support_notes.push(s.output.role + ":" + s.output.summary);
        if s.output.confer_scout == true { confer = true; }
        if s.output.directive != () && s.output.directive != "" {
            directive = s.output.directive;
        }
        if (bet == "" || bet == ()) && s.output.primary_bet != () && s.output.primary_bet != "" {
            bet = s.output.primary_bet;
        }
    }
}
if bet == "" { bet = "M7"; }
log("support done bet=" + bet + " confer_scout=" + confer.to_string());
log("directive=" + directive);

if dry_run {
    complete(#{
        path: write_scratch_file("pulse-report.json", json_encode(#{
            dry_run: true,
            support: support_notes,
            bet: bet,
            directive: directive,
        })),
        report: #{ dry_run: true, bet: bet, support: support_notes },
    });
}

// If scout confer requested but scout was weak, one focused idea pass
if confer {
    let idea = "";
    idea += "### WINDOWS PWSH.\n";
    idea += "Overseer requested Idea conferral. Read overseer/CURRENT scout_question.\n";
    idea += "Harvest 5-10 <10★ patterns for that question + M7/N0 A2A commerce. Update IDEA_BUS.\n";
    idea += "WATCH only. Return role=scout_deep, ok, summary.\n";
    let _idea = agent(idea, #{
        label: "pulse-scout-deep",
        capability_mode: "all",
        output_schema: support_schema,
    });
}

// ===== ORCHESTRATE (single product path) =====
phase("Orchestrate");
let cond = "";
cond += "### WINDOWS PWSH SAFETY.\n\n";
cond += "CONDUCTOR pulse — AUTONOMOUS. Read GOVERNING, PRODUCT_ORG, CONFERRAL, Overseer CURRENT, STATE.\n";
cond += "prefer_bet=" + bet + "\n";
cond += "Overseer directive (honor unless git/gh contradicts): " + directive + "\n\n";
cond += "1. Squash-merge any green product PR for NEXT (and green docs if clean).\n";
cond += "2. Else if CI pending: poll once; merge if green.\n";
cond += "3. Else if queue clear: kick ONE bet for prefer_bet/STATE NEXT.\n";
cond += "   Prefer multi-worker path: plan+implement n=3 non-overlapping packages OR single flywheel cycle.\n";
cond += "   MUST pass Pruner ship_ok (G13) before PR/merge. tests, battery, auto-merge on green.\n";
cond += "4. G10 flywheel-claim. Never dual product. Never merge red. Never force-push main.\n";
cond += "5. Write conductor CURRENT/CONFERRAL/TRAJECTORY briefly.\n";
cond += "Return success, status (merged|shipped|wait_ci|noop|blocked), summary, pr_url, merged.\n";

let cond_r = agent(cond, #{
    label: "pulse-conductor",
    capability_mode: "all",
    output_schema: cycle_schema,
});

let st = "blocked";
let sum = "conductor failed";
let pr = "";
let merged = false;
let ok = false;
if cond_r != () && cond_r.success && cond_r.output != () {
    ok = cond_r.output.success == true;
    if cond_r.output.status != () { st = cond_r.output.status; }
    if cond_r.output.summary != () { sum = cond_r.output.summary; }
    if cond_r.output.pr_url != () { pr = cond_r.output.pr_url; }
    if cond_r.output.merged == true { merged = true; st = "merged"; ok = true; }
}

let report = #{
    autonomous: true,
    bet: bet,
    support: support_notes,
    directive: directive,
    status: st,
    summary: sum,
    pr: pr,
    merged: merged,
    success: ok,
    protocol: "docs/program/PRODUCT_ORG.md",
};
let path = write_scratch_file("pulse-report.json", json_encode(report));
log("pulse complete status=" + st);
complete(#{ path: path, report: report });
