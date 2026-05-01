# CPI-Fill Policy Implementation TODO

Implementation checklist for the **CPI-Fill** allocation policy in `src/allocator/allocation.py`.

---

## Overview

The CPI-Fill policy is a new **selectable option** added alongside the existing `"least_loaded"` policy in the existing app. When selected (`policy="cpi_fill"`), it routes to a two-phase procedure instead of `main_allocation`; the existing policies and their behaviour are unchanged. The two-phase procedure is:

**Phase 1 — CPI-ordered (with stopping condition)**

- All unassigned students are processed in strictly decreasing CPI order (tie-break: student ID). This can go tier-wise but without any `N_tier` cap.
- Each student is assigned to the advisor by preference order without exceeding maximum capacity of advisor.
- After each assignment, check: `len(unassigned) == len(empty labs)`. If so, stop Phase 1 immediately.

**Phase 2 — Empty-lab fill**

- The remaining unassigned students (exactly as many as there are empty labs) are processed in decreasing CPI order.
- Each student is assigned to the **highest-preferred empty lab** currently remaining on their full preference list (no `N_tier` cap — global search).
- Since preferences cover all `F` faculty, every student will find an empty lab somewhere in their list.

Round 1 is now not required.

---

## Stopping condition mechanics

Let `U` = number of unassigned students, `E` = number of faculty with `current_load == 0`.

| Assignment goes to | Effect on U | Effect on E | Effect on U − E |
| ------------------ | ----------- | ----------- | --------------- |
| Non-empty lab      | −1          | 0           | −1              |
| Empty lab          | −1          | −1          | 0               |

Phase 1 shrinks `U − E` by 1 with every assignment to a non-empty lab and leaves it unchanged when an empty lab is used. It terminates as soon as `U − E == 0`.

**Entry conditions to handle before Phase 1 begins:**

- [ ] If `U == E` already (e.g., Round 1 left exactly as many unassigned students as empty labs) → skip Phase 1 entirely, proceed directly to Phase 2.
- [ ] If `U < E` (more empty labs than unassigned students) → this violates the protocol's min-load guarantee; Proceed with a warning 'Not enough students to guarantee non-empty labs.'
- [ ] If `E == 0` (no empty labs after Round 1) → Phase 2 is a no-op; run Phase 1 to completion as a normal CPI-ordered highest-preferred eligible pass.

---

## 1. New helper — `_highest_preferred_empty`

```python
def _highest_preferred_empty(
    student: Student,
    faculty_map: Dict[str, Faculty],
    faculty_loads: Dict[str, int],
) -> Optional[Tuple[str, int]]:
```

- [ ] Iterate through `student.preferences` in order (full list, no `N_tier` cap).
- [ ] Return `(faculty_id, rank_1based)` for the **first** faculty whose `faculty_loads[fid] == 0`.
- [ ] Return `None` if no empty lab is found in the preference list (should not occur if preferences cover all `F` faculty and at least one empty lab remains, but handle defensively).

> This is Phase 2's selection rule. If no empty lab is found, it is a hard error condition, not a fallback.

---

## 2. New function — `cpi_fill_allocation`

```python
def cpi_fill_allocation(
    students: List[Student],
    faculty: List[Faculty],
    assignments: Dict[str, Optional[str]],
    faculty_loads: Dict[str, int],
    snapshots: SnapshotList,
) -> Tuple[Dict[str, Optional[str]], SnapshotList]:
```

This function is invoked **in place of** `main_allocation` only when `policy="cpi_fill"` is selected; `main_allocation` remains intact and is still called for all other policy values. It does **not** take `N_A`, `N_B`, or `policy` parameters — those belong to `main_allocation`.

### 2.1 — Setup

- [ ] Build `faculty_map`, `student_map` from the input lists.
- [ ] Compute `unassigned = {sid for sid, fid in assignments.items() if fid is None}`.
- [ ] Compute `empty_labs = {fid for fid, load in faculty_loads.items() if load == 0}` as a mutable set, kept in sync throughout both phases.
- [ ] Validate entry conditions (see §0 above).
- [ ] Record a "CPI-Fill begins" snapshot: log `U`, `E`, and `U − E`.

### 2.2 — Phase 1 loop

- [ ] Sort unassigned students by CPI descending, tie-break by student ID:
      `phase1_queue = _sorted_by_cpi([student_map[sid] for sid in unassigned])`.
- [ ] Iterate through `phase1_queue`. For each student `s`:
  1. **Stopping condition check** (before attempting assignment):
     `if len(unassigned) == len(empty_labs): break`.
  2. Build `cap = s.preferences[:s.n_tier]` (use `s.n_tier`; for Class C `n_tier is None` → use `s.preferences` in full).
  3. Call `_least_loaded_choice(s, cap, faculty_map, faculty_loads)` → `(fid, rank)` or `None`.
  4. If `None` (all N_tier advisors are at max capacity) → skip this student for Phase 1; they carry into Phase 2 along with the stopping-condition remainder.
  5. Otherwise: assign, update `faculty_loads[fid]`, update `unassigned`, update `empty_labs` (remove `fid` if `faculty_loads[fid]` just became 1), append snapshot.
- [ ] After the loop, append a "Phase 1 complete" snapshot: log how many students were assigned, current `U`, `E`.

### 2.3 — Phase 2 loop

- [ ] Sort remaining unassigned students by CPI descending, tie-break by student ID:
      `phase2_queue = _sorted_by_cpi([student_map[sid] for sid in unassigned])`.
- [ ] Append a "Phase 2 begins" snapshot: log `len(phase2_queue)` students and `len(empty_labs)` empty labs.
- [ ] Iterate through `phase2_queue`. For each student `s`:
  1. Call `_highest_preferred_empty(s, faculty_map, faculty_loads)` → `(fid, rank)` or `None`.
  2. If `None` → raise `RuntimeError` (no empty lab available; indicates a protocol-state inconsistency).
  3. Assign, update `faculty_loads[fid]`, update `unassigned`, remove `fid` from `empty_labs`, append snapshot.
- [ ] Append a "Phase 2 complete" snapshot.
- [ ] Append a "Final" snapshot identical in format to the one in `main_allocation`:
      `"Allocation complete | assigned=... | unassigned=..."`.

### 2.4 — Return

- [ ] Return `(assignments, snapshots)` — same signature as `main_allocation`.

---

## 3. Wire into `run_full_allocation`

```python
def run_full_allocation(
    ...,
    policy: str = "least_loaded",   # existing; "cpi_fill" added as a third valid value
) -> Tuple[Dict, SnapshotList, dict, dict]:
```

- [ ] Add `"cpi_fill"` to the `_POLICIES` set (currently in `main_allocation`; move it to `run_full_allocation` or duplicate it here for the routing check).
- [ ] After `round1(...)`, branch on `policy`:
  ```python
  if policy == "cpi_fill":
      assignments, snaps = cpi_fill_allocation(
          students, faculty, assignments, faculty_loads, snaps
      )
  else:
      assignments, snaps = main_allocation(
          students, faculty, assignments, faculty_loads, snaps, N_A, N_B, policy
      )
  ```
- [ ] `cpi_fill_allocation` does not receive `N_A` / `N_B` — it reads `n_tier` directly from each `Student` object, which was set by `phase0`. No further changes to `phase0` or `round1` are needed.
- [ ] Update the `run_full_allocation` docstring to document `"cpi_fill"` as a third policy option.

---

## 4. Expose in CLI (`allocation.py` → `_cli`)

- [ ] Add `"cpi_fill"` as a valid choice for the `--policy` argument.
- [ ] Update the help text to describe the two-phase behaviour.

---

## 5. Expose in the Dash app (`app.py`)

- [ ] Add `"cpi_fill"` as a selectable policy option in the existing policy-selector UI.
- [ ] Display the Phase 1 / Phase 2 boundary in the snapshot timeline so operators can see exactly where the stopping condition fired and which students were handled by each phase.

---

## 6. Tests

Add to `tests/test_allocation.py` (or create `tests/test_cpi_fill.py`).

- [ ] **Test 1 — Phase 1 stopping condition fires correctly**: construct a cohort where `U > E` after Round 1; verify Phase 1 stops when `len(unassigned) == len(empty_labs)`, not before or after.
- [ ] **Test 2 — Phase 2 fills all empty labs**: after a full CPI-Fill run, verify `faculty_loads[fid] >= 1` for every faculty and `len(unassigned) == 0`.
- [ ] **Test 3 — Phase 2 respects preference order**: student has two empty labs in their list at positions 2 and 5; verify they are assigned to position 2, not 5.
- [ ] **Test 4 — Phase 2 adapts to dynamic empty-lab state**: two Phase 2 students share the same highest-preferred empty lab; verify the first gets it and the second moves to their next empty lab.
- [ ] **Test 5 — U == E at entry, Phase 1 skipped**: Round 1 leaves exactly as many unassigned students as empty labs; verify Phase 1 produces zero assignments and only Phase 2 runs.
- [ ] **Test 6 — E == 0 after Round 1**: all faculty received a first-choice pick; verify the policy runs Phase 1 to completion and Phase 2 is a no-op (no empty labs to fill).
- [ ] **Test 7 — U < E raises RuntimeError**: construct a state where fewer students are unassigned than there are empty labs; verify `cpi_fill_allocation` raises `RuntimeError` before doing any assignments.
- [ ] **Test 8 — CPI ordering in Phase 1**: verify that a higher-CPI student who appears later in the input list is processed before a lower-CPI student who appears earlier.
- [ ] **Test 9 — N_tier window respected in Phase 1**: a student's `N_tier`-th advisor is full but their `(N_tier+1)`-th is not; verify the student is skipped in Phase 1 and carried to Phase 2.
- [ ] **Test 10 — Full run via `run_full_allocation`**: pass `policy="cpi_fill"`, verify the returned `assignments` dict has no `None` values and `metrics` keys are present.

---

## 7. Checklist summary

| #       | Task                                         | File(s) touched                |
| ------- | -------------------------------------------- | ------------------------------ |
| 1       | `_highest_preferred_empty` helper            | `allocation.py`                |
| 2.1–2.4 | `cpi_fill_allocation` function               | `allocation.py`                |
| 3       | Route `"cpi_fill"` in `run_full_allocation`  | `allocation.py`                |
| 4       | `--policy cpi_fill` CLI flag                 | `allocation.py`                |
| 5       | Policy selector + phase boundary in timeline | `app.py`                       |
| 6       | Unit tests                                   | `tests/test_cpi_fill.py` (new) |
