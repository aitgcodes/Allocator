# Policy: Tiered LL (`tiered_ll`)

## Overview

`tiered_ll` is a **hybrid policy** that combines the transparency of preference rounds with an empty-lab guarantee. It runs interactive tiered preference rounds for the first *k* rounds (where *k* is determined by a static dry-run pre-computation), then automatically switches to a backfill phase for any remaining unassigned students. The backfill algorithm differs by mode: GUI uses LL-HP backfill; CLI uses CPI-Fill Phase 1+2 semantics. When S ≥ F and the preference structure is feasible, `tiered_ll` guarantees no empty labs.

This policy is available both through the Dash UI and via the CLI. In CLI (batch) mode all tie-breaks in Phase 1 are resolved automatically by highest CPI (ties in CPI broken by student ID ascending); the manual pick UI is only available in the Dash GUI.

---

## Pipeline

```
Phase 0a (tiering)  →  Phase 0b (dry-run → k_crit)
  →  Phase 1: Tiered Rounds 1..k_crit  (interactive)
  →  Phase 2: Backfill (GUI: LL-HP | CLI: CPI-Fill Phase 1+2)  (automatic)
```

---

## Phase 0a — Tier Classification

Identical to all other policies. Students are tiered by CPI percentile (or quartile if the cohort clusters heavily). `N_tier` windows and faculty `max_load` values are set. The tier information is **diagnostic only** for the rounds phases — it is displayed in the completion panel's per-tier breakdown but does not restrict which advisors students can be assigned to during the preference rounds.

---

## Phase 0b — Dry-Run and Critical Round k

Before any interactive steps, the app runs a full dry-run of the tiered-rounds process using CPI-based automatic tie-breaking (no manual picks). The dry-run collects, per round:

- Number of unassigned students
- Number of faculty with zero students (empty labs)
- Number of faculty with remaining capacity that no unassigned student can reach (unreachable faculty)
- Whether the round produced zero new assignments (stall)

**`find_critical_round`** scans the dry-run states and returns *k*, the number of tiered rounds the GUI will run before switching to backfill:

| Stopping criterion | k returned | Meaning |
|--------------------|-----------|---------|
| `unreachable_faculty_count > 0` OR `is_stall` | prev round (min 1) | Structural problem; don't count the broken round |
| `unassigned_count > 0` AND `unassigned_count < empty_labs_count` | prev round (may be 0) | **Overshoot**: round *n* created more empty labs than students remain; stopping one round earlier keeps Phase 2b feasible |
| `unassigned_count > 0` AND `unassigned_count == empty_labs_count` | round *n* | **Exact parity**: run this round, then switch to backfill |

*k* = 0 is valid: it means round 1 itself overshoots (U₁ < E₁), so no tiered rounds are shown and the GUI jumps directly to backfill using the full preference list. The computed *k* is stored in `meta` as `k_crit_static` and displayed in the Phase 0 status panel. If the criterion never fires, *k* equals the total number of rounds (backfill receives zero students).

---

## Phase 1 — Tiered Rounds 1..k (Interactive)

Identical to the `tiered_rounds` policy for rounds 1 through *k*:

- In round *n*, every still-unassigned student simultaneously offers their *n*-th preference.
- Each advisor collects its candidate pool and picks **at most one student per round**.
- If one candidate has the highest CPI, that student is assigned automatically.
- If two or more candidates share the top CPI, the operator must make a **manual pick** before the round advances.

After each round completes, the app checks whether the round number has reached *k_crit*. If so, the UI transitions automatically to Phase 2 without requiring operator confirmation.

---

## Phase 2 — Backfill (Automatic)

The backfill phase runs non-interactively immediately after round *k* completes. It operates on each student's preferences from position *k+1* onward (`prefs[k:]`). The algorithm is identical between GUI and CLI modes (GUI: `tiered_ll_backfill`; CLI: `tiered_ll_cpi_backfill` wrapping the same two-phase logic).

### Phase 2a — Highest-preferred with capacity (while U > E)

While the number of remaining unassigned students exceeds the number of empty labs:

1. Take the highest-CPI remaining student.
2. Scan their `prefs[k:]` and assign them to the **first advisor with remaining capacity** (highest preference, any load level).
3. If no advisor in `prefs[k:]` has capacity, defer the student to Phase 2b.
4. Recount empty labs and repeat.

Phase 2a stops when `unassigned == empty_labs`.

### Phase 2b — Highest-preferred empty lab (when U == E)

When unassigned students equal empty labs exactly:

- Each remaining student (in CPI order) is assigned to their **highest-preferred empty lab** in `prefs[k:]`.
- One student per lab; once a lab is filled it is removed from the candidate set.
- Students whose `prefs[k:]` contains no empty lab become **overflow**.

### Both phases

- Faculty `max_load` constraints from Phase 0 are enforced throughout.
- Snapshot `phase` labels distinguish `TieredLL_Backfill_P2a` and `TieredLL_Backfill_P2b` so the two-phase trace is visible in the replay slider.
- If any students remain unassigned after Phase 2b (no empty lab in their `prefs[k:]`), they are flagged as **overflow** — same treatment as a `tiered_rounds` stall.

### CLI (auto) mode

Uses `cpi_fill_phase1` on `prefs[k:]` for Phase 2a and `cpi_fill_phase2` (scanning the full preference list) for Phase 2b, with automatic CPI tie-breaking throughout.

---

## Trade-offs

| vs `tiered_rounds` | `tiered_ll` adds an empty-lab guarantee via the backfill phase; `tiered_rounds` is fully preference-driven but cannot guarantee coverage |
| vs `least_loaded` | `tiered_ll` provides a preference-round phase visible to operators; `least_loaded` is simpler and fully automated from the start |
| vs `adaptive_ll` | Both guarantee no empty labs; `tiered_ll` uses interactive rounds for the first *k* steps, making early assignments more transparent to all parties |

---

## Known Limitations

- The dry-run assumes CPI tie-breaking; actual manual picks in Phase 1 may produce a different assignment trajectory, causing the live critical round to differ from *k_crit_static*. In most cohorts this does not change *k*; extreme tie-sensitivity is rare.
- If S < F (fewer students than faculty), empty labs cannot be avoided regardless of policy. The app flags this as a structural deficit.
- In CLI mode, tie-breaking uses CPI automatically (same rule as the dry-run), so `k_crit_static` is always exact. If you need human judgment over ties, use the Dash GUI.
