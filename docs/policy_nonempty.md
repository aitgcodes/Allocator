# Policy: `nonempty`

## Overview

`nonempty` is a **load-distribution variant** of `least_loaded`. It runs the same Phase 0 → Round 1 → Main Allocation pipeline but changes the advisor selection rule: instead of always choosing the advisor with the minimum current load, it **actively seeks out empty labs** (advisors with zero students) and steers students there first. Only if no empty lab exists within the student's preference window does it fall back to the least-loaded advisor.

The policy is designed for departments that want to **guarantee every advisor receives at least one student** as early and as efficiently as possible, rather than gradually filling the most preferred advisors to capacity before anyone else gets students.

---

## Pipeline

```
Phase 0  →  Round 1  →  Main Allocation (Class A → B → C)
```

Phase 0 and Round 1 are **identical** to `least_loaded`. The difference lives entirely in the per-student choice function used during the main allocation.

### Phase 0 — Tiering and parameter setup

Same as `least_loaded`. See [policy_least_loaded.md](policy_least_loaded.md) for full details.

### Round 1 — Global first-choice pass

Same as `least_loaded`. Each faculty with at least one first-choice applicant picks one student (highest CPI by default). After Round 1, some advisors will have load = 1 and others load = 0; the main allocation must fill the remaining empty labs.

### Main Allocation — Class A → B → C

The class-wise cascade (A → B → C, with promotion of unassigned students downward) is identical to `least_loaded`. The selection rule applied at each step is different:

---

## Assignment rule (applied at every step)

Given a student and their eligible candidate advisors (those within `N_tier` with remaining capacity):

1. **Check for empty labs**: among the eligible advisors, collect those with `current_load == 0`.
2. **If at least one empty lab exists**: pick the empty advisor that appears **earliest in the student's preference list** and assign there.
3. **If no empty lab exists among eligible advisors**: fall back to picking the eligible advisor that appears **earliest in the student's preference list**, regardless of load.

This makes **emptiness the primary criterion**, **preference rank the tiebreaker** within the empty set, and **preference rank** again the criterion in the fallback case. Load is only implicitly managed — once all labs have at least one student, the policy degenerates to a pure highest-preference-within-window rule.

---

## Comparison with `least_loaded`

| Aspect | `least_loaded` | `nonempty` |
|--------|----------------|------------|
| Primary criterion | Minimum load | Empty lab first |
| Tiebreaker | Earliest preference | Earliest preference |
| Fallback (no empty labs) | Minimum load | Earliest preference |
| Load balance after early rounds | Smooth, incremental | Fast emptying, then preference-first |
| Preference satisfaction | Good | Often better once empty labs are gone |
| Advisor equity (early) | Gradual | Aggressive early equalisation |

In practice, after Round 1 assigns one student to roughly `min(F, S)` advisors, the main allocation begins with some number of truly empty labs. `nonempty` will steer the first wave of main-allocation students into those empty labs (picking the preferred one among them), after which both policies behave similarly.

---

## Properties and trade-offs

| Property | Behaviour |
|----------|-----------|
| **Load balance** | Good early on; converges to preference-first once all labs are non-empty. |
| **Preference satisfaction (PSI)** | Can be slightly better than `least_loaded` in some cohorts, because once empty labs are filled the fallback is pure preference-rank rather than minimum-load. |
| **Merit sensitivity (NPSS)** | Similar to `least_loaded` — no explicit CPI ordering beyond the tier window. |
| **Overflow** | Similar to `least_loaded`. |
| **Empty-lab guarantee** | Strong — the policy will actively fill empty labs before balancing loads. |
| **Robustness** | Good in standard cohorts; in very clustered cohorts where most students rank the same advisors first, the empty-lab preference may route students to lower-ranked advisors unnecessarily. |

### When `nonempty` performs best

- Departments with a strong **institutional requirement that every advisor must receive at least one student** — `nonempty` fills empty labs faster and more explicitly than `least_loaded`.
- Cohorts where **advisor preferences are spread broadly** — when students distribute their top choices across many advisors, directing some students to empty labs costs little in preference rank.
- As a **complement to Round 1**: since Round 1 already assigns one student to many popular advisors, the remaining empty labs after Round 1 tend to be less-popular advisors; `nonempty` ensures they are filled before the more popular ones are further loaded.

### Known limitations

- Once all labs have at least one student, the fallback rule is **pure preference** (not load-balanced). This means the later stages of a large cohort can accumulate load unevenly at popular advisors.
- In **clustered preference** cohorts, the popular-first preference in the fallback can concentrate students at a few advisors while others hover near minimum load.
- The policy does not explicitly prevent a lab from going empty *again* (i.e., there is no mechanism to undo Round 1 assignments that may have left some labs with exactly one student while others have many).

---

## Configuration

Set in `src/allocator/app.py`:

```python
ALLOCATION_POLICY = "nonempty"
```

Or via CLI:

```bash
PYTHONPATH=src python -m allocator.allocation \
  --students data/sample_students.csv \
  --faculty  data/sample_faculty.csv  \
  --policy   nonempty
```
