# TODO: Documentation Update — Reflect Current App State

**Goal:** Audit and rewrite all Markdown docs so they describe the app as it stands
today, with no references to superseded designs, old metric definitions, or removed
features. Each doc should be self-contained and verifiable against the current code.

---

## 1. Policy Docs (`docs/policy_*.md`)

### `docs/policy_least_loaded.md`
- [ ] Verify pipeline matches current code: Phase 0 → Round 1 → `main_allocation`
  with LL assignment rule and CPI tie-break.
- [ ] Confirm N_tier window description (standard: N_A=3, N_B=5; scaled S/F>4:
  N_A=4, N_B=6) matches `phase0()`.
- [ ] Remove any references to old metric definitions (pre-ERR, pre-H_norm).
- [ ] Add cross-reference to `adaptive_ll` as the empty-lab-safe variant.

### `docs/policy_adaptive_ll.md`
- [ ] Verify Phase 0b description matches `phase0_optimize_caps`: N_B expands first,
  then N_A, invariant N_A ≤ N_B ≤ F.
- [ ] Document `E_baseline_excess` meta field and what it represents.
- [ ] Document `C_remaining` distinction from total |C| in the empty-lab check.
- [ ] Document the two UI paths: caps optimized (⚠ modal with before/after) vs
  baseline-sufficient (✓ modal).
- [ ] Document structural deficit flag and recommended fallback policies.

### `docs/policy_nonempty.md`
- [ ] Verify assignment rule: highest-preferred empty lab first; falls back to
  highest-preferred advisor with remaining capacity.
- [ ] Confirm no Phase 0b or cap optimization step.
- [ ] Remove any stale metric references.

### `docs/policy_cpi_fill.md`
- [ ] Verify Phase 1 stopping condition: stop when `unassigned == empty_labs`.
- [ ] Verify Phase 2: each remaining student → highest-preferred empty lab (full
  preference list, no n_tier cap).
- [ ] Confirm Round 1 is skipped.
- [ ] Document the `cpi_p1_e_is_zero` early-exit condition.

### `docs/policy_tiered_rounds.md`
- [ ] Verify round mechanics match `tiered_rounds_start` / `tiered_rounds_resume`.
- [ ] Document stall detection and the `stall_unassigned` field.
- [ ] Document manual tie-break UI flow (advisor picks one student per round).
- [ ] Add note on CLI usage requirement: `--auto-tiebreak` flag needed for
  non-interactive mode (once CLI TODO is implemented).
- [ ] Add cross-reference to `tiered_ll` as the hybrid variant with LL-HP backfill.

### `docs/policy_tiered_ll.md` ← **new file** (create once policy is implemented)
- [ ] Write from scratch after `tiered_ll` implementation is complete (see
  `TODO/tiered_ll_policy.md`).

---

## 2. Metrics Docs

### `NPSS_Metric.md`
- [ ] Confirm NPSS formula matches `metrics.py`: `score_i = (F − p_i + 1) / F`,
  full-list denominator F for all policies.
- [ ] Confirm overflow handling: rank > N_tier no longer clips score to 0; tracked
  as diagnostic only.
- [ ] Confirm PSI formula (equal-weighted, same denominator).
- [ ] Remove any references to old denominator (N_tier-based) or clipped overflow.

### `MSThesisAllocationProtocol.md`
- [ ] Audit against current tiering logic: percentile mode, quartile fallback,
  tiny-cohort special case.
- [ ] Update advisor metrics section: ERR = avg entropy / actual-load ceiling × 100,
  bounded [0,100%]; MSES; LUR; CPI skewness — confirm definitions match `metrics.py`.
- [ ] Remove or archive any description of allocation steps that no longer exist
  (e.g. old Round 2 mechanics if changed, old metric formulas).
- [ ] Add `adaptive_ll` and `tiered_ll` (pending) to the policy enumeration section.

---

## 3. User Manual (`docs/user_manual.md`)

- [ ] **Startup modes**: confirm `OUTPUT_MODE`, `STARTUP_MODE`, `ALLOCATION_POLICY`
  constants and their valid values are correctly documented.
- [ ] **Policy selector**: list all five current policies with one-line descriptions.
- [ ] **Phase 0 panel**: document empty-lab risk modal for `least_loaded`,
  `adaptive_ll` (both ✓ and ⚠ variants), and `s_lt_f` / structural-deficit cases.
- [ ] **Round 1**: document candidate list panel and confirm-picks flow.
- [ ] **Metrics panel**: document all displayed metrics (NPSS, PSI, MSES, LUR, ERR,
  CPI skewness) with brief definitions.
- [ ] **Export**: document CSV and HTML export; Phase 0 CSV save button.
- [ ] **Tiered Rounds**: document tie-break modal and manual pick flow.
- [ ] Remove any screenshots or UI descriptions that reference removed panels or
  old layout.
- [ ] Regenerate `docs/user_manual.pdf` from updated Markdown.

---

## 4. `stats/policy_report.md`

- [ ] Regenerate by running `stats/run_study.py` (or the new `analyze study`
  subcommand once available) after all policy CLI changes land.
- [ ] Expand to include `adaptive_ll` and `nonempty` alongside `least_loaded` and
  `cpi_fill` (current report only covers the latter two).
- [ ] Add `tiered_rounds` column once `--auto-tiebreak` CLI flag is available.

---

## 5. `CLAUDE.md`

- [ ] Update policy table: add `adaptive_ll` row with description; update `nonempty`
  and `tiered_rounds` rows if stale.
- [ ] Add `tiered_ll` row (marked as "forthcoming") once the TODO is underway.
- [ ] Update NPSS formula section to match current full-list denominator.
- [ ] Update **Commands** section to match CLI TODO (new `analyze` subcommand,
  updated `--policy` choices).
- [ ] Remove any references to old `STARTUP_MODE` values or removed constants.

---

## 6. `README.md` (if present) / repo root

- [ ] Check if a `README.md` exists at repo root; if not, assess whether one is needed.
- [ ] If present, ensure policy list, setup instructions, and metric descriptions
  are consistent with current code.
