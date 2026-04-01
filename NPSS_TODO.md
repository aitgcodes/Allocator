# Metrics Implementation TODO

Implementation checklist for student satisfaction metrics in `src/allocator/`.

**Primary metric** — **NPSS** (Normalized Preference Satisfaction Score): tier-aware, CPI-weighted, window-enforcing.
**Secondary metric** — **PSI** (Preference Satisfaction Index): global rank score, equal-weighted, policy-agnostic.

---

## 1. Create `src/allocator/metrics.py`

This is the only new file required. Everything else is wiring it in.

---

### 1.1 — `collect_preference_ranks`

```python
def collect_preference_ranks(
    students: List[Student],
    assignments: Dict[str, Optional[str]],
) -> Dict[str, Optional[int]]:
```

- [ ] For each student `s`, look up `assignments[s.id]` to get the assigned faculty ID.
- [ ] If assigned, find the 1-based position of that faculty ID in `s.preferences`
      (`s.preferences.index(assigned_fid) + 1`).
- [ ] Since the updated protocol guarantees preferences cover **all F faculty**, the faculty ID
      will always be found in `s.preferences` — treat a missing entry as `None` only as a
      defensive fallback.
- [ ] Return `{student_id: rank_or_None}`.

> **Why recompute instead of reading from snapshots?**
> `AllocationSnapshot.preference_rank` only stores the rank of the *one student assigned at that step*.
> Reconstructing from the final `assignments` dict + each student's `.preferences` list is simpler
> and more reliable.

---

### 1.2 — `npss_per_student_score`

```python
def npss_per_student_score(
    student: Student,
    rank: Optional[int],
) -> float:
```

- [ ] If `rank is None` → return `0.0` (unassigned or faculty not in preference list).
- [ ] Determine `n` = effective window size:
  - Class A / B / B1 / B2: `student.n_tier` (already capped to `len(student.preferences)` in Phase 0).
  - Class C (`student.n_tier is None`): use `len(student.preferences)` as the denominator.
    If `len(student.preferences) == 0` → return `0.0`.
- [ ] If `rank > n` (outside protection window) → return `0.0`.
- [ ] Otherwise → return `(n - rank + 1) / n`.
- [ ] Edge case: `n == 1` → score is 1.0 (1st choice) or 0.0 only.

---

### 1.3 — `psi_per_student_score`

```python
def psi_per_student_score(
    rank: Optional[int],
    F: int,
) -> float:
```

- [ ] If `rank is None` → return `0.0`.
- [ ] If `F <= 1` → return `1.0` (degenerate: only one faculty, no meaningful scale).
- [ ] Return `1.0 - (rank - 1) / (F - 1)`.
- [ ] Result is always in `[0, 1]`: 1.0 at rank 1, 0.0 at rank F.

> PSI uses F as its denominator because preferences cover the entire faculty list.
> It makes no distinction between tiers or protection windows — every student is scored
> on the same scale regardless of class.

---

### 1.4 — `compute_npss` (primary metric)

```python
def compute_npss(
    students: List[Student],
    ranks: Dict[str, Optional[int]],
) -> dict:
```

- [ ] Compute `total_cpi = sum(s.cpi for s in students)`. Guard against zero (raise or default to equal weights).
- [ ] For each student:
  - `w_i = s.cpi / total_cpi`
  - `score_i = npss_per_student_score(s, ranks[s.id])`
- [ ] Aggregate: `npss = sum(w_i * score_i for all i)`.
- [ ] Compute per-tier breakdown (see §1.6).
- [ ] Return results dict (see §1.7).

---

### 1.5 — `compute_psi` (secondary metric)

```python
def compute_psi(
    students: List[Student],
    ranks: Dict[str, Optional[int]],
    F: int,
) -> dict:
```

- [ ] For each student:
  - `score_i = psi_per_student_score(ranks[s.id], F)`
- [ ] Aggregate: `mean_psi = sum(score_i) / len(students)`. Guard against empty cohort.
- [ ] Compute per-tier breakdown: mean PSI score broken down by tier label
      (`"A"`, `"B"`, `"B1"`, `"B2"`, `"C"`), for diagnostic comparison with NPSS.
- [ ] Return results dict (see §1.7).

---

### 1.6 — Shared per-tier breakdown (used by both metrics)

For each tier label (`"A"`, `"B"`, `"B1"`, `"B2"`, `"C"`), compute:

- [ ] `count`: number of students with that original `.tier` label (students merged into a later
      tier during allocation retain their original label and are counted here).
- [ ] **NPSS-specific**:
  - `within_window_rate`: fraction of students in the tier with `rank <= n_tier` (not `None`).
  - `mean_npss_score`: mean of `npss_per_student_score` values for the tier.
- [ ] **PSI-specific**:
  - `mean_psi_score`: mean of `psi_per_student_score` values for the tier.
- [ ] **Shared**:
  - `mean_rank`: arithmetic mean of `rank` values for assigned students in the tier
    (skip `None`; report `None` if tier is empty or all are `None`).
  - `overflow_count`: students with `rank is None` or `rank > n_tier` (NPSS window definition).

---

### 1.7 — Top-level `compute_metrics`

```python
def compute_metrics(
    students: List[Student],
    assignments: Dict[str, Optional[str]],
    F: int,
) -> dict:
```

- [ ] Call `collect_preference_ranks(students, assignments)` → `ranks`.
- [ ] Call `compute_npss(students, ranks)` → `npss_results`.
- [ ] Call `compute_psi(students, ranks, F)` → `psi_results`.
- [ ] Return a unified results dict with the structure below.

```python
{
    # ── Primary metric ─────────────────────────────────────────────────────
    "npss": float,               # CPI-weighted, tier-aware ∈ [0, 1]
    "overflow_count": int,       # students placed outside their N_tier window

    # ── Secondary metric ────────────────────────────────────────────────────
    "mean_psi": float,           # equal-weighted global rank score ∈ [0, 1]

    # ── Per-tier breakdown ──────────────────────────────────────────────────
    "per_tier": {
        "<tier_label>": {
            "count": int,
            "mean_rank": float | None,
            "within_window_rate": float,   # NPSS window definition
            "mean_npss_score": float,
            "mean_psi_score": float,
        },
        ...
    },

    # ── Per-student detail ──────────────────────────────────────────────────
    "per_student": {
        "<student_id>": {
            "tier": str,
            "n_tier": int | None,
            "assigned_rank": int | None,
            "npss_score": float,
            "psi_score": float,
            "cpi_weight": float,           # student's share of total CPI
        },
        ...
    },
}
```

---

## 2. Wire into `allocation.py`

### 2.1 — Import

```python
from .metrics import compute_metrics
```

- [ ] Add this import.

### 2.2 — Update `run_full_allocation`

```python
def run_full_allocation(...) -> Tuple[Dict, SnapshotList, dict, dict]:
```

- [ ] After `main_allocation(...)` returns, call `compute_metrics(students, assignments, F=len(faculty))`.
- [ ] Add `metrics` as a 4th return value.
- [ ] Update the return type annotation and docstring.
- [ ] Update all call sites (`app.py`, CLI `_cli`, any tests) to unpack the new 4th value.

---

## 3. Expose in CLI (`allocation.py` → `_cli`)

- [ ] After `run_full_allocation(...)`, print a summary block:

```
Satisfaction Metrics
--------------------
NPSS (primary)   : 0.87   [CPI-weighted, tier-aware]
Mean PSI (secondary): 0.91   [equal-weighted, global rank]
Overflow count   : 0

Per-tier breakdown:
  Class A  | within-window: 100.0% | mean rank: 1.2 | NPSS: 0.94 | PSI: 0.95 | n=8
  Class B  | within-window:  91.4% | mean rank: 2.7 | NPSS: 0.83 | PSI: 0.88 | n=35
  Class C  | within-window:  88.0% | mean rank: 4.1 | NPSS: 0.71 | PSI: 0.82 | n=25
```

- [ ] Write the full `per_student` table to `reports/metrics_report.csv` with columns:
      `student_id`, `name`, `tier`, `n_tier`, `assigned_rank`, `within_window`,
      `npss_score`, `cpi_weight`, `psi_score`.

---

## 4. Expose in the Dash app (`app.py`)

- [ ] After allocation runs, store `metrics` in app state or as a module-level variable.
- [ ] Add a **Metrics** section to the results panel (below the assignment table):
  - **Primary row**: NPSS as a large number with colour band —
    green ≥ 0.90, yellow ≥ 0.75, red < 0.75.
  - **Secondary row**: Mean PSI displayed alongside NPSS for direct comparison.
    Use a muted style (smaller font or grey label) to signal it is supplementary.
  - Overflow count displayed as a warning badge if > 0.
  - Per-tier table with columns: Tier, Count, Mean Rank, Within-Window %, NPSS, PSI.
- [ ] (Optional) Add a grouped bar chart: one bar per tier, showing NPSS and PSI side by side,
      to visualise where the two metrics agree or diverge.

---

## 5. Tests

Create `tests/test_metrics.py`.

**NPSS tests:**

- [ ] **Test 1 — Perfect allocation**: every student gets their 1st choice → NPSS = 1.0, mean PSI = 1.0.
- [ ] **Test 2 — All overflow**: every student assigned outside their window → NPSS = 0.0;
      mean PSI still > 0 (PSI does not penalise overflow). Verify the two diverge as expected.
- [ ] **Test 3 — Mixed tiers**: construct a small cohort (2 Class A, 3 Class B, 2 Class C)
      with known assignments; verify NPSS against a hand-computed value.
- [ ] **Test 4 — Class C denominator**: a Class C student assigned at rank `k` out of `F` faculty
      scores `(F - k + 1) / F` for NPSS (since `n_tier = None` → uses `F` as denominator).
- [ ] **Test 5 — Tiny cohort** (`S < 10`, all Class A, `n_tier = 2`): student at rank 2 scores
      NPSS = 0.5; student at rank 3 scores NPSS = 0.0; verify PSI values independently.
- [ ] **Test 6 — CPI weighting**: two students with different CPIs; the higher-CPI student's
      score dominates NPSS but not PSI (equal-weighted). Verify the numerical difference.
- [ ] **Test 7 — Zero CPI guard**: a student with `cpi = 0.0` should not cause division-by-zero.

**PSI tests:**

- [ ] **Test 8 — PSI formula**: for F=10, rank=3 → PSI = 1 - 2/9 ≈ 0.778. Verify exactly.
- [ ] **Test 9 — PSI boundary values**: rank=1 → PSI = 1.0; rank=F → PSI = 0.0.
- [ ] **Test 10 — PSI ignores window**: a Class A student at rank 5 (outside N_A=3) should score
      PSI = 1 - 4/(F-1) > 0, while NPSS scores 0.0. Confirm the divergence.
- [ ] **Test 11 — PSI degenerate case**: F=1 → PSI = 1.0 for any assignment.

**Integration test:**

- [ ] **Test 12 — `compute_metrics` round-trip**: run `compute_metrics` on a minimal but complete
      set of students and faculty; assert that `"npss"`, `"mean_psi"`, `"per_tier"`,
      and `"per_student"` keys are all present and values are in `[0, 1]`.

---

## 6. Checklist summary

| # | Task | File(s) touched |
|---|------|-----------------|
| 1.1 | `collect_preference_ranks` | `metrics.py` (new) |
| 1.2 | `npss_per_student_score` | `metrics.py` (new) |
| 1.3 | `psi_per_student_score` | `metrics.py` (new) |
| 1.4 | `compute_npss` | `metrics.py` (new) |
| 1.5 | `compute_psi` | `metrics.py` (new) |
| 1.6–1.7 | `compute_metrics` (unified entry point) | `metrics.py` (new) |
| 2.1 | Import `compute_metrics` | `allocation.py` |
| 2.2 | 4th return value from `run_full_allocation` | `allocation.py` |
| 3 | CLI summary + `metrics_report.csv` | `allocation.py` |
| 4 | Dash metrics panel (primary + secondary) | `app.py` |
| 5 | Unit + integration tests | `tests/test_metrics.py` (new) |
