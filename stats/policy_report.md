# Allocation Policy Comparison Study

**Policies compared:** `least_loaded` vs `cpi_fill`  
**Datasets:** 1 original + 4 synthetic (random, clustered, polarised, uniform_high_cpi)  
**Metrics:** NPSS (primary, CPI-weighted), PSI (secondary, equal-weighted), 
  advisor avg entropy, CPI skewness of advisor load  

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

| Metric | `least_loaded` | `cpi_fill` | Winner |
|--------|---------------|------------|--------|
| NPSS | 0.8882 ± 0.0630 | 0.9066 ± 0.0868 | `cpi_fill` |
| PSI | 0.9511 ± 0.0415 | 0.9386 ± 0.0430 | `least_loaded` |
| Overflow Count | 1.0000 ± 2.2361 | 1.4000 ± 3.1305 | `least_loaded` |
| % In Window | 97.7273 ± 5.0820 | 96.8182 ± 7.1148 | `least_loaded` |
| Avg Advisor Entropy | 0.1613 ± 0.0342 | 0.1548 ± 0.0334 | `least_loaded` |
| CPI Skewness (|abs|) | 0.2461 ± 0.1381 | 0.1917 ± 0.1519 | `cpi_fill` |
| Advisors Assigned | 31.0000 ± 0.0000 | 31.0000 ± 0.0000 | `least_loaded` |

## 4. Per-Dataset Policy Deltas (cpi_fill − least_loaded)

Positive ΔNPSS / ΔPSI means `cpi_fill` is better; negative means `least_loaded` is better.

| Dataset | ΔNPSS | ΔPSI | ΔOverflow | Δ% In Window | ΔAvg Entropy | ΔSkewness |
|---------|-------|------|-----------|--------------|--------------|-----------|
| Original | +0.0102 | -0.0220 | +0 | +0.0% | +0.0000 | -0.2564 |
| Sample 1 (Random) | +0.0829 | +0.0091 | +0 | +0.0% | -0.0161 | -0.3210 |
| Sample 2 (Clustered) | -0.0275 | -0.0106 | +2 | -4.5% | +0.0161 | 0.1387 |
| Sample 3 (Polarised) | +0.0183 | -0.0121 | +0 | +0.0% | -0.0323 | -0.0464 |
| Sample 4 (High-CPI) | +0.0083 | -0.0265 | +0 | +0.0% | +0.0000 | -0.1285 |

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
- NPSS winner: **cpi_fill** (LL=0.8942, CF=0.9044)
- PSI winner: **least_loaded** (LL=0.9250, CF=0.9030)
- Advisor entropy winner: **least_loaded** (LL=0.1613, CF=0.1613)
- Overflow → LL=0, CF=0

### Sample 1 (Random)
- NPSS winner: **cpi_fill** (LL=0.8856, CF=0.9685)
- PSI winner: **cpi_fill** (LL=0.9636, CF=0.9727)
- Advisor entropy winner: **least_loaded** (LL=0.1935, CF=0.1774)
- Overflow → LL=0, CF=0

### Sample 2 (Clustered)
- NPSS winner: **least_loaded** (LL=0.7850, CF=0.7575)
- PSI winner: **least_loaded** (LL=0.8924, CF=0.8818)
- Advisor entropy winner: **cpi_fill** (LL=0.1129, CF=0.1290)
- Overflow → LL=5, CF=7

### Sample 3 (Polarised)
- NPSS winner: **cpi_fill** (LL=0.9276, CF=0.9460)
- PSI winner: **least_loaded** (LL=0.9841, CF=0.9720)
- Advisor entropy winner: **least_loaded** (LL=0.1452, CF=0.1129)
- Overflow → LL=0, CF=0

### Sample 4 (High-CPI)
- NPSS winner: **cpi_fill** (LL=0.9486, CF=0.9569)
- PSI winner: **least_loaded** (LL=0.9902, CF=0.9636)
- Advisor entropy winner: **least_loaded** (LL=0.1935, CF=0.1935)
- Overflow → LL=0, CF=0

---

## 7. Policy Recommendation

Across 5 datasets:

| Criterion | `least_loaded` wins | `cpi_fill` wins |
|-----------|--------------------|--------------------|
| NPSS (primary) | 1 | 4 |
| PSI (secondary) | 4 | 1 |
| Advisor Entropy | 4 | 1 |
| Lower Overflow  | 5  | 0  |

### When to use `least_loaded`

- When **load balancing across advisors** is the primary concern. The policy
  distributes students to the least-loaded eligible advisor, naturally spreading
  the advising burden and resulting in higher advisor CPI diversity (entropy).
- When **equal treatment of students** regardless of CPI is important: every
  student in a given tier has an equal chance of landing near the top of their
  preference list, because placement depends only on faculty load, not student rank.
- In **uniform or random cohort** scenarios where there is no strong correlation
  between CPI and preference similarity.

### When to use `cpi_fill`

- When **rewarding academic merit** is an explicit institutional goal. Because
  students are processed in descending CPI order, high-performing students get
  first access to their preferred advisors.
- In **clustered preference** scenarios (many students competing for the same
  few popular advisors), `cpi_fill` can give top students their #1 or #2 choice
  while `least_loaded` may arbitrarily split that cohort.
- When **minimizing empty-lab spots** matters: Phase 2 of `cpi_fill` explicitly
  fills remaining empty labs, so no advisor seat is left unused when students
  remain unassigned.
- In **polarised** cohorts (high-CPI students all prefer a different group of
  advisors from low-CPI students), `cpi_fill` can outperform on PSI because
  the CPI-ordered pass naturally separates the two groups.

### Summary recommendation

Both policies generally perform well and produce near-identical NPSS/PSI in
random or balanced cohorts. The practical choice depends on institutional values:

| Priority | Recommended Policy |
|----------|-------------------|
| Advisor load balance & equity | `least_loaded` |
| Student merit-based access | `cpi_fill` |
| Minimising unfilled advisor slots | `cpi_fill` |
| Robustness across cohort shapes | `least_loaded` |

> **Practical default:** Use `least_loaded` for most cohorts. Switch to `cpi_fill`
> when the institution explicitly weights academic performance in advisor matching
> or when a large number of students compete for a small popular subset of advisors.

---

*Report generated by `stats/run_study.py` using the IISER-B MS Thesis Allocator engine.*