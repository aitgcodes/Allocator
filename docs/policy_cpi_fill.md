# Policy: `cpi_fill`

## Overview

`cpi_fill` is a **merit-first, two-phase allocation policy**. It skips Round 1 entirely and replaces the standard class-wise main allocation with a two-phase procedure built around a single principle: **students are processed in strict descending CPI order**, so academically stronger students always gain access to their preferred advisors before lower-CPI peers.

Phase 1 fills the bulk of assignments by CPI rank, stopping at a mathematically precise point. Phase 2 then uses the remaining unassigned students to guarantee that every advisor receives at least one student.

---

## Pipeline

```
Phase 0  →  CPI-Fill Phase 1  →  CPI-Fill Phase 2
```

Round 1 is **not run** under this policy. The two-phase procedure replaces both Round 1 and the main allocation.

### Phase 0 — Tiering and parameter setup

Identical to `least_loaded`. Students are tiered by CPI percentile (or quartile), `N_tier` windows are set, and faculty `max_load` is determined. The tier information is computed but is not used during the assignment phases — `cpi_fill` does not apply tier-based preference windows. All students draw from their full preference list.

---

## Phase 1 — CPI-ordered greedy assignment

**Goal**: assign as many students as possible in strict CPI order, stopping precisely when the number of remaining unassigned students equals the number of remaining empty labs.

**Stopping condition**: `|unassigned| == |empty_labs|`

This preserves exactly enough unassigned students to guarantee that every empty lab receives at least one student in Phase 2.

### Step-by-step

1. Sort all students by CPI, descending (ties broken by student ID).
2. For each student in that order:
   - Scan the student's preference list from rank 1 onward.
   - Assign the student to the **first advisor in their list that still has remaining capacity** (`current_load < max_load`).
   - Update loads and mark the student assigned.
   - **Check the stopping condition**: if `|unassigned| == |empty_labs|`, stop Phase 1 immediately — regardless of whether more students remain.
3. If `|empty_labs| == 0` at the start (all advisors already have students, e.g. in a reload scenario), Phase 1 runs to completion with no stopping condition.
4. If `|unassigned| == |empty_labs|` at the start, Phase 1 is skipped entirely and all remaining students go to Phase 2.

### Assignment rule in Phase 1

Among eligible advisors (those with remaining capacity), pick the one **earliest in the student's own preference list** — not the least-loaded one. This means a student goes to their most preferred advisor that has a free slot, regardless of how loaded that advisor is relative to others.

---

## Phase 2 — Empty-lab fill by CPI order

**Goal**: assign each remaining unassigned student to their **most preferred advisor that currently has zero students** (an empty lab).

### Step-by-step

1. Sort the remaining unassigned students by CPI, descending.
2. For each student:
   - Scan their preference list from rank 1 onward.
   - Assign the student to the **first advisor in their list whose current load is 0** (empty lab).
   - Increment that advisor's load from 0 to 1.
3. After Phase 2, every advisor has at least one student (by design of the stopping condition) and all students are assigned.

### Assignment rule in Phase 2

Among advisors with `load == 0`, pick the one **earliest in the student's preference list**. Students still go to their most preferred empty lab; the CPI ordering of the Phase 2 queue means higher-CPI students get first pick of the remaining empty labs.

---

## Why the stopping condition works

Let `U` be the number of unassigned students at any point and `E` the number of empty labs. The invariant maintained is:

- Phase 1 assigns students one by one. Each assignment can reduce `E` by at most 1 (if the advisor was empty) and reduces `U` by exactly 1.
- Phase 1 stops when `U == E`, meaning there are exactly as many students left as there are empty labs.
- Phase 2 then assigns each remaining student to their preferred empty lab, consuming exactly one student and one empty lab per step.
- Result: `U` and `E` both reach 0 simultaneously, guaranteeing full assignment with no empty labs.

---

## Comparison with `least_loaded`

| Aspect | `least_loaded` | `cpi_fill` |
|--------|----------------|------------|
| Round 1 | Yes | No |
| Processing order | Tier-by-tier, arbitrary within tier | Strict descending CPI across all tiers |
| Preference window | `N_tier` (3/5/full per tier) | Full list (no window) |
| Primary advisor criterion | Minimum load | Earliest in preference list with capacity |
| Empty-lab guarantee | Indirect (via Class C fallback) | Explicit (Phase 2 design) |
| Merit sensitivity (NPSS) | Moderate | High — high-CPI students claim top choices first |
| Equal-weighted satisfaction (PSI) | Often higher | Often lower (lower-CPI students pushed further) |
| Load balance | Strong | Variable — can concentrate load at popular advisors |

---

## Properties and trade-offs

| Property | Behaviour |
|----------|-----------|
| **Merit sensitivity (NPSS)** | High — high-CPI students are processed first and claim their top preferences before any lower-CPI student is considered. |
| **Preference satisfaction (PSI)** | Mixed — top students get excellent matches; lower-CPI students may end up further down their list because popular advisors are already filled. |
| **Load balance** | Weaker than `least_loaded` — popular advisors can fill up quickly through Phase 1, while less popular ones wait for Phase 2. |
| **Empty-lab guarantee** | Very strong — the stopping condition and Phase 2 design make it structurally impossible to leave an advisor empty. |
| **Overflow count** | Can be higher than `least_loaded` in clustered cohorts — many students land beyond their `N_tier` window because there is no window-based redirection. The NPSS score uses the full preference list F as its denominator, so out-of-window placements still receive a positive NPSS contribution; the overflow count is the separate diagnostic for tier-cap compliance. |
| **Equity Retention Rate** | Moderate — because high-CPI students all land at popular advisors first, those advisors tend to accumulate homogeneous high-CPI cohorts, reducing the ERR below what `least_loaded` achieves. |
| **MSES** | Tends to be low (good) for high-CPI students, who claim their top-preferred advisors first; higher for lower-CPI students who receive whoever remains. System-level MSES outcome depends on cohort composition. |

### When `cpi_fill` performs best

- When **academic merit should explicitly determine priority**: the institution wants students with higher CPI to have unambiguous first access to their preferred advisors, not just a wider preference window.
- When **empty-lab elimination is a hard requirement**: the Phase 2 design makes it impossible to leave any advisor without a student as long as `S ≥ F`.
- In **random or weakly correlated preference** cohorts: when students' preferences are not heavily clustered, Phase 1's greedy first-choice rule gives most students their top pick with little competition.
- When the **S/F ratio is moderate** (around 1–2): with few students per advisor, the stopping condition fires early and Phase 2 cleanly fills the remaining empty labs.

### Known limitations

- In **clustered preference** cohorts (many students all ranking the same few advisors at the top), high-CPI students fill those advisors rapidly. When Phase 2 students (lower CPI) arrive, their top choices are already full and they receive assignments further down their lists, increasing overflow and reducing PSI.
- **No tier window**: unlike `least_loaded`, there is no `N_tier` protection. A Class A student whose top 3 advisors are full will still be assigned to an advisor further down their list in Phase 1, rather than being promoted to a broader pool.
- **Load imbalance**: because the selection rule in Phase 1 is highest-preference-with-capacity (not least-loaded), popular advisors can absorb many students while unpopular ones wait for Phase 2, potentially producing a more skewed load distribution.

---

## Configuration

Set in `src/allocator/app.py`:

```python
ALLOCATION_POLICY = "cpi_fill"
```

Or via CLI:

```bash
PYTHONPATH=src python -m allocator.allocation \
  --students data/sample_students.csv \
  --faculty  data/sample_faculty.csv  \
  --policy   cpi_fill
```

> **Note:** The `--phase0-only` flag still works with `cpi_fill` — it will compute and export tiers without running either allocation phase.
