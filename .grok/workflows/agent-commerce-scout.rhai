// Idea agent (Scout) — pattern fuel for Overseer vision
// Spec: GOVERNING.md · SCOUT_TICK_PROMPT.md

let meta = #{
    name: "agent-commerce-scout",
    description: "Idea harvest for A2A commerce vision; answers Overseer scout_question; never sets NEXT",
    when_to_use: "When Overseer vision is thin; scheduled idea pass; pulse deep scout",
    phases: [
        #{ title: "Harvest", detail: "Low-star OSS + Overseer question" },
        #{ title: "Publish", detail: "IDEA_BUS + CURRENT + log" },
    ],
};

let out_schema = #{
    "type": "object",
    "required": ["success", "seedling_count", "top_watch", "answered_overseer", "notes"],
    "properties": #{
        "success": #{ "type": "boolean" },
        "seedling_count": #{ "type": "integer" },
        "top_watch": #{ "type": "array", "maxItems": 5, "items": #{ "type": "string" } },
        "answered_overseer": #{ "type": "boolean" },
        "notes": #{ "type": "string" },
    },
};

phase("Harvest");
let p = "";
p += "### WINDOWS PWSH SAFETY.\n";
p += "You are Veritas Idea agent (Scout). Read SCOUT_TICK_PROMPT.md, GOVERNING.md, overseer/CURRENT.md.\n";
p += "If confer_scout or scout_question set, prioritise that question.\n";
p += "Harvest <10★ tools for A2A commerce (credits/SIWx, payments, custody, discovery, notary, metering).\n";
p += "WATCH not approve. Never set STATE NEXT. Never implement product.\n";
p += "Write scout/IDEA_BUS.md (include ## Response to Overseer if asked), CURRENT.md, log/NNN.md.\n";
p += "Return success, seedling_count, top_watch[], answered_overseer, notes.\n";

let r = agent(p, #{
    label: "scout-harvest",
    capability_mode: "all",
    output_schema: out_schema,
});

phase("Publish");
if r == () || !r.success || r.output == () {
    complete(#{
        path: write_scratch_file("scout-report.json", json_encode(#{ success: false })),
        report: #{ success: false },
    });
}

complete(#{
    path: write_scratch_file("scout-report.json", json_encode(r.output)),
    report: r.output,
});
