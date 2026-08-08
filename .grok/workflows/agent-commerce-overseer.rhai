// Agent Commerce Overseer — quality + objectivity + vision + strategy gate.
// Spec: GOVERNING.md · OVERSEER.md · GUARDIAN.md
// Cadence: every 10m durable scheduler; this workflow is interactive form.

let meta = #{
    name: "agent-commerce-overseer",
    description: "Top-tier quality/vision/strategy gate: honesty scores, vision health, Scout conferral, redirect thrash",
    when_to_use: "Standing product self-government; when work may drift; before endorsing a bet",
    phases: [
        #{ title: "Stock", detail: "Governing loops, tree, STATE, IDEA_BUS, PRs" },
        #{ title: "Judge", detail: "Quality + honesty + vision/strategy scores" },
        #{ title: "Steer", detail: "Write CURRENT + log; Scout question if vision thin" },
    ],
};

let review_schema = #{
    "type": "object",
    "required": ["verdict", "scores", "happening", "lazy", "strategic_note", "directive", "do_not", "property_block", "vision", "strategy", "confer_scout"],
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
        "vision": #{ "type": "integer" },
        "strategy": #{ "type": "integer" },
        "confer_scout": #{ "type": "boolean" },
        "scout_question": #{ "type": "string" },
        "idea_synthesis": #{ "type": "string" },
        "functioning": #{ "type": "boolean" },
        "necessary": #{ "type": "boolean" },
        "pursuant": #{ "type": "boolean" },
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
stock_prompt += "You are the Veritas OVERSEER — top-tier quality/objectivity/vision/strategy gate.\n";
stock_prompt += "Read GOVERNING.md, OVERSEER.md, GUARDIAN.md, INNOVATION_LOOP.md, STATE.md, OVERSEER_TICK_PROMPT.md.\n";
stock_prompt += "Also: overseer/CURRENT, steward/CURRENT, conductor/CONFERRAL+TRAJECTORY, scout/IDEA_BUS,\n";
stock_prompt += "cycles/*, git status/log, open PRs. Never invent.\n\n";
stock_prompt += "Governing loops set goals. You judge: functioning (tests/CI), necessary (not vanity),\n";
stock_prompt += "pursuant (A2A commerce trajectory / scorecard A-F / STATE NEXT).\n";
stock_prompt += "Strategy order: money real → product worth → independence → discovery → lifecycle.\n";
stock_prompt += "Score vision 0-3 and strategy 0-3. If either <=1: confer_scout=true + scout_question;\n";
stock_prompt += "read IDEA_BUS and put idea_synthesis (hypotheses only, WATCH not approve).\n";
stock_prompt += "Detect lazy/half-measured/theater. Prefer STATE NEXT unless severity outranks.\n\n";
stock_prompt += "Return: verdict, scores{}, vision, strategy, confer_scout, scout_question, idea_synthesis,\n";
stock_prompt += "functioning, necessary, pursuant, happening, lazy, lazy_proof, strategic_note, directive,\n";
stock_prompt += "do_not[], branch, property_block, pr_comment_needed, pr_url.\n";
stock_prompt += "Fail closed on thin evidence. Never claim multibillion outcomes as proven.\n";

let review_r = agent(stock_prompt, #{
    label: "overseer-judge",
    capability_mode: "read-only",
    output_schema: review_schema,
});

if review_r == () || !review_r.success || review_r.output == () {
    // AUTONOMOUS: no human pause — complete with failure so next tick retries
    complete(#{
        path: write_scratch_file("overseer-report.json", json_encode(#{
            success: false,
            reason: "judge_failed",
            autonomous: true,
        })),
        report: #{ success: false, reason: "judge_failed" },
    });
}

let review = review_r.output;
log("overseer verdict=" + review.verdict + " lazy=" + review.lazy.to_string());
log("directive: " + review.directive);

phase("Steer");
let steer_prompt = "";
steer_prompt += "### WINDOWS PWSH SAFETY.\n\n";
steer_prompt += "Write overseer artifacts from this review JSON (do not soften the verdict):\n";
steer_prompt += json_encode(review) + "\n\n";
steer_prompt += "1. Overwrite docs/program/overseer/CURRENT.md per OVERSEER.md contract INCLUDING\n";
steer_prompt += "   vision/strategy scores, quality gate (functioning/necessary/pursuant),\n";
steer_prompt += "   Confer Scout? / Scout question / Idea synthesis.\n";
steer_prompt += "2. Create docs/program/overseer/log/NNN-brief.md (next free NNN).\n";
steer_prompt += "3. If pr_comment_needed and pr_url set, short factual PR comment via gh if available.\n";
steer_prompt += "4. Do not merge. Do not force-push. Do not invent green.\n";
steer_prompt += "5. Guardian-class one-line integrity fix + test only if finishable this tick.\n";
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
