// Optimizer — continuous self-improvement of org / latency / momentum
// Spec: docs/program/OPTIMIZER.md
// Authority: may edit PRODUCT_ORG, CONTINUOUS, workflows (not weaken Guardian)

let meta = #{
    name: "agent-commerce-optimizer",
    description: "Every-5-cycle and on-demand: improve product outcomes, reduce latency, scale momentum; no terminal end state",
    when_to_use: "After 5 product cycles; continuous forever optimize phase; org thrash",
    phases: [
        #{ title: "Review", detail: "Stock outcomes + latency + momentum" },
        #{ title: "Apply", detail: "Edit org/cadence/workflows under Guardian" },
    ],
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
        "deferred": #{ "type": "array", "maxItems": 8, "items": #{ "type": "string" } },
        "next_experiment": #{ "type": "string" },
        "property_block": #{ "type": "string" },
    },
};

phase("Review");
phase("Apply");

let p = "";
p += "### WINDOWS PWSH SAFETY.\n\n";
p += "You are Veritas OPTIMIZER with AUTHORITY to change org/cadence/workflows.\n";
p += "Read OPTIMIZER.md, OPTIMIZER_TICK_PROMPT.md, GOVERNING.md, GUARDIAN.md, PRODUCT_ORG.md,\n";
p += "CONTINUOUS.md, overseer/CURRENT, pruner/CURRENT, conductor/CURRENT, STATE.md,\n";
p += "optimizer/CYCLE_COUNT.md, last cycle results if any.\n\n";
p += "MANDATE: continuous self-improvement — no finished org. Improve product outcomes,\n";
p += "reduce latency, improve scalable momentum toward A2A commerce (L0 multi-billion direction).\n\n";
p += "APPLY real file edits when evidence warrants (CONTINUOUS intervals, PRODUCT_ORG, .grok/workflows/*).\n";
p += "Do NOT weaken battery, G13 Pruner, one NEXT, or invent settlement.\n";
p += "Write optimizer/CURRENT.md + log/NNN.md; reset since_last_optimize in CYCLE_COUNT.md.\n";
p += "Return product_score, latency_score, momentum_score 0-3, summary, changes_applied[],\n";
p += "deferred[], next_experiment, property_block.\n";

let r = agent(p, #{
    label: "optimizer-main",
    capability_mode: "all",
    output_schema: opt_schema,
});

if r == () || !r.success || r.output == () {
    complete(#{
        path: write_scratch_file("optimizer-report.json", json_encode(#{ success: false })),
        report: #{ success: false },
    });
}

let report = #{
    success: true,
    product_score: r.output.product_score,
    latency_score: r.output.latency_score,
    momentum_score: r.output.momentum_score,
    summary: r.output.summary,
    changes_applied: r.output.changes_applied,
    next_experiment: r.output.next_experiment,
    continuous_mandate: true,
    protocol: "docs/program/OPTIMIZER.md",
};
complete(#{
    path: write_scratch_file("optimizer-report.json", json_encode(report)),
    report: report,
});
