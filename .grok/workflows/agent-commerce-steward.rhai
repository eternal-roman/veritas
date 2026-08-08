// Steward — card hygiene, STATE cohesion, cooperative momentum
// Spec: docs/program/STEWARD.md

let meta = #{
    name: "agent-commerce-steward",
    description: "Clean agent cards, refresh STATE claim hygiene, maintain multi-agent cohesion",
    when_to_use: "Every 30m or after merges when cards may be stale",
    phases: [
        #{ title: "Stock", detail: "git/gh truth vs cards" },
        #{ title: "Align", detail: "Rewrite stale CURRENT cards" },
        #{ title: "Report", detail: "Steward CURRENT + log" },
    ],
};

let stock_schema = #{
    "type": "object",
    "required": ["main_sha", "open_prs", "contradictions", "next_action", "cohesion_score"],
    "properties": #{
        "main_sha": #{ "type": "string" },
        "open_prs": #{ "type": "array", "maxItems": 20, "items": #{ "type": "string" } },
        "contradictions": #{ "type": "array", "maxItems": 15, "items": #{ "type": "string" } },
        "next_action": #{ "type": "string" },
        "cohesion_score": #{ "type": "integer" },
        "retention_on_main": #{ "type": "boolean" },
        "notes": #{ "type": "string" },
    },
};

let write_schema = #{
    "type": "object",
    "required": ["success", "cards_rewritten", "steward_path", "log_path"],
    "properties": #{
        "success": #{ "type": "boolean" },
        "cards_rewritten": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
        "steward_path": #{ "type": "string" },
        "log_path": #{ "type": "string" },
        "momentum_directive": #{ "type": "string" },
        "notes": #{ "type": "string" },
    },
};

phase("Stock");
let stock_prompt = "";
stock_prompt += "### WINDOWS PWSH: no bare head/grep/tail.\n\n";
stock_prompt += "You are Veritas STEWARD (docs/program/STEWARD.md). Stock truth with tools:\n";
stock_prompt += "1. git fetch; git log origin/main --oneline -8\n";
stock_prompt += "2. git cat-file origin/main:veritas/retention.py (exists?)\n";
stock_prompt += "3. gh pr list --state open\n";
stock_prompt += "4. Read overseer/CURRENT.md, steward/CURRENT.md, peer/CURRENT.md, STATE.md NEXT, scout/IDEA_BUS.md if present, cycles/\n";
stock_prompt += "5. List contradictions between cards and git/gh.\n";
stock_prompt += "Return main_sha, open_prs[], contradictions[], next_action, cohesion_score 0-3, retention_on_main, notes.\n";

let stock_r = agent(stock_prompt, #{
    label: "steward-stock",
    capability_mode: "execute",
    output_schema: stock_schema,
});

if stock_r == () || !stock_r.success || stock_r.output == () {
    // AUTONOMOUS: no human pause — complete so next tick retries
    complete(#{
        path: write_scratch_file("steward-report.json", json_encode(#{
            success: false,
            reason: "stock_failed",
            autonomous: true,
        })),
        report: #{ success: false, reason: "stock_failed" },
    });
}
let stock = stock_r.output;
log("cohesion=" + stock.cohesion_score.to_string() + " main=" + stock.main_sha);

phase("Align");
let align_prompt = "";
align_prompt += "### WINDOWS PWSH SAFETY.\n\n";
align_prompt += "STEWARD ALIGN: fix contradictions. Stock JSON:\n" + json_encode(stock) + "\n\n";
align_prompt += "Rewrite as needed:\n";
align_prompt += "- docs/program/overseer/CURRENT.md (must match main/PRs)\n";
align_prompt += "- docs/program/overseer/peer/CURRENT.md (IDLE if no peer PR)\n";
align_prompt += "- docs/program/steward/CURRENT.md (full contract)\n";
align_prompt += "- docs/program/overseer/log/INDEX.md if logs are messy\n";
align_prompt += "- STATE.md ONLY for claim hygiene (SHAs for landed work) — do not jump ladder silently\n";
align_prompt += "Append docs/program/steward/log/NNN.md\n";
align_prompt += "Do not implement product features. Do not merge.\n";
align_prompt += "Return success, cards_rewritten[], steward_path, log_path, momentum_directive, notes.\n";

let write_r = agent(align_prompt, #{
    label: "steward-align",
    capability_mode: "all",
    output_schema: write_schema,
});

let ok = false;
let cards = [];
let steward_path = "docs/program/steward/CURRENT.md";
let log_path = "";
let directive = "";
if write_r != () && write_r.success && write_r.output != () {
    if write_r.output.success == true { ok = true; }
    if write_r.output.cards_rewritten != () && type_of(write_r.output.cards_rewritten) == "array" {
        cards = write_r.output.cards_rewritten;
    }
    if write_r.output.steward_path != () { steward_path = write_r.output.steward_path; }
    if write_r.output.log_path != () { log_path = write_r.output.log_path; }
    if write_r.output.momentum_directive != () { directive = write_r.output.momentum_directive; }
}
if !ok { log("WARNING: steward write incomplete"); }

phase("Report");
let report = #{
    cohesion: stock.cohesion_score,
    main: stock.main_sha,
    open_prs: stock.open_prs,
    cards_rewritten: cards,
    directive: directive,
    steward: steward_path,
    log: log_path,
    wrote: ok,
};
let path = write_scratch_file("steward-report.json", json_encode(report));
complete(#{ path: path, report: report });
