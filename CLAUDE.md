# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

```bash
conda env create -f environment.yml   # one-time setup
conda activate allocator
```

## Commands

**Run the app:**
```bash
PYTHONPATH=src python -m allocator.app
# → http://127.0.0.1:8050
```

**Run tests:**
```bash
conda run -n allocator python -m pytest tests/ -v
conda run -n allocator python -m pytest tests/test_metrics.py -v    # metrics only
conda run -n allocator python -m pytest tests/test_cpi_fill.py -v   # CPI-Fill only
```

**Phase-0 CLI (no GUI):**
```bash
PYTHONPATH=src python -m allocator.allocation --phase0-only \
  --students data/sample_students.csv \
  --faculty data/sample_faculty.csv \
  --out reports/
```

**Full allocation CLI (with policy selection):**
```bash
PYTHONPATH=src python -m allocator.allocation \
  --students data/sample_students.csv \
  --faculty data/sample_faculty.csv \
  --policy least_loaded   # or: nonempty | cpi_fill  (tiered_rounds requires the GUI)
  --out reports/
```

**Policy comparison study (stats folder):**
```bash
PYTHONPATH=src python stats/run_study.py
# → generates 4 synthetic datasets + runs both policies on all 5 datasets
# → writes stats/policy_report.md
```

**Preprocess form exports:**
```bash
python scripts/make_preference_sheet.py form_responses.csv
# → preference_sheet.csv, faculty_list.csv
```

## Architecture

### Package layout (`src/allocator/`)

| File | Role |
|------|------|
| `app.py` | Dash web app: layout, all callbacks, global `_app_state` dict |
| `allocation.py` | Core engine: Phase 0 (tiering), Round 1, main allocation, CPI-Fill Phase 1/2 |
| `state.py` | Dataclasses: `Student`, `Faculty`, `AllocationSnapshot`, `SnapshotList` |
| `data_loader.py` | CSV/Excel I/O, raw Google Form column normalisation, preprocessing pipeline (`preprocess_students`), validation, Phase-0 report read/write |
| `visualizer.py` | Plotly figure builders: bipartite graph, load bars, step log, stats panel |
| `metrics.py` | NPSS (CPI-weighted, full-list denominator) and PSI (equal-weighted) satisfaction scores |

### Data flow

```
Load CSVs → Phase 0 (tier + N_tier + max_load)
  → Round 1 (interactive first-choice pass)  [skipped for cpi_fill policy]
  → Main Allocation  OR  CPI-Fill Phase 1 → Phase 2
  → NPSS/PSI metrics → 4-panel visualization → CSV/HTML export
```

### Allocation policies (set via `ALLOCATION_POLICY` in `app.py`)

- **`least_loaded`** *(default)* — Phase 0 → Round 1 → class-wise assignment to the least-loaded advisor within the student's `N_tier` window; ties broken by preference rank. See `docs/policy_least_loaded.md`.
- **`nonempty`** — Phase 0 → Round 1 → class-wise assignment preferring the highest-preferred **empty lab** (load = 0) first; falls back to highest-preferred advisor with remaining capacity. See `docs/policy_nonempty.md`.
- **`cpi_fill`** — Phase 0 → CPI-Fill Phase 1 (students processed in descending CPI order, assigned to highest-preferred advisor with capacity, stops when `unassigned == empty_labs`) → Phase 2 (each remaining student goes to their highest-preferred empty lab). Round 1 is **skipped**. See `docs/policy_cpi_fill.md`.
- **`tiered_rounds`** — Phase 0 (tier classification, diagnostic only) → Preference Rounds: in round *n* every unassigned student offers their *n*-th preference; each advisor picks at most one student per round (highest CPI wins; ties require a manual pick). Runs until all students assigned or a stall is detected. See `docs/policy_tiered_rounds.md`.

### NPSS formula

NPSS uses `score_i = (F − p_i + 1) / F` where F = total number of faculty (full preference list length). This denominator is the same for all four policies, enabling cross-policy comparison. Overflow (rank > N_tier) is tracked separately as a diagnostic; it no longer clips the NPSS score to 0.

### Snapshot/replay model

Every allocation step appends an `AllocationSnapshot` to `SnapshotList`. The Dash UI steps through snapshots for interactive replay. `_app_state` in `app.py` is the single source of truth for runtime state; `phase0_snapshots` is a checkpoint used by the Reset button.

### Tiering (Phase 0)

- **Percentile mode** (default): Class A ≥ 90th, Class B 70–90th, Class C < 70th; ±0.1 grace band
- **Quartile mode** (triggered if >40% cluster in one band): A top 25%, B1/B2 middle 50%, C bottom 25%
- **Tiny cohort** (S < 10): all students → Class A
- N_tier window: A → 3 (4 if S/F > 4), B → 5 (6 if S/F > 4), C → full list

### App startup modes (`app.py` top-level constants)

```python
OUTPUT_MODE = "dash"        # "dash" | "html"
STARTUP_MODE = "full"       # "full" | "phase0_only" | "from_report"
ALLOCATION_POLICY = "least_loaded"
```

## Input file formats

**students.csv (pre-processed):** `student_id, name, cpi, pref_1, pref_2, ...` — faculty IDs in preference columns
**students (raw form export):** Google Form column names (`Roll No.`, `CPI (as on date)`, `Preference  1`, …) are normalised automatically by `preprocess_students` when using the app's **Clean & Load** button, or by running `scripts/make_preference_sheet.py` offline.
**faculty.csv:** `faculty_id, name, max_load` — `max_load` optional; blank → Phase 0 fills with `floor(S/F) + 1`

Sample data: `data/sample_students.csv` (24 students, 8 faculty)

## Key documentation

- `MSThesisAllocationProtocol.md` — full protocol specification
- `NPSS_Metric.md` — NPSS/PSI metric definitions
- `docs/policy_least_loaded.md` — `least_loaded` policy: pipeline, assignment rule, trade-offs
- `docs/policy_nonempty.md` — `nonempty` policy: pipeline, assignment rule, trade-offs
- `docs/policy_cpi_fill.md` — `cpi_fill` policy: Phase 1/2 mechanics, stopping condition, trade-offs
- `docs/policy_tiered_rounds.md` — `tiered_rounds` policy: round mechanics, tie-breaking, audit trace
- `stats/policy_report.md` — empirical comparison of `least_loaded` vs `cpi_fill` across 5 datasets
