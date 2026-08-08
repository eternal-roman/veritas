#!/usr/bin/env python3
"""Git Agent inventory: classify local/remote branches for abandonment vs salvage.

Pure reporting by default. Emits JSON (stdout) and optional Markdown path.
Does not delete anything — cleanup is a separate, confirmed step.

Usage:
  python scripts/git_branch_audit.py
  python scripts/git_branch_audit.py --markdown docs/program/git-agent/log/AUDIT.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def run(args: list[str], cwd: Path | None = None) -> str:
    r = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if r.returncode != 0 and not r.stdout.strip():
        raise RuntimeError(f"cmd failed ({r.returncode}): {' '.join(args)}\n{r.stderr}")
    return r.stdout


@dataclass
class BranchRow:
    name: str
    kind: str  # remote | local
    sha: str
    subject: str
    committer_date: str
    ahead_of_main: int
    behind_main: int
    is_merged_to_main: bool
    unique_paths: list[str] = field(default_factory=list)
    classification: str = "unknown"
    salvage: str = ""
    proposed_action: str = ""
    notes: str = ""


PROTECT = frozenset({"main", "master", "origin/main", "origin/HEAD"})

# Patterns that usually mean docs thrash after product already landed
DOCS_THRASH = re.compile(
    r"^(docs/(conductor|steward|cycle|release|post-merge|p7c|n1|n0|g9|v080))"
)
LANDED_FEAT = re.compile(
    r"^(feat/(n1\.|n0|p7|o\.8|o\.6|cycle|g9|session)|release/|fix/(credit|sdk|verify|lock))"
)


def classify(row: BranchRow) -> BranchRow:
    short = row.name.removeprefix("origin/")
    if short in ("main", "master") or row.name in PROTECT:
        row.classification = "protected"
        row.proposed_action = "never_delete"
        row.salvage = "none"
        return row

    if short == "fable/survival-records" or short.startswith("fable/"):
        row.classification = "active_product"
        row.proposed_action = "keep_open_pr_or_confer"
        row.salvage = "A26/A27/standing mechanism — PR #75 family; do not drop"
        row.notes = "Buyer-side survival + warranty W0; G10 stays open"
        return row

    if short.startswith("docs/g10") or "survival" in short:
        row.classification = "knowledge_merge"
        row.proposed_action = "cherry_or_merge_docs_then_delete"
        row.salvage = "G10 consensus brief if not on main"
        return row

    if row.is_merged_to_main and row.ahead_of_main == 0:
        row.classification = "fully_merged"
        row.proposed_action = "delete_remote_and_local"
        row.salvage = "none — already on main"
        return row

    # Fully merged often shows ahead=0; if tip is ancestor of main:
    if row.is_merged_to_main:
        row.classification = "fully_merged"
        row.proposed_action = "delete_remote_and_local"
        row.salvage = "none — tip reachable from main"
        return row

    if DOCS_THRASH.match(short) and row.ahead_of_main <= 3:
        # Small docs-only ahead of old tip — usually superseded closeouts
        if row.behind_main >= 1 and _looks_docs_only(row):
            row.classification = "stale_docs_closeout"
            row.proposed_action = "delete_after_overseer_ack"
            row.salvage = "skim CURRENT/STATE for any unique note; else drop"
            return row

    if short.startswith("docs/") and row.ahead_of_main > 0:
        if _looks_docs_only(row):
            row.classification = "stale_docs_closeout"
            row.proposed_action = "delete_after_overseer_ack"
            row.salvage = "diff docs/program only; harvest unique sentences to steward log if any"
            return row

    if LANDED_FEAT.match(short) or short.startswith("feat/") or short.startswith("fix/"):
        if row.is_merged_to_main or row.ahead_of_main == 0:
            row.classification = "merged_feature"
            row.proposed_action = "delete_remote_and_local"
            row.salvage = "none"
            return row
        # Unmerged feature commits — high interest
        row.classification = "unmerged_product"
        row.proposed_action = "overseer_review_diff"
        row.salvage = "inspect unique commits vs main; open salvage PR or abandon with reason"
        return row

    if row.ahead_of_main > 0 and not row.is_merged_to_main:
        row.classification = "diverged"
        row.proposed_action = "overseer_review_diff"
        row.salvage = "list unique paths; decide harvest vs abandon"
        return row

    if row.ahead_of_main == 0 and row.behind_main > 0:
        row.classification = "ancestor_only"
        row.proposed_action = "delete_remote_and_local"
        row.salvage = "none — old tip"
        return row

    row.classification = "unknown"
    row.proposed_action = "manual"
    return row


def _looks_docs_only(row: BranchRow) -> bool:
    if not row.unique_paths:
        return True
    return all(
        p.startswith("docs/")
        or p.endswith(".md")
        or p in ("CHANGELOG.md", "STATUS.md", "CONSTITUTION.md")
        for p in row.unique_paths
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--markdown", type=Path, default=None)
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()
    repo = args.repo.resolve()

    run(["git", "fetch", "origin", "--prune"], cwd=repo)
    main_sha = run(["git", "rev-parse", "origin/main"], cwd=repo).strip()

    raw = run(
        [
            "git",
            "for-each-ref",
            "--format=%(refname:short)|%(objectname:short)|%(committerdate:iso8601)|%(subject)",
            "refs/remotes/origin",
        ],
        cwd=repo,
    )

    rows: list[BranchRow] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line == "origin" or line.startswith("origin/HEAD"):
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        name, sha, date, subject = parts[0], parts[1], parts[2], parts[3]
        if name == "origin":
            continue

        # ahead/behind
        ab = run(
            ["git", "rev-list", "--left-right", "--count", f"origin/main...{name}"],
            cwd=repo,
        ).strip()
        try:
            behind_s, ahead_s = ab.split()
            behind, ahead = int(behind_s), int(ahead_s)
        except ValueError:
            behind, ahead = -1, -1

        # merged?
        merged_list = run(
            ["git", "branch", "-r", "--merged", "origin/main"],
            cwd=repo,
        )
        is_merged = any(
            m.strip() == name or m.strip().endswith(name.split("/", 1)[-1])
            for m in merged_list.splitlines()
        )
        # merge-base --is-ancestor: exit 0 = yes, 1 = no (not an error for us)
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, main_sha],
            cwd=repo,
            capture_output=True,
        )
        is_merged = r.returncode == 0

        unique_paths: list[str] = []
        if ahead > 0 and not is_merged:
            diff = run(
                ["git", "diff", "--name-only", f"origin/main...{name}"],
                cwd=repo,
            )
            unique_paths = [p for p in diff.splitlines() if p.strip()][:40]

        row = BranchRow(
            name=name,
            kind="remote",
            sha=sha,
            subject=subject,
            committer_date=date,
            ahead_of_main=ahead,
            behind_main=behind,
            is_merged_to_main=is_merged,
            unique_paths=unique_paths,
        )
        rows.append(classify(row))

    # Local branches with gone upstream
    local_raw = run(["git", "branch", "-vv"], cwd=repo)
    local_gone: list[dict[str, str]] = []
    for line in local_raw.splitlines():
        if ": gone]" in line or "[gone]" in line:
            local_gone.append({"line": line.strip()})

    worktrees = run(["git", "worktree", "list"], cwd=repo).strip().splitlines()

    buckets: dict[str, list[str]] = {}
    for r in rows:
        buckets.setdefault(r.classification, []).append(r.name)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "origin_main": main_sha[:12],
        "remote_branch_count": len(rows),
        "buckets": {k: sorted(v) for k, v in sorted(buckets.items())},
        "branches": [asdict(r) for r in sorted(rows, key=lambda x: (x.classification, x.name))],
        "local_gone_tracking": local_gone,
        "worktrees": worktrees,
        "delete_candidates_remote": sorted(
            r.name
            for r in rows
            if r.proposed_action == "delete_remote_and_local"
            and r.name not in ("origin/main",)
        ),
        "overseer_review_required": sorted(
            r.name
            for r in rows
            if r.proposed_action in ("overseer_review_diff", "keep_open_pr_or_confer", "cherry_or_merge_docs_then_delete")
        ),
    }

    text = json.dumps(report, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)

    if args.markdown:
        md = _to_markdown(report)
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(md, encoding="utf-8")

    return 0


def _to_markdown(report: dict) -> str:
    lines = [
        "# Git branch audit",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**origin/main:** `{report['origin_main']}`",
        f"**Remote branches:** {report['remote_branch_count']}",
        "",
        "## Buckets",
        "",
    ]
    for k, names in report["buckets"].items():
        lines.append(f"### {k} ({len(names)})")
        for n in names:
            lines.append(f"- `{n}`")
        lines.append("")

    lines.extend(
        [
            "## Overseer review required",
            "",
        ]
    )
    for n in report["overseer_review_required"]:
        br = next(b for b in report["branches"] if b["name"] == n)
        lines.append(
            f"- **`{n}`** — {br['classification']} / {br['proposed_action']}: "
            f"{br.get('salvage') or br.get('notes') or br['subject']}"
        )
    lines.extend(
        [
            "",
            "## Safe delete candidates (tip ancestor of main)",
            "",
        ]
    )
    for n in report["delete_candidates_remote"]:
        lines.append(f"- `{n}`")

    lines.extend(
        [
            "",
            "## Local gone-tracking (cleanup worktrees/branches)",
            "",
        ]
    )
    for g in report["local_gone_tracking"][:40]:
        lines.append(f"- `{g['line']}`")

    lines.extend(
        [
            "",
            "## Worktrees",
            "",
            "```",
            *report["worktrees"],
            "```",
            "",
            "## Per-branch table",
            "",
            "| Branch | SHA | A/B | Class | Action |",
            "|--------|-----|-----|-------|--------|",
        ]
    )
    for b in report["branches"]:
        lines.append(
            f"| `{b['name']}` | `{b['sha']}` | +{b['ahead_of_main']}/-{b['behind_main']} | "
            f"{b['classification']} | {b['proposed_action']} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
