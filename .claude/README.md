# Plugin settings (per-project, local)

This repo uses the **plugin-settings** pattern from Claude Code plugin-dev:

| Path | Git? | Purpose |
|------|------|---------|
| `.claude/<plugin-name>.local.md` | **no** (gitignored) | YAML frontmatter + body for that plugin |
| This README | yes | Operator guide + templates |

## Active plugins (Grok)

From `~/.grok/config.toml`: **ponytail**, **ledger**, **superpowers**.

SessionStart **hooks were disabled** on Windows (harness failures). Skills/commands stay available. Local settings below default `hooks_enabled: false`.

## Create / edit settings

```text
.claude/ponytail.local.md
.claude/ledger.local.md
.claude/superpowers.local.md
```

Copy a template from below, then **restart** Claude Code / Grok so hooks/tools re-read state.

## Templates

### ponytail

```markdown
---
enabled: true
hooks_enabled: false
mode: full
level: full
---

# Ponytail (this project)

Lazy senior defaults for Veritas: smallest honest ship, no dual product NEXT,
no settlement fiction. Hooks off (Windows); skill still applies when invoked.
```

### ledger

```markdown
---
enabled: true
hooks_enabled: false
strict_money: true
forbid_floats: true
---

# Ledger Chad (this project)

Plane + product money: integer VAAT / Money.from only. Never invent x402 settle.
Use ledger-verify before shipping monetary code.
```

### superpowers

```markdown
---
enabled: true
hooks_enabled: false
process_skills_first: true
---

# Superpowers (this project)

Process skills (brainstorming, TDD, systematic-debugging) before implementation.
SessionStart hook disabled on Windows; invoke skills explicitly.
```

## Parsing (hooks / scripts)

```bash
STATE_FILE=".claude/ponytail.local.md"
[[ -f "$STATE_FILE" ]] || exit 0
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//')
[[ "$ENABLED" == "true" ]] || exit 0
```

## Veritas agent loop note

Plugin settings do **not** dual product NEXT. Support agents stay under
`docs/program/WORKFLOW_HYGIENE.md` and `ORG_LOOPS.md`.
