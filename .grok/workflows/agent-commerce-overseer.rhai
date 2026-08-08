// Agent Commerce Overseer — honesty + strategy + course-correction review.
// Spec: docs/program/OVERSEER.md  ·  Rules: docs/program/GUARDIAN.md
// Cadence: every 15m via durable scheduler; this workflow is the interactive form.

let meta = #{
    name: "agent-commerce-overseer",
    description: "15m-class overseer: review WIP honesty, A2A strategy, redirect lazy/misguided work",
    when_to_use: "When work may be drifting, before merge, or to run an overseer pass interactively",
    phases: [
        #{ title: "Stock", detail: "Tree, STATE, PRs, prior CURRENT" },
        #{ title: "Judge", detail: "Rubric scores + verdict" },
        #{ title: "Steer", detail: "Write CURRENT + log; optional PR comment" },
    ],
};

let review_schema = #{
    "type": "object",
    "required": ["verdict", "scores", "happening", "lazy", "strategic_note", "directive", "do_not", "property_block"],
    "properties": #{
        "verdict": #{ "type": "string" },
        "scores": #{
            "type": "object",
            "required": ["on_task", "measured", "integrity", "a2a", "claims"],
            "properties": #{
                "on_task": #{ "type": "integer" },
                "measured": #{ "type": "integer" },
                "integrity": #{ "type": "integer" },
                "a2a": #{ "type": "integer" },
                "claims": #{ "type": "integer" },
            },
        },
        "happening": #{ "type": "string" },
        "lazy": #{ "type": "boolean" },
        "lazy_proof": #{ "type": "string" },
        "strategic_note": #{ "type": "string" },
        "directive": #{ "type": "string" },
        "do_not": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
        "branch": #{ "type": "string" },
        "property_block": #{ "type": "string" },
        "pr_comment_needed": #{ "type": "boolean" },
        "pr_url": #{ "type": "string" },
    },
};

let write_schema = #{
    "type": "object",
    "required": ["success", "current_path", "log_path", "notes"],
    "properties": #{
        "success": #{ "type": "boolean" },
        "current_path": #{ "type": "string" },
        "log_path": #{ "type": "string" },
        "notes": #{ "type": "string" },
        "pr_commented": #{ "type": "boolean" },
    },
};

phase("Stock");
let stock_prompt = "";
stock_prompt += "### WINDOWS PWSH: no bare head/grep/tail; use Select-Object -First N.\n\n";
stock_prompt += "You are the Veritas OVERSEER (docs/program/OVERSEER.md).\n";
stock_prompt += "Read with tools — never invent:\n";
stock_prompt += "1. docs/program/OVERSEER.md, GUARDIAN.md, STATE.md, OVERSEER_TICK_PROMPT.md\n";
stock_prompt += "2. docs/program/overseer/CURRENT.md if present; cycles/000-baseline.md; latest cycle\n";
stock_prompt += "3. git status -sb; branch; log --oneline -12; diff --stat if dirty\n";
stock_prompt += "4. Open PRs if gh/GitHub available\n";
stock_prompt += "5. If WIP claims O.6 or similar, spot-check tests exist for the claim (e.g. 410 Gone)\n\n";
stock_prompt += "Judge against agent-to-agent commerce value: money real → product worth → independence → discovery → lifecycle.\n";
stock_prompt += "Detect lazy/half-measured/theater. Prefer STATE NEXT ACTION unless severity outranks it.\n\n";
stock_prompt += "Return JSON: verdict (ON_TASK|DRIFT|LAZY|MISGUIDED|BLOCKED), scores 0-3 each,\n";
stock_prompt += "happening, lazy bool + lazy_proof, strategic_note, directive, do_not[], branch,\n";
stock_prompt += "property_block (full gate text), pr_comment_needed, pr_url if any.\n";
stock_prompt += "Fail closed on thin evidence: do not cheerlead.\n";

let review_r = agent(stock_prompt, #{
    label: "overseer-judge",
    capability_mode: "read-only",
    output_schema: review_schema,
});

if review_r == () || !review_r.success || review_r.output == () {
    pause("infra", "Overseer stock/judge failed — cannot steer without reading the tree.");
}

let review = review_r.output;
log("overseer verdict=" + review.verdict + " lazy=" + review.lazy.to_string());
log("directive: " + review.directive);

phase("Steer");
let steer_prompt = "";
steer_prompt += "### WINDOWS PWSH SAFETY.\n\n";
steer_prompt += "Write overseer artifacts from this review JSON (do not soften the verdict):\n";
steer_prompt += json_encode(review) + "\n\n";
steer_prompt += "1. Overwrite docs/program/overseer/CURRENT.md per OVERSEER.md output contract.\n";
steer_prompt += "2. Create docs/program/overseer/log/NNN-brief.md with next NNN after existing log files.\n";
steer_prompt += "3. If pr_comment_needed and pr_url set, leave a short factual PR comment via gh if available.\n";
steer_prompt += "4. Do not merge. Do not force-push. Do not invent green.\n";
steer_prompt += "5. Only if verdict implies a guardian-class one-line integrity bug with a test you can finish now — otherwise no code drive-by.\n";
steer_prompt += "Return success, current_path, log_path, notes, pr_commented.\n";

let write_r = agent(steer_prompt, #{
    label: "overseer-write",
    capability_mode: "all",
    output_schema: write_schema,
});

// Fail closed on missing write in spirit, but do not hang the run: still emit the
// verdict so a human/scheduler sees the judgment. Live agents should write CURRENT.
let wrote = false;
let current_path = "";
let log_path = "";
let write_notes = "write_agent_failed";
if write_r != () && write_r.success && write_r.output != () {
    if write_r.output.success == true {
        wrote = true;
    }
    if write_r.output.current_path != () {
        current_path = write_r.output.current_path;
    }
    if write_r.output.log_path != () {
        log_path = write_r.output.log_path;
    }
    if write_r.output.notes != () {
        write_notes = write_r.output.notes;
    }
}
if !wrote {
    log("WARNING: overseer artifacts may not have been written: " + write_notes);
}

let report = #{
    verdict: review.verdict,
    directive: review.directive,
    current: current_path,
    log: log_path,
    lazy: review.lazy,
    wrote_artifacts: wrote,
    write_notes: write_notes,
    property_block: review.property_block,
};

let path = write_scratch_file("overseer-report.json", json_encode(report));
complete(#{ path: path, report: report });
