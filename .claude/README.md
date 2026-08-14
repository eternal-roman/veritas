# Plugin settings (per-project, local)

| Path | Git? | Purpose |
|------|------|---------|
| `.claude/<plugin>.local.md` | no | YAML frontmatter + body |
| This README | yes | Templates |

Active plugins (from `~/.grok/config.toml`): **ponytail**, **ledger**, **superpowers**.
SessionStart hooks are off on Windows. Skills still work. Locals default
`hooks_enabled: false`. Restart the host after editing.

```text
.claude/ponytail.local.md
.claude/ledger.local.md
.claude/superpowers.local.md
```

### ponytail

```markdown
---
enabled: true
hooks_enabled: false
mode: full
level: full
---
# Ponytail (this project)
Smallest honest ship. No dual product NEXT. No settlement fiction.
```

### ledger

```markdown
---
enabled: true
hooks_enabled: false
strict_money: true
forbid_floats: true
---
# Ledger (this project)
Integer VAAT / Money.from only. Never invent x402 settle.
```

### superpowers

```markdown
---
enabled: true
hooks_enabled: false
process_skills_first: true
---
# Superpowers (this project)
Process skills before implementation. Invoke explicitly (hooks off).
```

Plugin settings do not dual product NEXT. Support agents follow
`docs/program/WORKFLOW_HYGIENE.md` and `ORG_LOOPS.md`.
