# Allocation Policy Comparison Study

**Policies compared:** `least_loaded` vs `cpi_fill`
**Abbreviations:** LL = `least_loaded`, CF = `cpi_fill` (used in table annotations and inline comparisons throughout this report)
**Datasets:** 1 original + 4 synthetic (random, clustered, polarised, uniform_high_cpi)
**Metrics:** NPSS (primary, CPI-weighted), PSI (secondary, equal-weighted),
  advisor avg entropy, CPI skewness of advisor load
**Diagnostic columns (not independent deciding metrics):** Overflow Count, % Assigned in Window
  — out-of-window assignments already score 0 in NPSS, so these columns explain *why* NPSS
  is low in stressed scenarios but carry no additional evidential weight for policy comparison.

---

## 0. Dataset Descriptions

| Dataset | Students | Faculty | Description |
|---------|----------|---------|-------------|
| **Original** | 44 | 31 | Real anonymised preference data from the 2024 IISER-B MS thesis allocation form. Students submitted ranked lists of all 31 faculty; CPI values span 5.6–9.7. Used as the ground-truth baseline. |
| **Sample 1 (Random)** | 44 | 31 | Fully synthetic cohort. Each student's preference list is an independent uniform random shuffle of all faculty, and CPI values are drawn uniformly from [5.5, 10.0]. Models a cohort with no shared popularity bias and no CPI–preference correlation. Serves as a statistical null baseline. |
| **Sample 2 (Clustered)** | 44 | 31 | Simulates high advisor popularity concentration. 70% of students rank the same 8 "popular" faculty first (in random order), then fill the remaining 23 slots randomly; the other 30% have fully random lists. CPI is drawn uniformly from [5.5, 10.0]. Stress-tests how each policy handles bottlenecked demand on a small advisor subset. |
| **Sample 3 (Polarised)** | 44 | 31 | Simulates a CPI-stratified preference split. Students with CPI ≥ 7.75 rank the top-half faculty (F01–F15) before the bottom-half (F16–F31), while lower-CPI students do the opposite. CPI is drawn uniformly from [5.5, 10.0]. Tests whether CPI-ordered processing (`cpi_fill`) exploits the natural alignment between merit and preference group. |
| **Sample 4 (High-CPI)** | 44 | 31 | Homogeneous high-achiever cohort: all CPI values drawn from [8.0, 10.0] with fully random preferences. Simulates a competitive intake year where tier separation is narrow and almost every student falls in Class A or B. Highlights how each policy behaves when the CPI-weighting advantage of `cpi_fill` is spread uniformly across the cohort. |

---

## 1. Per-Dataset Metric Summary

### 1a. Student Satisfaction Metrics

| Dataset | Policy | NPSS ↑ | PSI ↑ | Overflow ↓ | % Assigned in Window ↑ |
|---------|--------|--------|-------|------------|------------------------|
| Original | least_loaded | 0.8942 | 0.9250 | 0 | 100.0% |
| Original | cpi_fill | 0.9044 | 0.9030 | 0 | 100.0% |
| Sample 1 (Random) | least_loaded | 0.8856 | 0.9636 | 0 | 100.0% |
| Sample 1 (Random) | cpi_fill | 0.9685 | 0.9727 | 0 | 100.0% |
| Sample 2 (Clustered) | least_loaded | 0.7850 | 0.8924 | 5 | 88.6% |
| Sample 2 (Clustered) | cpi_fill | 0.7575 | 0.8818 | 7 | 84.1% |
| Sample 3 (Polarised) | least_loaded | 0.9276 | 0.9841 | 0 | 100.0% |
| Sample 3 (Polarised) | cpi_fill | 0.9460 | 0.9720 | 0 | 100.0% |
| Sample 4 (High-CPI) | least_loaded | 0.9486 | 0.9902 | 0 | 100.0% |
| Sample 4 (High-CPI) | cpi_fill | 0.9569 | 0.9636 | 0 | 100.0% |

### 1b. Per-Tier Student Satisfaction Metrics

| Dataset | Policy | Tier | Count | Mean Rank ↓ | Within-Window % ↑ | Mean NPSS ↑ | Mean PSI ↑ |
|---------|--------|------|-------|------------|-------------------|-------------|------------|
| Original | least_loaded | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Original | least_loaded | B1 | 11 | 1.18 | 100.0% | 0.9636 | 0.9939 |
| Original | least_loaded | B2 | 11 | 1.91 | 100.0% | 0.8182 | 0.9697 |
| Original | least_loaded | C | 11 | 8.91 | 100.0% | 0.7449 | 0.7364 |
| Original | cpi_fill | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Original | cpi_fill | B1 | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Original | cpi_fill | B2 | 11 | 1.55 | 100.0% | 0.8909 | 0.9818 |
| Original | cpi_fill | C | 11 | 12.09 | 100.0% | 0.6422 | 0.6303 |
| Sample 1 (Random) | least_loaded | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 1 (Random) | least_loaded | B1 | 11 | 2.00 | 100.0% | 0.8000 | 0.9667 |
| Sample 1 (Random) | least_loaded | B2 | 11 | 1.91 | 100.0% | 0.8182 | 0.9697 |
| Sample 1 (Random) | least_loaded | C | 11 | 3.45 | 100.0% | 0.9208 | 0.9182 |
| Sample 1 (Random) | cpi_fill | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 1 (Random) | cpi_fill | B1 | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 1 (Random) | cpi_fill | B2 | 11 | 1.27 | 100.0% | 0.9455 | 0.9909 |
| Sample 1 (Random) | cpi_fill | C | 11 | 4.00 | 100.0% | 0.9032 | 0.9000 |
| Sample 2 (Clustered) | least_loaded | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 2 (Clustered) | least_loaded | B1 | 11 | 2.45 | 90.9% | 0.8000 | 0.9515 |
| Sample 2 (Clustered) | least_loaded | B2 | 11 | 5.36 | 63.6% | 0.5091 | 0.8545 |
| Sample 2 (Clustered) | least_loaded | C | 11 | 8.09 | 100.0% | 0.7713 | 0.7636 |
| Sample 2 (Clustered) | cpi_fill | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 2 (Clustered) | cpi_fill | B1 | 11 | 2.09 | 90.9% | 0.7818 | 0.9636 |
| Sample 2 (Clustered) | cpi_fill | B2 | 11 | 5.45 | 45.5% | 0.4545 | 0.8515 |
| Sample 2 (Clustered) | cpi_fill | C | 11 | 9.64 | 100.0% | 0.7214 | 0.7121 |
| Sample 3 (Polarised) | least_loaded | A | 11 | 1.18 | 100.0% | 0.9394 | 0.9939 |
| Sample 3 (Polarised) | least_loaded | B1 | 11 | 1.55 | 100.0% | 0.8909 | 0.9818 |
| Sample 3 (Polarised) | least_loaded | B2 | 11 | 1.45 | 100.0% | 0.9091 | 0.9848 |
| Sample 3 (Polarised) | least_loaded | C | 11 | 1.73 | 100.0% | 0.9765 | 0.9758 |
| Sample 3 (Polarised) | cpi_fill | A | 11 | 1.18 | 100.0% | 0.9394 | 0.9939 |
| Sample 3 (Polarised) | cpi_fill | B1 | 11 | 1.36 | 100.0% | 0.9273 | 0.9879 |
| Sample 3 (Polarised) | cpi_fill | B2 | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 3 (Polarised) | cpi_fill | C | 11 | 3.82 | 100.0% | 0.9091 | 0.9061 |
| Sample 4 (High-CPI) | least_loaded | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 4 (High-CPI) | least_loaded | B1 | 11 | 1.36 | 100.0% | 0.9273 | 0.9879 |
| Sample 4 (High-CPI) | least_loaded | B2 | 11 | 1.64 | 100.0% | 0.8727 | 0.9788 |
| Sample 4 (High-CPI) | least_loaded | C | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| Sample 4 (High-CPI) | cpi_fill | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Sample 4 (High-CPI) | cpi_fill | B1 | 11 | 1.09 | 100.0% | 0.9818 | 0.9970 |
| Sample 4 (High-CPI) | cpi_fill | B2 | 11 | 1.18 | 100.0% | 0.9636 | 0.9939 |
| Sample 4 (High-CPI) | cpi_fill | C | 11 | 5.09 | 100.0% | 0.8680 | 0.8636 |

## 2. Advisor Fairness Metrics

| Dataset | Policy | Advisors Assigned | Avg CPI Entropy ↑ | CPI Skewness |
|---------|--------|------------------|-------------------|--------------|
| Original | least_loaded | 31 | 0.1613 | 0.4597 |
| Original | cpi_fill | 31 | 0.1613 | 0.2033 |
| Sample 1 (Random) | least_loaded | 31 | 0.1935 | 0.1591 |
| Sample 1 (Random) | cpi_fill | 31 | 0.1774 | -0.1619 |
| Sample 2 (Clustered) | least_loaded | 31 | 0.1129 | -0.1195 |
| Sample 2 (Clustered) | cpi_fill | 31 | 0.1290 | 0.0192 |
| Sample 3 (Polarised) | least_loaded | 31 | 0.1452 | 0.1863 |
| Sample 3 (Polarised) | cpi_fill | 31 | 0.1129 | 0.1399 |
| Sample 4 (High-CPI) | least_loaded | 31 | 0.1935 | -0.3057 |
| Sample 4 (High-CPI) | cpi_fill | 31 | 0.1935 | -0.4342 |

## 3. Aggregate Statistics Across All Datasets

Values are **mean ± std** across the 5 datasets.

> **Note on interpretation:** With only 5 datasets and no formal significance testing, these
> aggregate comparisons are descriptive, not inferential. The std devs overlap heavily for
> every metric. A "winner" is called only when the mean difference clearly exceeds the
> per-metric significance threshold defined in Section 3a; otherwise the result is a **draw**.

### 3a. Significance Thresholds

Thresholds below are chosen based on the observed delta distribution and the practical
resolution of each metric. Differences smaller than these values are treated as within-noise
and declared a draw.

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| NPSS | \|Δ\| ≥ 0.04 | Aggregate std dev ~0.07; deltas < 0.03 cluster tightly around zero |
| PSI | \|Δ\| ≥ 0.025 | All observed deltas are < 0.03; only the extremes are distinguishable |
| Advisor Entropy | \|Δ\| ≥ 0.02 | Metric spans a narrow band (~0.11–0.19); smaller deltas are within rounding noise |
| CPI Skewness (\|abs\|) | \|Δ\| ≥ 0.10 | Higher variance metric; deltas below 0.10 are dataset-specific noise |
| Overflow Count | *(diagnostic only)* | Subsumed by NPSS: out-of-window students score 0 in NPSS, so this column explains *why* NPSS drops in stressed cohorts but adds no independent signal |
| % In Window | *(diagnostic only)* | Same reason as overflow; redundant with the NPSS penalty already applied |

### 3b. Aggregate Comparison

| Metric | `least_loaded` | `cpi_fill` | Raw winner | Threshold | Verdict |
|--------|---------------|------------|------------|-----------|---------|
| NPSS | 0.8882 ± 0.0630 | 0.9066 ± 0.0868 | `cpi_fill` (+0.018) | ≥ 0.04 | **Draw** — difference within noise; std devs overlap fully |
| PSI | 0.9511 ± 0.0415 | 0.9386 ± 0.0430 | `least_loaded` (+0.013) | ≥ 0.025 | **Draw** — all per-dataset deltas are marginal |
| Avg Advisor Entropy | 0.1613 ± 0.0342 | 0.1548 ± 0.0334 | `least_loaded` (+0.006) | ≥ 0.02 | **Draw** — difference is negligible across the metric's range |
| CPI Skewness (\|abs\|) | 0.2461 ± 0.1381 | 0.1917 ± 0.1519 | `cpi_fill` (−0.054) | ≥ 0.10 | **Draw** at aggregate level; per-dataset wins are clearer (see §4) |
| Advisors Assigned | 31.00 ± 0.00 | 31.00 ± 0.00 | Tied | — | **Draw** |
| Overflow Count | 1.00 ± 2.24 | 1.40 ± 3.13 | — | *(diagnostic)* | Not a deciding metric — out-of-window penalty already captured by NPSS=0 |
| % In Window | 97.73 ± 5.08 | 96.82 ± 7.11 | — | *(diagnostic)* | Not a deciding metric — same reason as overflow |

## 4. Per-Dataset Policy Deltas (cpi_fill − least_loaded)

Positive ΔNPSS / ΔPSI means `cpi_fill` is better; negative means `least_loaded` is better.
Entries marked **[draw]** did not meet the significance threshold. Entries marked **[win]** did.
Overflow and % In Window columns are shown for diagnostic context only (not used to declare wins).

| Dataset | ΔNPSS | ΔPSI | ΔOverflow *(diag)* | Δ% In Window *(diag)* | ΔAvg Entropy | ΔSkewness |
|---------|-------|------|-----------|--------------|--------------|-----------|
| Original | +0.0102 **[draw]** | −0.0220 **[draw]** | +0 | +0.0% | +0.0000 **[draw]** | −0.2564 **[cpi_fill win]** |
| Sample 1 (Random) | +0.0829 **[cpi_fill win]** | +0.0091 **[draw]** | +0 | +0.0% | −0.0161 **[draw]** | −0.3210 **[cpi_fill win]** |
| Sample 2 (Clustered) | −0.0275 **[draw]** | −0.0106 **[draw]** | +2 | −4.5% | +0.0161 **[draw]** | +0.1387 **[draw]** |
| Sample 3 (Polarised) | +0.0183 **[draw]** | −0.0121 **[draw]** | +0 | +0.0% | −0.0323 **[LL win]** | −0.0464 **[draw]** |
| Sample 4 (High-CPI) | +0.0083 **[draw]** | −0.0265 **[LL win]** | +0 | +0.0% | +0.0000 **[draw]** | −0.1285 **[cpi_fill win]** |

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
- NPSS: cpi_fill=0.9044 vs LL=0.8942 (Δ=+0.010) — **too small to distinguish; draw**
- PSI: LL=0.9250 vs cpi_fill=0.9030 (Δ=−0.022) — **too small to distinguish; draw**
- Advisor entropy: identical (0.1613 each)
- CPI skewness: cpi_fill reduces |skewness| by 0.256 — **cpi_fill wins; meaningful reduction**
- Overflow: 0 each; rank spread similar (mean 3.25 vs 3.91)
- *Note: Per-tier data shows cpi_fill gives B1 students a perfect NPSS=1.0 at the expense of Tier C (mean rank 12.09 vs 8.91). This intra-cohort redistribution is real but does not surface in the overall NPSS delta.*

### Sample 1 (Random)
- NPSS: cpi_fill=0.9685 vs LL=0.8856 (Δ=+0.083) — **cpi_fill wins; largest and most reliable delta in study**
- PSI: near-identical (0.9727 vs 0.9636, Δ=+0.009) — **draw**
- Advisor entropy: LL slightly higher (0.1935 vs 0.1774, Δ=−0.016) — **draw**
- CPI skewness: cpi_fill reduces |skewness| by 0.321 — **cpi_fill wins**
- *Note: With random preferences, cpi_fill's ordered processing avoids contention more effectively. This is the only dataset where NPSS shows a clear, threshold-crossing policy difference.*

### Sample 2 (Clustered)
- NPSS: LL=0.7850 vs cpi_fill=0.7575 (Δ=−0.028) — **just below threshold; draw, but the largest directional lean toward LL in the study**
- PSI: LL=0.8924 vs cpi_fill=0.8818 (Δ=−0.011) — **draw**
- Overflow *(diagnostic)*: LL=5, cpi_fill=7 (Δ=+2) — not a deciding metric, but explains the NPSS gap: cpi_fill's serial pass exhausts popular advisors early, forcing more mid-tier students out of their preference window (scored 0 in NPSS)
- % In Window *(diagnostic)*: LL=88.6% vs cpi_fill=84.1% (Δ=−4.5 pp) — same phenomenon; shown for context only
- All metrics: **draw** (NPSS delta directionally favours LL but does not cross the 0.04 threshold)
- *Note: Clustered demand stresses both policies severely. The overflow and window-miss diagnostics are useful for understanding *why* both policies produce low NPSS here, but since out-of-window assignments already score 0 in NPSS, these columns add no independent evidence beyond what NPSS already captures. Neither policy resolves the structural bottleneck.*

### Sample 3 (Polarised)
- NPSS: cpi_fill=0.9460 vs LL=0.9276 (Δ=+0.018) — **draw**
- PSI: LL=0.9841 vs cpi_fill=0.9720 (Δ=−0.012) — **draw**
- Advisor entropy: LL=0.1452 vs cpi_fill=0.1129 (Δ=−0.032) — **LL wins; meaningful difference**
- CPI skewness: small reduction with cpi_fill (0.186 vs 0.140, Δ=−0.046) — **draw**
- *Note: All rank distributions are compact (max rank 5 for LL, 26 for cpi_fill — a noteworthy tail for cpi_fill despite identical median). Entropy difference suggests cpi_fill concentrates advisors more narrowly.*

### Sample 4 (High-CPI)
- NPSS: cpi_fill=0.9569 vs LL=0.9486 (Δ=+0.008) — **draw**
- PSI: LL=0.9902 vs cpi_fill=0.9636 (Δ=−0.027) — **LL wins; largest PSI delta in study**
- Advisor entropy: identical (0.1935 each)
- CPI skewness: cpi_fill reduces |skewness| by 0.129 — **cpi_fill wins**
- *Note: When the cohort is uniformly high-CPI, cpi_fill's merit-ordering provides no real differentiation — everyone is equally "meritorious". Yet its serial processing still produces a longer rank tail (max rank 31 vs 4), hurting PSI for the unlucky students at the back of the queue.*

---

## 7. Policy Recommendation

### 7a. Revised Win Count (applying significance thresholds from §3a)

The original win-count table counted every numerical difference as a win, regardless of
magnitude or metric redundancy. The table below applies two corrections:
(1) only threshold-crossing differences count as wins; and
(2) Overflow Count and % In Window are excluded as deciding metrics because out-of-window
assignments already score 0 in NPSS — they are diagnostic columns, not independent criteria.

| Metric | `least_loaded` wins | `cpi_fill` wins | Draws |
|--------|--------------------|--------------------|-------|
| NPSS (primary, ≥ 0.04) | 0 | 1 (Random) | 4 |
| PSI (secondary, ≥ 0.025) | 1 (High-CPI) | 0 | 4 |
| Advisor Entropy (≥ 0.02) | 1 (Polarised) | 0 | 4 |
| CPI Skewness (≥ 0.10) | 0 | 3 (Orig / Rand / High-CPI) | 2 |
| Overflow Count | *(diagnostic — subsumed by NPSS)* | | |
| % In Window | *(diagnostic — subsumed by NPSS)* | | |

**The central finding: the two policies are broadly equivalent across most scenarios.**
Across the four independent deciding metrics, there are only 5 threshold-crossing results
total — out of a possible 20 (4 metrics × 5 datasets). Meaningful differences appear only
in specific structural conditions, not as a general tendency.

### 7b. What the Data Actually Supports

**`cpi_fill` has a genuine advantage in two situations:**

1. **Random/uncorrelated preferences (NPSS, Δ=+0.083):** This is the only threshold-crossing
   NPSS win in the study and also the largest single delta observed. When preferences carry no
   structural signal, cpi_fill's ordered pass avoids accidental contention, improving merit-weighted
   satisfaction for mid-tier students.

2. **CPI skewness reduction (3 of 5 datasets):** cpi_fill consistently distributes CPI more
   evenly across advisors. This is the most robust signal in the study — it persists across
   random, original, and high-CPI cohorts with deltas well above threshold (0.256–0.321).
   If advisor CPI diversity is an institutional goal, this is the strongest argument for cpi_fill.

**`least_loaded` shows a directional advantage in one situation, but no threshold-crossing win:**

3. **Clustered demand (NPSS Δ=−0.028, just below the 0.04 threshold):** cpi_fill's serial
   pass exhausts popular capacity early, pushing more students outside their preference window;
   these out-of-window assignments score 0 in NPSS, dragging its score down. The Overflow and
   % In Window columns (LL=5/88.6% vs CF=7/84.1%) make this mechanism visible, but they are
   diagnostic — the penalty is already fully encoded in the NPSS gap. The gap is real and
   directionally consistent with LL being more robust under clustered demand, but it does not
   clear the significance threshold on any independent metric.

**Neither policy dominates on PSI, advisor entropy, or NPSS in structured cohorts.**
Most deltas for these metrics are below the noise threshold, and the aggregate std devs
overlap too heavily to support a claim of superiority.

**A caution on per-tier interpretation:** The tier-level data (§1b) shows that cpi_fill
redistributes satisfaction *within* a cohort — Tier A and B1 students gain, Tier C students
lose — without necessarily improving the overall NPSS. This intra-cohort trade-off is a
policy value judgement, not a metric win.

### 7c. When to Use Each Policy

| Situation | Recommended Policy | Reason |
|-----------|-------------------|--------|
| Preferences are largely uncorrelated | `cpi_fill` | Only scenario with a threshold-crossing NPSS advantage (Δ=+0.083) |
| Advisor CPI diversity matters institutionally | `cpi_fill` | Most robust signal in study: skewness reduction in 3 of 5 datasets above threshold |
| Many students competing for few advisors | `least_loaded` | Directional NPSS lean (Δ=−0.028); LL's load-spreading is less likely to exhaust popular capacity early — no independent metric win, but the mechanism is structurally sound |
| Cohort is uniformly high-CPI | `least_loaded` | cpi_fill's merit-ordering adds no differentiation; PSI penalty is real (only threshold-crossing PSI result in study) |
| Institution prioritises merit-based access | `cpi_fill` | Structural design intent; Tier A/B1 gains are real even when overall metrics do not separate |
| Default / unknown cohort structure | `least_loaded` | No scenario where it clearly fails on a deciding metric |

### 7d. Summary

> **The honest conclusion is that neither policy is uniformly superior.** Across 5 datasets and
> 4 independent deciding metrics (NPSS, PSI, Advisor Entropy, CPI Skewness), only 5 of a
> possible 20 pairwise comparisons cross the significance threshold. Overflow Count and
> % In Window, while useful diagnostics, are not independent criteria — both are already
> absorbed into NPSS through the zero-weight penalty for out-of-window assignments. The two
> policies converge on nearly identical outcomes in typical cohorts.
>
> The choice between them should be driven by **institutional values**, not by these metrics alone:
>
> - Choose `cpi_fill` if the institution explicitly rewards academic merit in advisor matching,
>   or if advisor CPI balance is a priority.
> - Choose `least_loaded` if equitable treatment across CPI tiers, robustness to clustered
>   demand, or predictability of outcomes is the priority.
>
> A more definitive empirical comparison would require either a larger sample of real datasets
> (≥ 20–30 cohorts) or bootstrap resampling of the existing datasets to construct confidence
> intervals for each metric delta.

---

*Report generated by `stats/run_study.py` using the IISER-B MS Thesis Allocator engine.*
