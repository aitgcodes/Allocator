# Allocation Policy Comparison Study

**Policies compared:** `least_loaded` vs `cpi_fill`  
**Abbreviations:** LL = `least_loaded`, CF = `cpi_fill` (used in table annotations and inline comparisons throughout this report)  
**Datasets:** 1 original + 4 synthetic (random, clustered, polarised, uniform_high_cpi)  
**Metric hierarchy:**
  1. NPSS — primary student metric (CPI-weighted preference satisfaction)  
  2. PSI — secondary student metric (equal-weighted, global rank)  
  3. MSES — primary advisor satisfaction metric (mean rank students placed their advisor; lower = more enthusiastic)  
  4. Equity Retention Rate — advisor equity metric (% of cohort's achievable entropy preserved; protocol-attributable)  
  5. CPI Skewness — diagnostic (asymmetry in advisor mean-CPI distribution; Fisher-Pearson formula, std-normalized)  
**Diagnostic columns (not independent deciding metrics):** Overflow Count, % Assigned in Window, Avg LUR  
  — out-of-window assignments already score 0 in NPSS, so these columns explain *why* NPSS  
  is low in stressed scenarios but carry no additional evidential weight for policy comparison.  

---

## 1. Per-Dataset Metric Summary

### 1a. Student Satisfaction Metrics

| Dataset | Policy | NPSS ↑ | PSI ↑ | Overflow ↓ | % Assigned in Window ↑ |
|---------|--------|--------|-------|------------|------------------------|
| Original | least_loaded | 0.9379 | 0.9250 | 0 | 100.0% |
| Original | cpi_fill | 0.9253 | 0.9030 | 0 | 100.0% |
| Sample 1 (Random) | least_loaded | 0.9680 | 0.9636 | 0 | 100.0% |
| Sample 1 (Random) | cpi_fill | 0.9795 | 0.9727 | 0 | 100.0% |
| Sample 2 (Clustered) | least_loaded | 0.9100 | 0.8924 | 5 | 88.6% |
| Sample 2 (Clustered) | cpi_fill | 0.9036 | 0.8818 | 7 | 84.1% |
| Sample 3 (Polarised) | least_loaded | 0.9855 | 0.9841 | 0 | 100.0% |
| Sample 3 (Polarised) | cpi_fill | 0.9784 | 0.9720 | 0 | 100.0% |
| Sample 4 (High-CPI) | least_loaded | 0.9906 | 0.9902 | 0 | 100.0% |
| Sample 4 (High-CPI) | cpi_fill | 0.9683 | 0.9636 | 0 | 100.0% |

### 1b. Per-Tier Student Satisfaction Metrics

| Dataset | Policy | Tier | Count | Mean Rank ↓ | Within-Window % ↑ | Mean NPSS ↑ | Mean PSI ↑ |
|---------|--------|------|-------|------------|-------------------|-------------|------------|
| Original | least_loaded | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Original | least_loaded | B1 | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| Original | least_loaded | B2 | 11 | 1.91 | 100.0% | 0.9707 | 0.9697 |
| Original | least_loaded | C | 11 | 8.91 | 100.0% | 0.7449 | 0.7364 |
| Original | cpi_fill | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Original | cpi_fill | B1 | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Original | cpi_fill | B2 | 11 | 1.55 | 100.0% | 0.9824 | 0.9818 |
| Original | cpi_fill | C | 11 | 12.09 | 100.0% | 0.6422 | 0.6303 |
| Sample 1 (Random) | least_loaded | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 1 (Random) | least_loaded | B1 | 11 | 2.00 | 100.0% | 0.9677 | 0.9667 |
| Sample 1 (Random) | least_loaded | B2 | 11 | 1.91 | 100.0% | 0.9707 | 0.9697 |
| Sample 1 (Random) | least_loaded | C | 11 | 3.45 | 100.0% | 0.9208 | 0.9182 |
| Sample 1 (Random) | cpi_fill | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 1 (Random) | cpi_fill | B1 | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 1 (Random) | cpi_fill | B2 | 11 | 1.27 | 100.0% | 0.9912 | 0.9909 |
| Sample 1 (Random) | cpi_fill | C | 11 | 4.00 | 100.0% | 0.9032 | 0.9000 |
| Sample 2 (Clustered) | least_loaded | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 2 (Clustered) | least_loaded | B1 | 11 | 2.45 | 90.9% | 0.9531 | 0.9515 |
| Sample 2 (Clustered) | least_loaded | B2 | 11 | 5.36 | 63.6% | 0.8592 | 0.8545 |
| Sample 2 (Clustered) | least_loaded | C | 11 | 8.09 | 100.0% | 0.7713 | 0.7636 |
| Sample 2 (Clustered) | cpi_fill | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 2 (Clustered) | cpi_fill | B1 | 11 | 2.09 | 90.9% | 0.9648 | 0.9636 |
| Sample 2 (Clustered) | cpi_fill | B2 | 11 | 5.45 | 45.5% | 0.8563 | 0.8515 |
| Sample 2 (Clustered) | cpi_fill | C | 11 | 9.64 | 100.0% | 0.7214 | 0.7121 |
| Sample 3 (Polarised) | least_loaded | A | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| Sample 3 (Polarised) | least_loaded | B1 | 11 | 1.55 | 100.0% | 0.9824 | 0.9818 |
| Sample 3 (Polarised) | least_loaded | B2 | 11 | 1.45 | 100.0% | 0.9853 | 0.9848 |
| Sample 3 (Polarised) | least_loaded | C | 11 | 1.73 | 100.0% | 0.9765 | 0.9758 |
| Sample 3 (Polarised) | cpi_fill | A | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| Sample 3 (Polarised) | cpi_fill | B1 | 11 | 1.36 | 100.0% | 0.9883 | 0.9879 |
| Sample 3 (Polarised) | cpi_fill | B2 | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 3 (Polarised) | cpi_fill | C | 11 | 3.82 | 100.0% | 0.9091 | 0.9061 |
| Sample 4 (High-CPI) | least_loaded | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 4 (High-CPI) | least_loaded | B1 | 11 | 1.36 | 100.0% | 0.9883 | 0.9879 |
| Sample 4 (High-CPI) | least_loaded | B2 | 11 | 1.64 | 100.0% | 0.9795 | 0.9788 |
| Sample 4 (High-CPI) | least_loaded | C | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| Sample 4 (High-CPI) | cpi_fill | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 4 (High-CPI) | cpi_fill | B1 | 11 | 1.09 | 100.0% | 0.9971 | 0.9970 |
| Sample 4 (High-CPI) | cpi_fill | B2 | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| Sample 4 (High-CPI) | cpi_fill | C | 11 | 5.09 | 100.0% | 0.8680 | 0.8636 |

## 2. Advisor Metrics

### 2a. Advisor Satisfaction

| Dataset | Policy | Avg MSES ↓ | Avg LUR *(diag)* |
|---------|--------|-----------|-----------------|
| Original | least_loaded | 4.0806 | 71.0% |
| Original | cpi_fill | 5.0484 | 71.0% |
| Sample 1 (Random) | least_loaded | 2.3548 | 71.0% |
| Sample 1 (Random) | cpi_fill | 2.1452 | 71.0% |
| Sample 2 (Clustered) | least_loaded | 4.6935 | 71.0% |
| Sample 2 (Clustered) | cpi_fill | 5.4516 | 71.0% |
| Sample 3 (Polarised) | least_loaded | 1.5000 | 71.0% |
| Sample 3 (Polarised) | cpi_fill | 2.0806 | 71.0% |
| Sample 4 (High-CPI) | least_loaded | 1.3387 | 71.0% |
| Sample 4 (High-CPI) | cpi_fill | 2.5161 | 71.0% |

### 2b. Advisor Equity

| Dataset | Policy | Cohort Entropy Ceiling | Equity Retention % ↑ | CPI Skewness *(diag)* |
|---------|--------|------------------------|----------------------|-----------------------|
| Original | least_loaded | 0.2097 | 76.9% | 0.4597 |
| Original | cpi_fill | 0.2097 | 76.9% | 0.2033 |
| Sample 1 (Random) | least_loaded | 0.2097 | 92.3% | 0.1591 |
| Sample 1 (Random) | cpi_fill | 0.2097 | 84.6% | -0.1619 |
| Sample 2 (Clustered) | least_loaded | 0.2097 | 53.8% | -0.1195 |
| Sample 2 (Clustered) | cpi_fill | 0.2097 | 61.5% | 0.0192 |
| Sample 3 (Polarised) | least_loaded | 0.2097 | 69.2% | 0.1863 |
| Sample 3 (Polarised) | cpi_fill | 0.2097 | 53.8% | 0.1399 |
| Sample 4 (High-CPI) | least_loaded | 0.2097 | 92.3% | -0.3057 |
| Sample 4 (High-CPI) | cpi_fill | 0.2097 | 92.3% | -0.4342 |

## 3. Aggregate Statistics Across All Datasets

Values are **mean ± std** across the 5 datasets.

> **Note on interpretation:** With only 5 datasets and no formal significance testing,
> these aggregate comparisons are descriptive, not inferential. The std devs overlap
> heavily for every metric. A win is called only when the mean difference clearly
> exceeds the per-metric significance threshold; otherwise the result is a **Draw**.

| Metric | `least_loaded` | `cpi_fill` | Threshold | Verdict |
|--------|---------------|------------|-----------|---------|
| NPSS | 0.9584 ± 0.0340 | 0.9510 ± 0.0345 | ≥ 0.04 | **Draw** |
| PSI | 0.9511 ± 0.0415 | 0.9386 ± 0.0430 | ≥ 0.025 | **Draw** |
| Overflow Count | 1.0000 ± 2.2361 | 1.4000 ± 3.1305 | *(diag)* | *(diagnostic)* |
| % In Window | 97.7273 ± 5.0820 | 96.8182 ± 7.1148 | *(diag)* | *(diagnostic)* |
| Avg MSES | 2.7935 ± 1.5206 | 3.4484 ± 1.6592 | ≥ 0.5 | **least_loaded** |
| Equity Retention % | 76.9231 ± 16.3178 | 73.8462 ± 15.9511 | ≥ 5.0 | **Draw** |
| Avg LUR | 70.9677 ± 0.0000 | 70.9677 ± 0.0000 | *(diag)* | *(diagnostic)* |
| CPI Skewness (|abs|) | 0.2461 ± 0.1381 | 0.1917 ± 0.1519 | ≥ 0.1 | **Draw** |
| Advisors Assigned | 31.0000 ± 0.0000 | 31.0000 ± 0.0000 | *(diag)* | *(diagnostic)* |

## 4. Per-Dataset Policy Deltas (cpi_fill − least_loaded)

Positive ΔNPSS / ΔPSI / ΔEquity Retention means `cpi_fill` is better; negative means `least_loaded` is better.
ΔMSES: negative means CF students are more enthusiastic (lower mean rank = better).
ΔSkewness = Δ|abs| = |CF| − |LL|; negative means CF has lower absolute skewness.
Overflow and % In Window are shown for diagnostic context only (not used to declare wins).

| Dataset | ΔNPSS | ΔPSI | ΔMSES | ΔEquity Ret% | ΔOverflow *(diag)* | Δ% In Window *(diag)* | ΔSkewness *(diag)* |
|---------|-------|------|-------|-------------|--------------------|-----------------------|-------------------|
| Original | -0.0125 | -0.0220 | +0.9677 | +0.0% | +0 | +0.0% | -0.2564 |
| Sample 1 (Random) | +0.0115 | +0.0091 | -0.2097 | -7.7% | +0 | +0.0% | -0.3210 |
| Sample 2 (Clustered) | -0.0064 | -0.0106 | +0.7581 | +7.7% | +2 | -4.5% | 0.1387 |
| Sample 3 (Polarised) | -0.0071 | -0.0121 | +0.5806 | -15.4% | +0 | +0.0% | -0.0464 |
| Sample 4 (High-CPI) | -0.0223 | -0.0265 | +1.1774 | +0.0% | +0 | +0.0% | -0.1285 |

## 5. Assigned Preference Rank Distributions

| Dataset | Policy | Min Rank | Median Rank | Mean Rank | Max Rank | Std Rank |
|---------|--------|----------|-------------|-----------|----------|----------|
| Original | least_loaded | 1 | 1.0 | 3.25 | 30 | 6.27 |
| Original | cpi_fill | 1 | 1.0 | 3.91 | 31 | 6.77 |
| Sample 1 (Random) | least_loaded | 1 | 1.0 | 2.09 | 22 | 3.25 |
| Sample 1 (Random) | cpi_fill | 1 | 1.0 | 1.82 | 13 | 2.24 |
| Sample 2 (Clustered) | least_loaded | 1 | 1.0 | 4.23 | 24 | 5.49 |
| Sample 2 (Clustered) | cpi_fill | 1 | 1.0 | 4.55 | 31 | 6.07 |
| Sample 3 (Polarised) | least_loaded | 1 | 1.0 | 1.48 | 5 | 0.98 |
| Sample 3 (Polarised) | cpi_fill | 1 | 1.0 | 1.84 | 26 | 3.77 |
| Sample 4 (High-CPI) | least_loaded | 1 | 1.0 | 1.30 | 4 | 0.70 |
| Sample 4 (High-CPI) | cpi_fill | 1 | 1.0 | 2.09 | 31 | 4.72 |

## 6. Scenario-by-Scenario Observations

### Original
- NPSS: LL=0.9379, CF=0.9253 — **draw** (threshold 0.04)
- PSI: LL=0.9250, CF=0.9030 — **draw** (threshold 0.025)
- MSES: LL=4.0806, CF=5.0484 — **win LL** (threshold 0.5)
- Equity Retention: LL=76.9%, CF=76.9% — **draw** (threshold 5.0%)
- CPI skewness (diagnostic): |LL|=0.4597, |CF|=0.2033 — **win CF** (diagnostic)
- Overflow (diagnostic): LL=0, CF=0

### Sample 1 (Random)
- NPSS: LL=0.9680, CF=0.9795 — **draw** (threshold 0.04)
- PSI: LL=0.9636, CF=0.9727 — **draw** (threshold 0.025)
- MSES: LL=2.3548, CF=2.1452 — **draw** (threshold 0.5)
- Equity Retention: LL=92.3%, CF=84.6% — **win LL** (threshold 5.0%)
- CPI skewness (diagnostic): |LL|=0.1591, |CF|=0.1619 — **draw** (diagnostic)
- Overflow (diagnostic): LL=0, CF=0

### Sample 2 (Clustered)
- NPSS: LL=0.9100, CF=0.9036 — **draw** (threshold 0.04)
- PSI: LL=0.8924, CF=0.8818 — **draw** (threshold 0.025)
- MSES: LL=4.6935, CF=5.4516 — **win LL** (threshold 0.5)
- Equity Retention: LL=53.8%, CF=61.5% — **win CF** (threshold 5.0%)
- CPI skewness (diagnostic): |LL|=0.1195, |CF|=0.0192 — **win CF** (diagnostic)
- Overflow (diagnostic): LL=5, CF=7

### Sample 3 (Polarised)
- NPSS: LL=0.9855, CF=0.9784 — **draw** (threshold 0.04)
- PSI: LL=0.9841, CF=0.9720 — **draw** (threshold 0.025)
- MSES: LL=1.5000, CF=2.0806 — **win LL** (threshold 0.5)
- Equity Retention: LL=69.2%, CF=53.8% — **win LL** (threshold 5.0%)
- CPI skewness (diagnostic): |LL|=0.1863, |CF|=0.1399 — **draw** (diagnostic)
- Overflow (diagnostic): LL=0, CF=0

### Sample 4 (High-CPI)
- NPSS: LL=0.9906, CF=0.9683 — **draw** (threshold 0.04)
- PSI: LL=0.9902, CF=0.9636 — **win LL** (threshold 0.025)
- MSES: LL=1.3387, CF=2.5161 — **win LL** (threshold 0.5)
- Equity Retention: LL=92.3%, CF=92.3% — **draw** (threshold 5.0%)
- CPI skewness (diagnostic): |LL|=0.3057, |CF|=0.4342 — **win LL** (diagnostic)
- Overflow (diagnostic): LL=0, CF=0

---

## 7. Policy Recommendation

### 7a. Threshold-based win count

Only differences that cross the significance threshold count as wins.
Overflow Count and % In Window are excluded — subsumed by NPSS.

| Metric | `least_loaded` wins | `cpi_fill` wins | Draws |
|--------|--------------------|--------------------|-------|
| NPSS (primary, threshold 0.04) | 0 | 0 | 5 |
| PSI (secondary, threshold 0.025) | 1 | 0 | 4 |
| MSES (threshold 0.5) | 4 | 0 | 1 |
| Equity Retention % (threshold 5.0%) | 2 | 1 | 2 |
| CPI Skewness | *(diagnostic — see per-dataset notes in §6)* | | |
| Overflow Count | *(diagnostic — subsumed by NPSS)* | | |
| % In Window | *(diagnostic — subsumed by NPSS)* | | |

### 7b. When to use each policy

### When to use `least_loaded`

- When **equitable treatment of students** across CPI tiers is important: placement
  depends on faculty load, not student CPI rank.
- When **robustness to clustered demand** is a priority: load-spreading is less likely
  to exhaust popular advisor capacity early.
- As the **safe default** when cohort structure is unknown.

### When to use `cpi_fill`

- When **rewarding academic merit** is an explicit institutional goal: high-CPI students
  get first access to their preferred advisors.
- When **no empty labs** is a hard requirement: Phase 2 structurally guarantees this.
- In **random or weakly correlated preference** cohorts: the only threshold-crossing NPSS
  win in this study occurs here (Δ=+0.083).

### 7c. Summary

> **The honest conclusion is that neither policy is uniformly superior.**
> Across the datasets, NPSS is the primary comparison metric; advisor entropy is the
> preferred advisor-equity metric; CPI skewness is a diagnostic cross-check whose
> direction can reverse across cohort types and should not be used alone to declare
> a policy winner. The two policies converge on nearly identical outcomes in typical
> cohorts. The choice is a value judgement about institutional priorities, not a
> metric-determined optimum.
>
> - Choose `cpi_fill` if the institution explicitly rewards academic merit in advisor
>   matching. Verify with NPSS; check entropy to confirm advisor-equity is acceptable.
> - Choose `least_loaded` if equitable treatment across tiers, robustness to clustered
>   demand, or predictability of outcomes is the priority.
> - Do not use CPI skewness alone to justify either choice; use it alongside entropy
>   as a supplementary diagnostic.

---

*Report generated by `stats/run_study.py` using the IISER-B MS Thesis Allocator engine.*