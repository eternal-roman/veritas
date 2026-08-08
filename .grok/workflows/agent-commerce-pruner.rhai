// Pruner — aggressive bloat denial, refine, battery + E2E QA, ship veto
// Spec: docs/program/PRUNER.md · GUARDIAN.md · GOVERNING.md
//
// Args:
//   branch     string optional — focus branch
//   pr_number  int    optional — focus PR
//   apply      bool   default true — perform deletes/refines (false = report only)

let meta = #{
    name: "agent-commerce-pruner",
    description: "Aggressive clean/prune/QA/E2E gate — deny useless, non-functional, or bloated ships",
    when_to_use: "Before ship; scheduled anti-bloat; after multi-worker integrate",
    phases: [
        #{ title: "Inspect", detail: "Stock surface + diff" },
        #{ title: "Prune", detail: "Delete bloat; refine" },
        #{ title: "Verify", detail: "Battery + E2E; ship_ok" },
    ],
};

let prune_schema = #{
    "type": "object",
    "required": ["verdict", "ship_ok", "summary", "battery_green", "property_block"],
    "properties": #{
        "verdict": #{ "type": "string" },
        "ship_ok": #{ "type": "boolean" },
        "summary": #{ "type": "string" },
        "pruned": #{ "type": "array", "maxItems": 20, "items": #{ "type": "string" } },
        "denied": #{ "type": "array", "maxItems": 12, "items": #{ "type": "string" } },
        "battery_green": #{ "type": "boolean" },
        "e2e_notes": #{ "type": "string" },
        "directive": #{ "type": "string" },
        "property_block": #{ "type": "string" },
        "branch": #{ "type": "string" },
    },
};

let branch = "";
let pr_number = 0;
let apply = true;
if args != () {
    if args.branch != () { branch = args.branch; }
    if args.pr_number != () { pr_number = args.pr_number; }
    if args.apply != () { apply = args.apply; }
}

phase("Inspect");
phase("Prune");
phase("Verify");

let p = "";
p += "### WINDOWS PWSH SAFETY: no bare head/grep/tail/find.\n\n";
p += "You are Veritas PRUNER (docs/program/PRUNER.md). AGGRESSIVE anti-bloat + QA gate.\n";
p += "Goals: GOVERNING.md A2A commerce — only functioning, necessary, pursuant code ships.\n";
p += "apply=" + apply.to_string() + " focus_branch=" + branch + " pr_number=" + pr_number.to_string() + "\n\n";
p += "1. Stock: git fetch; gh pr list; flywheel-claim.md; STATE NEXT; open product PR diffs.\n";
p += "2. Choose active surface: product PR > claim branch > dirty product tree.\n";
p += "3. If apply: DELETE/reduce bloat (dead code, dupe docs, speculative APIs, soft-fail, vanity).\n";
p += "   Prefer delete over comment-out. Do not expand product scope. Do not dual NEXT.\n";
p += "4. Run FULL battery — all must exit 0 for battery_green=true:\n";
p += "   python -m pytest tests/ -q\n";
p += "   ruff check veritas tests\n";
p += "   python -m veritas.evaluations.harness\n";
p += "   python -m veritas.evaluations.payment_model\n";
p += "5. E2E: exercise claimed CLI/module or set ship_ok=false with NOT PROVEN.\n";
p += "6. ship_ok=true ONLY if battery_green and not bloated and not broken claims.\n";
p += "7. Write docs/program/pruner/CURRENT.md + pruner/log/NNN.md.\n";
p += "8. Optional short PR comment if product PR bloated/broken. Do not merge. No force-push main.\n";
p += "Return verdict (LEAN|BLOATED|BROKEN|MIXED), ship_ok, summary, pruned[], denied[],\n";
p += "battery_green, e2e_notes, directive, property_block, branch.\n";

let r = agent(p, #{
    label: "pruner-main",
    capability_mode: "all",
    output_schema: prune_schema,
});

if r == () || !r.success || r.output == () {
    let fail = #{
        success: false,
        ship_ok: false,
        reason: "pruner_agent_failed",
        autonomous: true,
    };
    complete(#{
        path: write_scratch_file("pruner-report.json", json_encode(fail)),
        report: fail,
    });
}

let out = r.output;
let report = #{
    success: true,
    ship_ok: out.ship_ok == true,
    verdict: out.verdict,
    summary: out.summary,
    battery_green: out.battery_green == true,
    pruned: out.pruned,
    denied: out.denied,
    directive: out.directive,
    branch: out.branch,
    property_block: out.property_block,
    autonomous: true,
    protocol: "docs/program/PRUNER.md",
};
let path = write_scratch_file("pruner-report.json", json_encode(report));
log("pruner ship_ok=" + (out.ship_ok == true).to_string() + " verdict=" + out.verdict);
complete(#{ path: path, report: report });
