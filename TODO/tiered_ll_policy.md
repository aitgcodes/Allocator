# TODO: `tiered_ll` Policy Implementation

**Policy name:** `tiered_ll`  
**Description:** Tiered Rounds for rounds 1..k (operator-mediated, CPI tie-break), then
LL-HP (CPI-ordered, highest-preferred advisor with remaining capacity) over each
student's remaining preferences from position k+1 onward. The critical round k is
determined by a static dry-run pre-computation; an optional dynamic check validates
or adjusts k during the actual run based on live reachability.

---

## Phase 0 — Tiering + Dry-Run (Phase 0b)

- [ ] **Phase 0a**: run standard `phase0()` for tier classification (same as
  `tiered_rounds`). Tiering is informational; `n_tier` is not used as a hard cap
  in the backfill phase.
- [ ] **`tiered_rounds_dry_run(students, faculty)`** (`allocation.py`): deep-copy
  students/faculty, run `tiered_rounds_start` + repeated `tiered_rounds_resume`
  with CPI-based auto tie-breaking (no manual picks), collect per-round state
  snapshots (unassigned count, reachable-faculty count, assignments).
- [ ] **`_reachability(unassigned_ids, faculty, assignments, faculty_loads)`**
  (`allocation.py`): for each faculty with remaining capacity, check whether at
  least one unassigned student still lists them in their remaining preferences.
  Return count of reachable-but-uncovered faculty (capacity > 0, reachable by ≥ 1
  student) and count of unreachable faculty (capacity > 0, reachable by 0 students).
- [ ] **`find_critical_round(dry_run_states)`** (`allocation.py`): iterate dry-run
  states round by round; return the last round k where the stopping criterion has
  NOT yet fired. Stopping criterion: unreachable-faculty count first goes positive
  OR round produces zero new assignments (stall). If criterion never fires, k = total
  rounds (tiered rounds runs to completion without a backfill switch).
- [ ] Store dry-run results in `meta`: `k_crit_static`, `dry_run_empty_labs`,
  `dry_run_rounds_total`, `dry_run_stall_round` (None if no stall).

---

## Phase 1 — Tiered Rounds (rounds 1..k_crit)

- [ ] Run actual `tiered_rounds_start` + `tiered_rounds_resume` as normal (operator
  sees manual tie-break prompts).
- [ ] **Dynamic stopping criterion** (optional, enabled via `use_dynamic=True`):
  after each completed round, call `_reachability()` on live state. If criterion
  fires at round k_live ≠ k_crit_static, store `k_crit_dynamic = k_live` in meta
  and flag discrepancy in the status message ("static k=3, dynamic adjusted to k=2").
  When dynamic is disabled, switch at k_crit_static unconditionally.
- [ ] On reaching k (static or dynamic), freeze tiered-rounds state: record
  `assignments`, `faculty_loads`, list of unassigned student IDs, and the preference
  position each student has reached (= k, since tiered_rounds processes rank by round
  number).

---

## Phase 2 — LL-HP Backfill

- [ ] **`tiered_ll_backfill(unassigned, faculty, assignments, faculty_loads, k, snapshots)`**
  (`allocation.py`): for each unassigned student, truncate their preference list to
  `prefs[k:]` (remaining preferences from position k+1 onward, 0-indexed). Run
  `main_allocation` logic on this reduced-preference subset with the inherited
  `assignments` and `faculty_loads` from Phase 1. CPI ordering is already guaranteed
  by `_sorted_by_cpi` inside `main_allocation`.
- [ ] Append backfill snapshots to the shared `SnapshotList` so the slider shows the
  full two-phase trace.
- [ ] If any students remain unassigned after backfill (their remaining preferences
  are all full), flag them as overflow — same treatment as `tiered_rounds` stall.

---

## App Integration (`app.py`)

- [ ] Add `"tiered_ll"` to the policy selector dropdown (with a short description).
- [ ] **`btn-phase0` / `btn-full`**: set `_optimize = False`; after `phase0()`, run
  `tiered_rounds_dry_run` + `find_critical_round`; store k_crit in `_app_state["meta"]`.
- [ ] **Phase 0 status message**: include dry-run summary —
  `"k_crit=3 | dry-run: 0 empty labs, switch after round 3"` or
  `"k_crit=2 | dry-run: stall detected at round 3, 1 lab unreachable"`.
- [ ] **Empty-lab risk modal**: extend `_build_risk_data` and `cb_risk_modal` to handle
  `tiered_ll` — show dry-run predicted empty labs (if any), k_crit, and whether
  dynamic checking is enabled.
- [ ] **UI state machine**: after each tiered round, check whether round count == k_crit
  (or dynamic criterion fired); auto-transition to backfill phase without operator
  confirmation (backfill is non-interactive).
- [ ] **Dynamic mode toggle**: add a checkbox or radio in the policy config panel —
  "Validate k dynamically during run" (off by default).
- [ ] **Status messages**:
  - Phase 1 in progress: `"Round n/k_crit — m students unassigned"`
  - Phase 1 → Phase 2 transition: `"Switching to LL-HP backfill after round k (static k=K [dynamic confirmed/adjusted])"`
  - Phase 2 complete: `"LL-HP backfill complete — n students assigned, m overflow (if any)"`

---

## State / Dataclasses (`state.py`)

- [ ] No new dataclasses required. Add fields to `_app_state`:
  - `"tiered_ll_k_crit"` — static k from dry-run
  - `"tiered_ll_k_dynamic"` — live k (None if dynamic disabled or not yet fired)
  - `"tiered_ll_phase"` — `"tiered_rounds"` | `"backfill"` | `"complete"`
  - `"tiered_ll_round"` — current round number during Phase 1

---

## Tests (`tests/test_tiered_ll.py`)

- [ ] `test_dry_run_returns_valid_k`: k_crit ≥ 1 and ≤ total rounds on a standard cohort.
- [ ] `test_backfill_uses_remaining_prefs`: after switching at k, students' preference
  lists passed to backfill start at index k (not 0).
- [ ] `test_zero_empty_labs_when_structurally_possible`: on a well-distributed cohort,
  `tiered_ll` produces 0 empty labs.
- [ ] `test_dynamic_k_agrees_with_static_on_clean_cohort`: no tie-break sensitivity →
  dynamic k == static k.
- [ ] `test_dynamic_k_adjusts_when_stall_earlier`: construct a cohort where a
  CPI-deterministic dry-run misses an earlier stall that only appears under specific
  tie-break choices; verify dynamic check catches it.
- [ ] `test_overflow_flagged_correctly`: cohort where remaining prefs after k are all
  full → overflow students reported, not silently unassigned.
- [ ] `test_meta_fields_always_present`: `k_crit_static`, `dry_run_empty_labs`,
  `dry_run_rounds_total` in meta after phase0.
- [ ] Regression: `tiered_rounds`, `least_loaded`, `cpi_fill`, `nonempty` unaffected.

---

## Documentation (`docs/policy_tiered_ll.md`)

- [ ] Pipeline diagram: Phase 0a (tiering) → Phase 0b (dry-run, k_crit) →
  Phase 1 (tiered rounds 1..k) → Phase 2 (LL-HP backfill).
- [ ] Stopping criterion definition with formal notation.
- [ ] Static vs dynamic k: when they agree, when they diverge, what the operator sees.
- [ ] Trade-offs vs `tiered_rounds` (fully interactive but no empty-lab guarantee)
  and `least_loaded` (no round structure but simpler).
- [ ] Known limitations: dry-run assumes CPI tie-breaking; actual manual choices may
  shift k; dynamic mode mitigates this.

## CLAUDE.md

- [ ] Add `tiered_ll` to the policy table and `ALLOCATION_POLICY` constant docs.
