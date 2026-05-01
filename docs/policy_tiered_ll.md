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

**`find_critical_round`** scans the dry-run states and returns the last round *k* at which the stopping criterion has **not yet fired**:

| Stopping criterion | Meaning |
|--------------------|---------|
| `unreachable_faculty_count > 0` | A faculty member with capacity can no longer be reached by any student |
| `is_stall` (zero new assignments) | The rounds process has deadlocked |
| `unassigned_count > 0` and `unassigned_count ≤ empty_labs_count` | Remaining students have reached parity with (or dropped below) empty labs — backfill can fill them one-to-one. The `> 0` guard ensures the criterion does not fire once all students are already assigned. |

The computed *k* is stored in `meta` as `k_crit_static` and shown in the Phase 0 status panel. If the stopping criterion never fires during the dry-run, *k* equals the total number of rounds (the tiered rounds process runs to completion and the backfill phase handles zero students).

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

The backfill phase runs non-interactively. The algorithm differs between GUI and CLI modes, but in both modes the switch happens automatically without operator confirmation.

### GUI mode — LL-HP Backfill

Processes unassigned students in descending CPI order using preferences from position *k+1* onward (preferences 1..k are exhausted).

**Assignment rule:** scan remaining preferences and assign to the **least-loaded advisor with remaining capacity** (LL rule). Ties between equally-loaded advisors are broken by preference rank (highest preferred wins).

### CLI (auto) mode — CPI-Fill Backfill

Uses CPI-Fill Phase 1 + Phase 2 semantics on the remaining unassigned students:

**Phase 2a (CPI-Fill Phase 1 on `prefs[k:]`):** process unassigned students in descending CPI order; assign each to their highest-preferred advisor with remaining capacity (scanning from position *k+1* onward). Stop when `unassigned == empty_labs`. Because the switch criterion fires at `unassigned > 0 and unassigned ≤ empty_labs`, Phase 2a typically has zero or very few assignments to make.

**Phase 2b (CPI-Fill Phase 2 on full preference list):** each remaining student is assigned to their highest-preferred **empty lab**, scanning their *full* preference list (advisors in positions 1..k that are still empty are eligible). This guarantees all empty labs are filled when S_remaining ≥ E_remaining.

Snapshot ranks recorded during Phase 2a are global (e.g., rank *k+1* for the first preference in `prefs[k:]`), keeping the trace consistent with Phase 1.

### Both modes

- Faculty `max_load` constraints from Phase 0 are enforced.
- Backfill snapshots are appended to the shared snapshot list so the full two-phase trace is visible in the replay slider.
- If any students remain unassigned after backfill (all remaining preferences are at capacity), they are flagged as **overflow** — same treatment as a `tiered_rounds` stall.

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
