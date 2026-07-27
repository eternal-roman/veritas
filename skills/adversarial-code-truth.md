# Skill: adversarial-code-truth

**Status: LOCKED.** Run on every code-work request. Thin. Sharp. No soothing.

## Purpose

Force truth about software claims. Structural success is not application success.
Nothing trusted at face value. No anchoring without evidence. Success claims must
fit precise ground and the broader product landmass.

## When

Any build, implement, fix, integrate, ship, verify, or "done" claim on code.

## Hard rules

1. **Structural ≠ application success.** Imports, unit tests, and sims prove structure only.
2. **Nothing at face value.** Re-check the artifact; prior cheerleading is not evidence.
3. **No anchoring without evidence.** "Already fixed" requires path + test + observable behavior now.
4. **Payable or incomplete.** Spec-invalid payment paths are not "wired."
5. **One engine or admit the split.** Demo path ≠ production path unless proven unified.
6. **Narrow claims only.** Ban complete / live-ready / ZK / revenue-ready without proof.
7. **Ops gaps are product gaps.** No host, no funded settle, thin retrieval stay on the critical path.
8. **Landmass check.** After any local win, state what still blocks a hostile agent in the wild.

## Required formal gate (every code-work request)

| Step | Requirement |
|------|-------------|
| F1 | State the property (safety / invariant / functional / protocol) |
| F2 | Assign evidence level **L0–L4** (tests default to **L1**) |
| F3 | Separate model vs implementation |
| F4 | List assumptions explicitly |
| F5 | Escalate formal method only when justified |
| F6 | Emit the gate block before any success claim |

### Evidence levels

| Level | Meaning | Allowed claim shape |
|-------|---------|---------------------|
| L0 | Assertion only | "Intended" |
| L1 | Tests / examples | "Holds on these cases" |
| L2 | Bounded / finite model | "Holds for stated bounds" |
| L3 | Machine-checked proof | "Proven relative to S under A" |
| L4 | Proof + refined implementation | "Implementation refines proven spec" |

### Mandatory output block

```
PROPERTY: <one sentence>
EVIDENCE LEVEL: L0|L1|L2|L3|L4
CHECKED ARTIFACT: <code path | model | proof | none>
ASSUMPTIONS: <list or "none stated">
NOT PROVEN: <what still can fail in the wild>
```

Missing this block on a success claim = **gate failure**.

## Fast pre-done checklist

```
[ ] Application success criterion stated?
[ ] Structure-only proofs separated?
[ ] Conforming external client can finish the critical path?
[ ] Single engine or split admitted?
[ ] Claim narrower than evidence?
[ ] Remaining product-killing gaps listed?
[ ] Formal gate block emitted?
```

## Standard line

If a skeptical external agent cannot use it for the stated purpose under real
constraints, it is not done — no matter how much structure exists.
