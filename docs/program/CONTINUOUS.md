# Continuous control plane

One honesty bar (`GUARDIAN.md`). Multiple agents, **one truth on main**,
**one primary trajectory**, recursive builder restart under Conductor.

| Loop | Interval | Job |
|------|----------|-----|
| **Overseer** | **15m** | Product honesty: lazy/half-measured, A2A strategy |
| **Scout** | **20m** | Low-star OSS → `scout/IDEA_BUS.md` |
| **Steward** | **30m** | Cohesion: clean cards, STATE claim hygiene |
| **Conductor** | **45m** | **Vision + conferral + restart flywheel when idle** |
| **Flywheel** | **1h** | One shippable bet (also kicked by Conductor) |

**Shared truth:** `STATE.md` · `steward/CURRENT.md` · **`conductor/CONFERRAL.md`** · `conductor/TRAJECTORY.md`  
**Guardian:** [`GUARDIAN.md`](GUARDIAN.md)

Orchestrators: `.grok/workflows/agent-commerce-{conductor,continuous,flywheel,overseer,scout,steward}.rhai`

## Recursion (how work keeps going)

```
Conductor tick / continuous workflow
    → confer all agent cards
    → update TRAJECTORY + CONFERRAL
    → if idle: run one build cycle (NEXT ACTION)
    → if PR opened: wait merge (human)
    → resume / next tick → recurse
```

```text
# Multi-cycle recurse (interactive)
/workflow agent-commerce-continuous {"max_cycles": 3, "prefer_bet": "O.8"}
/workflow agent-commerce-conductor {"continuous": true, "max_cycles": 2}

# Single roles
/workflow agent-commerce-steward
/workflow agent-commerce-overseer
/workflow agent-commerce-scout
/workflow agent-commerce-flywheel {"prefer_bet": "O.8"}
```

## Active schedules

| Name | Id | Interval |
|------|-----|----------|
| Overseer | `019fdfde0212` | 15m |
| Scout | `019fe0026e7d` | 20m |
| Steward | `019fdff1fbe4` | 30m |
| **Conductor** | `019fe25403f2` | **45m** |
| Flywheel hourly | `019fdfd6c9bf` | 1h |

### Conductor — 45m

Charter: [`CONDUCTOR.md`](CONDUCTOR.md) · Tick: [`CONDUCTOR_TICK_PROMPT.md`](CONDUCTOR_TICK_PROMPT.md)  
Writes: `conductor/CURRENT.md`, `TRAJECTORY.md`, `CONFERRAL.md`  
**Restarts** builder work when queue clear and NEXT is known.

### Steward — 30m · `019fdff1fbe4`

Card hygiene so Conductor/Overseer do not thrash on stale BLOCKED lies.

### Overseer — 15m · `019fdfde0212`

Product honesty only; must read CONFERRAL + steward CURRENT.

### Scout — 20m · `019fe0026e7d`

Seedlings only; never dual product path.

### Flywheel — 1h · `019fdfd6c9bf`

Scheduled backup builder; Conductor may also kick cycles mid-hour.

## Cohesion rules

1. Stock `origin/main` + `gh pr list` before any CURRENT write.  
2. **CONFERRAL.md** is the organized conference — agents read it first.  
3. One primary NEXT; dual tracks need explicit park in TRAJECTORY.  
4. git/gh beat stale cards.  
5. No auto-merge by default; no settlement fiction; no soft-fail.  

## Re-arm

```text
Ask Grok: "Re-arm Veritas control-plane schedulers"
```

Tasks expire ~7 days.
