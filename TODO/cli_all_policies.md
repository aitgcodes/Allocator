# TODO: CLI Mode for All Policies and Analysis

**Goal:** Extend `python -m allocator.allocation` to support all five policies
(including `adaptive_ll`, `tiered_rounds`, and the forthcoming `tiered_ll`), and
add a separate `python -m allocator.analyze` entry-point for post-allocation
metrics and cross-policy comparison reporting.

---

## 1. Extend `allocation.py` CLI (`python -m allocator.allocation`)

### Policy coverage
- [ ] Add `adaptive_ll` to `--policy` choices and help text. Document that it runs
  Phase 0 with cap optimization (`optimize=True`) and otherwise follows the LL
  assignment rule.
- [ ] Add `tiered_rounds` to `--policy` choices. Since `tiered_rounds` requires
  interactive tie-breaking, the CLI must handle this non-interactively:
  - [ ] Add `--auto-tiebreak` flag (default: highest-CPI wins). When set, all
    tie-break decisions are resolved automatically; no operator prompt is issued.
  - [ ] Without `--auto-tiebreak`, emit an error explaining that `tiered_rounds`
    requires the GUI or `--auto-tiebreak` for CLI use.
- [ ] Add `tiered_ll` to `--policy` choices once the policy is implemented.
  Document `--dynamic-k` flag (see below).

### New flags
- [ ] `--auto-tiebreak` (flag): resolve `tiered_rounds` / `tiered_ll` Phase-1
  tie-breaks automatically by CPI rank. Ignored for other policies.
- [ ] `--dynamic-k` (flag, `tiered_ll` only): enable per-round dynamic stopping
  criterion during Phase 1. Ignored for other policies.
- [ ] `--metrics` (flag): print NPSS, PSI, and advisor metrics (MSES, LUR, ERR,
  CPI skewness) to stdout after allocation, in addition to writing the CSV report.
- [ ] `--format` (`csv` | `json`, default `csv`): output format for the allocation
  result. JSON useful for programmatic consumption in `analyze` and `run_study`.

### Output
- [ ] Write `allocation_result.csv` (student → faculty mapping) to `--out`.
- [ ] Write `metrics.json` alongside the CSV when `--metrics` is set.
- [ ] Print a concise summary table to stdout:
  ```
  Policy        : adaptive_ll
  Assigned      : 24 / 24
  Empty labs    : 0
  NPSS          : 0.847
  PSI           : 0.831
  k_crit        : 3  (tiered_ll only)
  ```

### Error handling
- [ ] Validate that `tiered_rounds` / `tiered_ll` + no `--auto-tiebreak` → clear
  error message pointing to GUI or flag.
- [ ] Validate `--from-report` + `--policy adaptive_ll` warns that cap optimization
  was already applied; caps from meta are used as-is.

---

## 2. Analysis CLI (`python -m allocator.analyze`)

A new entry point for post-allocation analysis and cross-policy comparison.
Lives in a new file `src/allocator/analyze.py`.

### Subcommands

#### `metrics` — compute metrics for a single allocation result
```
python -m allocator.analyze metrics \
  --students data/students.csv \
  --faculty  data/faculty.csv \
  --result   reports/allocation_result.csv \
  [--out     reports/]
```
- [ ] Load assignment CSV, recompute NPSS / PSI / advisor metrics.
- [ ] Print formatted table to stdout; write `metrics.json` to `--out`.

#### `compare` — run multiple policies and produce a comparison report
```
python -m allocator.analyze compare \
  --students data/students.csv \
  --faculty  data/faculty.csv \
  --policies least_loaded adaptive_ll cpi_fill tiered_rounds tiered_ll \
  --auto-tiebreak \
  --out      reports/comparison/ \
  [--format  md | json | csv]
```
- [ ] Run `run_full_allocation` for each listed policy on the same cohort.
- [ ] Collect metrics per policy into a unified table.
- [ ] Write `comparison_report.md` (and optionally `.json` / `.csv`) to `--out`.
- [ ] Report: per-policy NPSS, PSI, empty labs, MSES, LUR, ERR, CPI skewness,
  assigned count; plus a summary row highlighting the best value per metric.
- [ ] Flag structural issues per policy (e.g. `tiered_rounds` stall, `adaptive_ll`
  structural deficit).

#### `study` — replace / supersede `stats/run_study.py`
```
python -m allocator.analyze study \
  --students data/students.csv \
  --faculty  data/faculty.csv \
  --synthetic-seeds 42 7 13 99 \
  --policies least_loaded adaptive_ll cpi_fill \
  --out      stats/
```
- [ ] Subsume the logic from `stats/run_study.py` into this subcommand.
- [ ] Accept real data + N synthetic variants (seeded); run all listed policies on all
  datasets; produce `policy_report.md` in `--out`.
- [ ] `stats/run_study.py` can be kept as a thin wrapper calling this subcommand for
  backward compatibility, or deprecated with a note.

---

## 3. CLAUDE.md Updates

- [ ] Update **Commands** section: add `analyze` entry-point with subcommand examples.
- [ ] Update `--policy` choices in the full allocation CLI example to include all five
  policies.
- [ ] Note `--auto-tiebreak` requirement for `tiered_rounds` / `tiered_ll` in CLI mode.
