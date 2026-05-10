# TODO — tiered_ll Backfill Refinement

## Motivation

The current `tiered_ll` backfill (GUI path) is a single CPI-order pass using
`_least_loaded_choice` on `prefs[k:]`. Empty labs (load=0) are naturally picked
as "least loaded" — but this means higher-CPI students absorb empty-lab slots
that would be better preserved for the structured Phase 2 guarantee.

The refined design splits backfill into two explicit phases:

- **Phase 2a** — while `unassigned > empty_labs`: assign one student at a time
  (highest CPI first) to their highest-preferred advisor with remaining capacity
  from `prefs[k:]`.
- **Phase 2b** — when `unassigned == empty_labs`: assign each remaining student to
  their highest-preferred **empty lab** in `prefs[k:]` (one student per lab).

This is structurally identical to CPI-Fill Phase 1 + Phase 2, but operating on
`prefs[k:]` rather than the full preference list.

This guarantees full coverage (no empty labs, no unassigned students when S ≥ F)
while maximising preference satisfaction in both phases.

### Companion change to `find_critical_round`

The current stopping criterion fires at round n when `unassigned_n ≤ empty_labs_n`.
This can overshoot: if `unassigned_n < empty_labs_n` (strictly less), then round n
produced more empty labs than there are students to fill them — Phase 2 backfill
would leave labs empty.

**New rule:** fire at round n−1 when round n produces `unassigned_n < empty_labs_n`.
Only fire at round n (as now) when `unassigned_n == empty_labs_n` (exact match).

| After round n | Old k_crit | New k_crit | Reason |
|---------------|-----------|-----------|--------|
| U_n == E_n | n | n | exact match — backfill at round n |
| U_n < E_n | n | n−1 | round n over-shot; stop before it |
| U_n > E_n | continue | continue | not yet time to switch |

Edge case: if round 1 produces U_1 < E_1, new k_crit = 0 (skip all tiered rounds,
full preference list used by backfill). This is a meaningful behaviour change on
real cohorts where the current k_crit = 1.

---

## Scope of Work

### 1. `src/allocator/allocation.py`

#### 1a. `find_critical_round`

**Current:**
```python
fires = (
    entry["unreachable_faculty_count"] > 0
    or entry["is_stall"]
    or (unassigned > 0 and unassigned <= empty_labs)
)
if fires:
    break
k = entry["round_no"]
```

**New logic:**
- Distinguish `unassigned < empty_labs` (overshoot: k_crit = round_no − 1) from
  `unassigned == empty_labs` (perfect: k_crit = round_no).
- Track the previous round's `round_no` so that when overshoot is detected we can
  return `prev_round_no` (or 0 if round 1 overshoots).
- All other firing conditions (stall, unreachable) remain unchanged at k_crit = round_no.

Pseudocode:
```python
k = 0
prev_round = 0
for entry in dry_run_states:
    unassigned = entry["unassigned_count"]
    empty_labs = entry.get("empty_labs_count", 0)
    round_no   = entry["round_no"]

    if entry["unreachable_faculty_count"] > 0 or entry["is_stall"]:
        k = max(round_no, 1)   # structural stop at current round (min 1)
        break
    if unassigned > 0 and unassigned < empty_labs:
        k = max(prev_round, 0)  # overshot — stop before this round
        break
    if unassigned > 0 and unassigned == empty_labs:
        k = round_no            # exact match — stop here
        break

    prev_round = round_no

# if never fired, k = prev_round (all rounds ran)
if k == 0 and prev_round > 0:
    k = prev_round
```

Update docstring to document the new k_crit=n−1 and k_crit=0 cases.

#### 1b. `tiered_ll_backfill`

**Rewrite** to two-phase logic:

```python
def tiered_ll_backfill(unassigned_students, faculty, assignments, faculty_loads, k, snapshots):
    faculty_map = {f.id: f for f in faculty}
    students_cpi = _sorted_by_cpi(unassigned_students)

    # ── Phase 2a: assign excess students to non-empty labs ──
    # "Excess" = students beyond the count of empty labs.
    # Each iteration: count current empty labs, if unassigned > empty_labs,
    # take the highest-CPI remaining student and assign LL-HP from their
    # non-empty prefs[k:].  Repeat until unassigned ≤ empty_labs.

    remaining = list(students_cpi)
    overflow_p2a = []

    while True:
        empty_count = sum(1 for f in faculty if faculty_loads[f.id] == 0)
        if len(remaining) == empty_count:
            break                           # switch to Phase 2b
        s = remaining.pop(0)               # highest CPI
        # highest-preferred advisor with remaining capacity (not least-loaded)
        preferred = next(
            (fid for fid in s.preferences[k:] if faculty_loads[fid] < faculty_map[fid].max_load),
            None,
        )
        if preferred:
            assignments[s.id] = preferred
            faculty_loads[preferred] += 1
            # append snapshot
        else:
            overflow_p2a.append(s)          # all prefs[k:] at capacity → defer to Phase 2b

    # ── Phase 2b: assign remaining students to their best empty lab ──
    phase2b_students = remaining + overflow_p2a   # maintain CPI order
    empty_lab_ids = {f.id for f in faculty if faculty_loads[f.id] == 0}

    overflow_p2 = []
    for s in phase2b_students:
        preferred_empty = next(
            (fid for fid in s.preferences[k:] if fid in empty_lab_ids), None
        )
        if preferred_empty:
            assignments[s.id] = preferred_empty
            faculty_loads[preferred_empty] += 1
            empty_lab_ids.discard(preferred_empty)
            # append snapshot
        else:
            overflow_p2.append(s)          # no empty lab in prefs[k:]

    return assignments, faculty_loads, overflow_p2
```

Snapshot events should distinguish Phase 2a and Phase 2b in the `phase` field
(e.g., `"TieredLL_Backfill_P2a"` / `"TieredLL_Backfill_P2b"`) for replay clarity.

**Note:** `tiered_ll_cpi_backfill` (CLI path) is unaffected — it already has a
two-phase CPI-fill structure.

---

### 2. `tests/test_tiered_ll.py`

#### Tests to update:
- `test_unassigned_above_empty_labs_does_not_fire` — verify it still passes
  (U > E, should not fire).
- `test_fires_at_exact_match` (if it exists) — k_crit = n when U_n == E_n, unchanged.
- Any test that assumes k_crit = n when U_n < E_n — update to expect k_crit = n−1.

#### New tests to add:
- `test_find_critical_round_overshoot` — dry_run_states where round 3 produces
  U < E; assert k_crit = 2 (not 3).
- `test_find_critical_round_overshoot_at_round1` — U_1 < E_1; assert k_crit = 0.
- `test_tiered_ll_backfill_two_phase_basic` — verify Phase 2a assigns highest-preferred
  with capacity while unassigned > empty_labs, and Phase 2b fills empty labs when
  unassigned == empty_labs.
- `test_tiered_ll_backfill_phase2_prefers_highest_ranked_empty` — student has two
  empty labs in prefs; verify highest-ranked is chosen.
- `test_tiered_ll_backfill_overflow_p2a_goes_to_phase2` — Phase 1 student with no
  non-empty prefs is deferred to Phase 2 and placed in empty lab.

---

### 3. `docs/policy_tiered_ll.md`

- Update **stopping criterion** table: add row for `U_n < E_n → k_crit = n−1`.
- Update **Phase 2** description: replace current LL-HP single-pass with the
  two-phase (non-empty / empty) description.
- Update **pipeline block** to show Phase 2a / Phase 2b labels within the backfill.
- Note k_crit = 0 edge case (skip all tiered rounds, full pref list for backfill).

---

### 4. `stats/run_study.py` — Re-run the 5-policy comparison

No code changes needed; re-run to regenerate `stats/policy_report.md` with updated
`tiered_ll` numbers.

```bash
PYTHONPATH=src python stats/run_study.py
```

Expected direction of change for `tiered_ll`:
- **NPSS / PSI**: likely higher — two-phase backfill places students in preferred
  labs more reliably; Phase 2 guarantees empty-lab preference alignment.
- **Empty labs**: unchanged at 0 (guarantee preserved).
- **MSES**: likely lower (advisors receive more preferred students via Phase 2).
- **ERR**: likely higher (more equitable load distribution with structured Phase 2).
- **Real cohorts**: if k_crit drops from 1 to 0, backfill uses full pref list →
  more options → better NPSS; closing the gap with `tiered_rounds`.

---

### 5. `docs/allocation_presentation.md` + PDF

- Update **Slide 10** (Policy 5 — `tiered_ll`) Phase 2 bullet to match new logic.
- Update **Slide 19** (Summary table) if TLL ratings improve.
- Regenerate PDF:

```bash
PATH="$PATH:/Library/TeX/texbin" pandoc docs/allocation_presentation.md \
  -o docs/allocation_presentation.pdf \
  --pdf-engine=xelatex -t beamer -V theme=Madrid -V fontsize=9pt \
  -V mainfont="Georgia" -V monofont="Menlo" -H /tmp/unicode_symbols.tex
```

---

## Dependency Order

```
Task 1a (find_critical_round)
Task 1b (tiered_ll_backfill)
    └──► Task 2 (tests — run after both 1a and 1b)
    └──► Task 3 (docs/policy_tiered_ll.md)
    └──► Task 4 (re-run study — needs passing tests first)
              └──► Task 5 (update presentation with new numbers)
```

Tasks 1a and 1b can be implemented in parallel.

---

## Risk & Rollback

- The change to `find_critical_round` is a **breaking change** for any test that
  assumes the current `U_n < E_n → k_crit = n` behaviour.
- k_crit = 0 is a new value; check that `tiered_ll_backfill` and app callback
  code handle `k=0` (i.e., `prefs[0:]` = full list) without off-by-one errors.
- The `app.py` callback `_run_tiered_ll_backfill_and_finalize` passes `k_crit`
  directly to `tiered_ll_backfill`; no change needed there, but verify the
  dry-run display message for k_crit=0 is human-readable.
