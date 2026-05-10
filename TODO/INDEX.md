# TODO Index — Implementation Order

Files are ordered by dependency. Complete each stage before moving to the next.
Stages within the same step have no inter-dependency and can be done in parallel.

---

## Step 1 — Data & Script Fixes ✓ COMPLETE

| File | Description |
|------|-------------|
| [`comparison_report_fixes.md`](comparison_report_fixes.md) | Fix duplicate-preference bug in 2020 anonymized CSV, column-name mismatch blocking UI load, and backfill ordering divergence between CLI and UI. |

**Completed 2026-04-30.** Fix A (dedup in anonymize script) applied; Fixes B, C, D
were already in the codebase. Real data anonymization can now be re-run cleanly.

**Blocks:** Step 4 (comparative study on real data).

---

## Step 2 — Core Policy Implementation (no inter-dependencies; parallel with Step 1)

| File | Description |
|------|-------------|
| [`tiered_ll_policy.md`](tiered_ll_policy.md) | Implement the `tiered_ll` policy: dry-run engine, `find_critical_round`, `tiered_ll_backfill`, app integration, state machine, tests, and `docs/policy_tiered_ll.md`. |

**Blocks:** Step 3 (full CLI coverage), Step 4 (5-policy matrix).

---

## Step 3 — CLI Extension ✓ COMPLETE

| File | Description |
|------|-------------|
| [`cli_all_policies.md`](cli_all_policies.md) | Extend `python -m allocator.allocation` to cover all five policies; add `--auto-tiebreak` and `--dynamic-k` flags; add `python -m allocator.analyze` with `metrics`, `compare`, and `study` subcommands. |

**Completed 2026-05-10.** `--auto-tiebreak`, `--dynamic-k`, `--metrics`, `--format` added to `allocation.py` CLI; interactive-policy validation; `allocation_result.csv` always written, `metrics.json` under `--metrics`. New `src/allocator/analyze.py` with `metrics`, `compare`, `study` subcommands. `stats/run_study.py` refactored with `run_study_with_params()` used by `analyze study`. CLAUDE.md updated.

**Blocks:** Step 4 (comparative study).

---

## Step 4 — Comparative Study (needs Steps 1 + 3; full matrix also needs Step 2)

| File | Description |
|------|-------------|
| [`comparative_study.md`](comparative_study.md) | Run LL, adaptive-LL, CPI-Fill, tiered_rounds, tiered_ll on 2019 and 2020 real cohort data; collect all metrics; produce `reports/comparison/real_data_report.md` and PDF. |

**Notes:**
- 4-policy run (excluding `tiered_ll`) can proceed once Steps 1 + 3 (`--auto-tiebreak`) are done.
- Full 5-policy matrix requires Step 2 (`tiered_ll`) and Step 3 (full CLI) to be complete.
- Real data must be preprocessed and anonymized before running (see Step 1).

**Blocks:** Step 5 (docs — policy report section).

---

## Step 5 — Documentation Update (needs all prior steps)

| File | Description |
|------|-------------|
| [`docs_update.md`](docs_update.md) | Audit and rewrite all docs (`policy_*.md`, `NPSS_Metric.md`, `MSThesisAllocationProtocol.md`, `user_manual.md`, `policy_report.md`, `CLAUDE.md`) to reflect current code. Add `docs/policy_tiered_ll.md`. Regenerate PDFs. |

**Notes:**
- Existing policy docs (LL, adaptive-LL, CPI-Fill, tiered_rounds) and metric
  docs can be updated as soon as their implementations are stable — no need to wait for
  Steps 2–4 to complete those sections.
- `tiered_ll` doc and the updated `policy_report.md` must wait for Steps 2 and 4.

---

---

## Step 6 — tiered_ll Backfill Refinement (independent; can start now)

| File | Description |
|------|-------------|
| [`tiered_ll_backfill_refinement.md`](tiered_ll_backfill_refinement.md) | Two-phase LL-HP backfill (Phase 1: non-empty labs while U > E; Phase 2: empty labs when U ≤ E) + `find_critical_round` overshoot fix (k_crit = n−1 when U_n < E_n). Includes tests, doc update, re-running 5-policy study, and regenerating presentation PDF. |

**Blocks:** nothing (self-contained refinement to an existing policy).

---

## Dependency Summary

```
Step 1 (data fixes)
    └──► Step 4 (real-data runs)

Step 2 (tiered_ll policy)
    └──► Step 3 (full CLI)
    └──► Step 4 (5-policy matrix)

Step 3 (CLI — --auto-tiebreak only)
    └──► Step 4 (4-policy matrix)

Steps 1 + 2 + 3 + 4
    └──► Step 5 (docs)
```
