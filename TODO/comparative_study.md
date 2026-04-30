# TODO: Comparative Policy Study — 2019 & 2020 Real Data

**Goal:** Run all five policies (LL, adaptive-LL, CPI-Fill, tiered_rounds, tiered_ll)
on the 2019 and 2020 real cohort data; collect and compare metrics; produce a
structured report alongside the existing synthetic-data study.

**Prerequisite:** `tiered_ll` policy implementation must be complete before it can
be included. All other four policies can be run immediately.

---

## 0. Data Preparation

- [ ] **Locate real data**: 2019 and 2020 preference sheets and faculty lists are not
  in the repo. Confirm file paths with the team; do not commit raw data.
- [ ] **Preprocess**: run `scripts/make_preference_sheet.py` on each raw Google Form
  export to produce `preference_sheet_{year}.csv` and `faculty_list_{year}.csv`.
  Alternatively use the app's **Clean & Load** button and export the cleaned CSVs.
- [ ] **Anonymise**: run the anonymiser script (if applicable) before any output
  files are committed or shared.
- [ ] **Validate**: run `validate_preferences` on both cohorts; log any missing
  faculty references or malformed rows.
- [ ] **Store**: place processed files in `test/{year}/preference_sheet.csv` and
  `test/{year}/faculty_list.csv`. Add a `.gitignore` entry if the data is not to
  be committed.

---

## 1. Cohort Profiles

Compute and record for each year:

- [ ] S (students), F (faculty), S/F ratio.
- [ ] CPI distribution: min, max, mean, std, percentiles (70th, 90th).
- [ ] Tier breakdown (A / B / C counts) under percentile mode.
- [ ] Preference list length distribution (min, max, median).
- [ ] Faculty max-load distribution.
- [ ] Empty-lab risk at baseline LL caps: `check_empty_lab_risk` result, C_remaining.

Write profiles to `reports/comparison/{year}_cohort_profile.md`.

---

## 2. Run Matrix

Policies × Datasets = 10 runs (+ tiered_ll when ready = 12 runs).

| Policy         | 2019 | 2020 |
|----------------|------|------|
| least_loaded   |  ✓   |  ✓   |
| adaptive_ll    |  ✓   |  ✓   |
| cpi_fill       |  ✓   |  ✓   |
| tiered_rounds  |  ✓   |  ✓   |
| tiered_ll      |  —   |  —   |  ← add when implemented

- [ ] **Script**: write `stats/run_real_study.py` (or use `python -m allocator.analyze
  compare` once CLI TODO lands) to run all policies on both datasets in sequence.
- [ ] **Tie-breaking**: `tiered_rounds` and `tiered_ll` must use `--auto-tiebreak`
  (CPI-based) for reproducibility. Note this in the report.
- [ ] **Seeded reproducibility**: set `random.seed(42)` for any stochastic steps.
- [ ] **Output per run**: `allocation_result_{policy}.csv` + `metrics_{policy}.json`
  written to `reports/comparison/{year}/`.

---

## 3. Metrics to Collect

For each run collect:

| Metric          | Description                                      |
|-----------------|--------------------------------------------------|
| NPSS            | CPI-weighted preference satisfaction score       |
| PSI             | Equal-weighted preference satisfaction score     |
| Empty labs      | Count of faculty with zero assigned students     |
| Assigned        | Count of successfully assigned students          |
| Overflow        | Students assigned beyond their N_tier cap        |
| MSES            | Mean squared entropy of advisor loads            |
| LUR             | Load utilisation ratio                           |
| ERR             | Equity retention rate                            |
| CPI skewness    | Skewness of CPI distribution across advisors     |
| k_crit          | Critical round (tiered_ll only)                  |
| Structural flag | Whether a structural deficit was detected        |

- [ ] Compute all metrics via `compute_metrics` in `metrics.py`.
- [ ] Record `tiered_ll`-specific fields (k_crit_static, k_crit_dynamic, backfill
  size) when that policy is included.

---

## 4. Report

- [ ] Write `reports/comparison/real_data_report.md` with:
  - Cohort profiles (§1).
  - Per-dataset comparison table (one table per year, policies as rows, metrics
    as columns). Highlight best value per metric column.
  - Cross-year observations: does policy ranking change between 2019 and 2020?
    Are any metrics sensitive to cohort size / CPI distribution differences?
  - Policy-specific notes: adaptive_ll cap expansion (N_A, N_B before/after),
    tiered_rounds stall details (if any), tiered_ll handoff round.
  - Comparison with synthetic-data study (`stats/policy_report.md`): do real-data
    results align with synthetic trends?
- [ ] Generate PDF from Markdown (pandoc + xelatex, same pipeline as other docs).

---

## 5. Statistical Significance (optional, if data permits)

- [ ] If multiple real-data cohorts become available (beyond 2019/2020), run a
  paired significance test (Wilcoxon signed-rank) on NPSS and PSI across policies,
  consistent with the methodology in `stats/policy_report.md`.
- [ ] Otherwise note explicitly that two cohorts are insufficient for significance
  testing and results are descriptive only.

---

## 6. Prerequisites Checklist

- [ ] CLI `--auto-tiebreak` flag implemented (see `TODO/cli_all_policies.md`).
- [ ] `run_full_allocation` supports `tiered_rounds` with auto tie-break.
- [ ] `tiered_ll` implemented (see `TODO/tiered_ll_policy.md`) — required for full
  5-policy matrix; run 4-policy matrix first if needed.
- [ ] Real data access confirmed and preprocessing complete (§0).
