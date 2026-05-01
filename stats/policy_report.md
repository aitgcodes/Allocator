# Allocation Policy Comparison Study — 5-Policy Matrix

**Policies:** LL = `least_loaded`, ALL = `adaptive_ll`, CF = `cpi_fill`, TR = `tiered_rounds`, TLL = `tiered_ll`  
**Datasets:** 2019 cohort, 2020 cohort + 4 synthetic (random, clustered, polarised, uniform_high_cpi)  
**Tie-breaking:** `tiered_rounds` and `tiered_ll` use automatic CPI tie-breaking (CLI mode)  
**Seed:** `RANDOM_SEED=42` for reproducibility  

**Metric hierarchy:**
  1. NPSS — primary student metric (CPI-weighted preference satisfaction)  
  2. PSI — secondary student metric (equal-weighted)  
  3. MSES — advisor satisfaction (mean rank students placed their advisor; lower = better)  
  4. Equity Retention Rate — % of achievable load-entropy preserved; [0, 100%]  
  5. CPI Skewness — diagnostic (asymmetry in advisor mean-CPI distribution)  

---

## 1. Student Satisfaction — Per Dataset

### 1a. NPSS and PSI (higher is better)

| Dataset | Policy | NPSS ↑ | PSI ↑ | Overflow ↓ | Assigned | Empty Labs ↓ |
|---------|--------|--------|-------|------------|----------|--------------|
| 2019 Cohort | LL | 0.9616 | 0.9554 | 0 | 28/28 | 2 |
| 2019 Cohort | ALL | 0.9240 | 0.9107 | 0 | 28/28 | 0 |
| 2019 Cohort | CF | 0.9132 | 0.8958 | 2 | 28/28 | 0 |
| 2019 Cohort | TR | 0.9817 | 0.9792 | 0 | 28/28 | 4 |
| 2019 Cohort | TLL | 0.9146 | 0.8988 | 2 | 28/28 | 0 |
|  |  |  |  |  |  |  |
| 2020 Cohort | LL | 0.9379 | 0.9250 | 0 | 44/44 | 0 |
| 2020 Cohort | ALL | 0.9379 | 0.9250 | 0 | 44/44 | 0 |
| 2020 Cohort | CF | 0.9253 | 0.9030 | 0 | 44/44 | 0 |
| 2020 Cohort | TR | 0.9739 | 0.9712 | 1 | 44/44 | 6 |
| 2020 Cohort | TLL | 0.9118 | 0.8909 | 0 | 44/44 | 0 |
|  |  |  |  |  |  |  |
| Synthetic 1 (Random) | LL | 0.9132 | 0.8869 | 0 | 24/24 | 0 |
| Synthetic 1 (Random) | ALL | 0.9132 | 0.8869 | 0 | 24/24 | 0 |
| Synthetic 1 (Random) | CF | 0.9911 | 0.9881 | 0 | 24/24 | 0 |
| Synthetic 1 (Random) | TR | 0.8453 | 0.8095 | 0 | 24/24 | 0 |
| Synthetic 1 (Random) | TLL | 0.8453 | 0.8095 | 0 | 24/24 | 0 |
|  |  |  |  |  |  |  |
| Synthetic 2 (Clustered) | LL | 0.9309 | 0.8988 | 0 | 24/24 | 0 |
| Synthetic 2 (Clustered) | ALL | 0.9309 | 0.8988 | 0 | 24/24 | 0 |
| Synthetic 2 (Clustered) | CF | 0.9960 | 0.9940 | 0 | 24/24 | 0 |
| Synthetic 2 (Clustered) | TR | 0.8748 | 0.8393 | 0 | 24/24 | 0 |
| Synthetic 2 (Clustered) | TLL | 0.8831 | 0.8512 | 0 | 24/24 | 0 |
|  |  |  |  |  |  |  |
| Synthetic 3 (Polarised) | LL | 0.8513 | 0.8095 | 0 | 24/24 | 0 |
| Synthetic 3 (Polarised) | ALL | 0.8513 | 0.8095 | 0 | 24/24 | 0 |
| Synthetic 3 (Polarised) | CF | 0.9756 | 0.9643 | 0 | 24/24 | 0 |
| Synthetic 3 (Polarised) | TR | 0.8697 | 0.8393 | 0 | 24/24 | 0 |
| Synthetic 3 (Polarised) | TLL | 0.8743 | 0.8452 | 0 | 24/24 | 0 |
|  |  |  |  |  |  |  |
| Synthetic 4 (High-CPI) | LL | 0.9433 | 0.9345 | 0 | 24/24 | 0 |
| Synthetic 4 (High-CPI) | ALL | 0.9433 | 0.9345 | 0 | 24/24 | 0 |
| Synthetic 4 (High-CPI) | CF | 0.9763 | 0.9702 | 0 | 24/24 | 0 |
| Synthetic 4 (High-CPI) | TR | 0.8285 | 0.7976 | 0 | 24/24 | 0 |
| Synthetic 4 (High-CPI) | TLL | 0.8331 | 0.8036 | 0 | 24/24 | 0 |
|  |  |  |  |  |  |  |

### 1b. Per-Tier Student Satisfaction

| Dataset | Policy | Tier | Count | Mean Rank ↓ | Within-Window % ↑ | Mean NPSS ↑ | Mean PSI ↑ |
|---------|--------|------|-------|-------------|-------------------|-------------|------------|
| 2019 Cohort | LL | A | 7 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2019 Cohort | LL | B1 | 7 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2019 Cohort | LL | B2 | 7 | 1.71 | 100.0% | 0.9714 | 0.9702 |
| 2019 Cohort | LL | C | 7 | 4.57 | 100.0% | 0.8571 | 0.8512 |
| 2019 Cohort | ALL | A | 7 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2019 Cohort | ALL | B1 | 7 | 3.14 | 100.0% | 0.9143 | 0.9107 |
| 2019 Cohort | ALL | B2 | 7 | 1.29 | 100.0% | 0.9886 | 0.9881 |
| 2019 Cohort | ALL | C | 7 | 7.14 | 100.0% | 0.7543 | 0.7440 |
| 2019 Cohort | CF | A | 7 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2019 Cohort | CF | B1 | 7 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2019 Cohort | CF | B2 | 7 | 3.71 | 71.4% | 0.8914 | 0.8869 |
| 2019 Cohort | CF | C | 7 | 8.29 | 100.0% | 0.7086 | 0.6964 |
| 2019 Cohort | TR | A | 7 | 1.14 | 100.0% | 0.9943 | 0.9940 |
| 2019 Cohort | TR | B1 | 7 | 1.43 | 100.0% | 0.9829 | 0.9821 |
| 2019 Cohort | TR | B2 | 7 | 1.43 | 100.0% | 0.9829 | 0.9821 |
| 2019 Cohort | TR | C | 7 | 2.00 | 100.0% | 0.9600 | 0.9583 |
| 2019 Cohort | TLL | A | 7 | 1.14 | 100.0% | 0.9943 | 0.9940 |
| 2019 Cohort | TLL | B1 | 7 | 1.43 | 100.0% | 0.9829 | 0.9821 |
| 2019 Cohort | TLL | B2 | 7 | 3.86 | 71.4% | 0.8857 | 0.8810 |
| 2019 Cohort | TLL | C | 7 | 7.29 | 100.0% | 0.7486 | 0.7381 |
| 2020 Cohort | LL | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2020 Cohort | LL | B1 | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| 2020 Cohort | LL | B2 | 11 | 1.91 | 100.0% | 0.9707 | 0.9697 |
| 2020 Cohort | LL | C | 11 | 8.91 | 100.0% | 0.7449 | 0.7364 |
| 2020 Cohort | ALL | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2020 Cohort | ALL | B1 | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| 2020 Cohort | ALL | B2 | 11 | 1.91 | 100.0% | 0.9707 | 0.9697 |
| 2020 Cohort | ALL | C | 11 | 8.91 | 100.0% | 0.7449 | 0.7364 |
| 2020 Cohort | CF | A | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2020 Cohort | CF | B1 | 11 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| 2020 Cohort | CF | B2 | 11 | 1.55 | 100.0% | 0.9824 | 0.9818 |
| 2020 Cohort | CF | C | 11 | 12.09 | 100.0% | 0.6422 | 0.6303 |
| 2020 Cohort | TR | A | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| 2020 Cohort | TR | B1 | 11 | 1.82 | 90.9% | 0.9736 | 0.9727 |
| 2020 Cohort | TR | B2 | 11 | 2.00 | 100.0% | 0.9677 | 0.9667 |
| 2020 Cohort | TR | C | 11 | 2.45 | 100.0% | 0.9531 | 0.9515 |
| 2020 Cohort | TLL | A | 11 | 1.18 | 100.0% | 0.9941 | 0.9939 |
| 2020 Cohort | TLL | B1 | 11 | 1.45 | 100.0% | 0.9853 | 0.9848 |
| 2020 Cohort | TLL | B2 | 11 | 2.18 | 100.0% | 0.9619 | 0.9606 |
| 2020 Cohort | TLL | C | 11 | 12.27 | 100.0% | 0.6364 | 0.6242 |
| Synthetic 1 (Random) | LL | A | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 1 (Random) | LL | B1 | 6 | 1.67 | 100.0% | 0.9167 | 0.9048 |
| Synthetic 1 (Random) | LL | B2 | 6 | 1.67 | 100.0% | 0.9167 | 0.9048 |
| Synthetic 1 (Random) | LL | C | 6 | 2.83 | 100.0% | 0.7708 | 0.7381 |
| Synthetic 1 (Random) | ALL | A | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 1 (Random) | ALL | B1 | 6 | 1.67 | 100.0% | 0.9167 | 0.9048 |
| Synthetic 1 (Random) | ALL | B2 | 6 | 1.67 | 100.0% | 0.9167 | 0.9048 |
| Synthetic 1 (Random) | ALL | C | 6 | 2.83 | 100.0% | 0.7708 | 0.7381 |
| Synthetic 1 (Random) | CF | A | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 1 (Random) | CF | B1 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 1 (Random) | CF | B2 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 1 (Random) | CF | C | 6 | 1.33 | 100.0% | 0.9583 | 0.9524 |
| Synthetic 1 (Random) | TR | A | 6 | 1.33 | 100.0% | 0.9583 | 0.9524 |
| Synthetic 1 (Random) | TR | B1 | 6 | 2.00 | 100.0% | 0.8750 | 0.8571 |
| Synthetic 1 (Random) | TR | B2 | 6 | 3.00 | 100.0% | 0.7500 | 0.7143 |
| Synthetic 1 (Random) | TR | C | 6 | 3.00 | 100.0% | 0.7500 | 0.7143 |
| Synthetic 1 (Random) | TLL | A | 6 | 1.33 | 100.0% | 0.9583 | 0.9524 |
| Synthetic 1 (Random) | TLL | B1 | 6 | 2.00 | 100.0% | 0.8750 | 0.8571 |
| Synthetic 1 (Random) | TLL | B2 | 6 | 3.00 | 100.0% | 0.7500 | 0.7143 |
| Synthetic 1 (Random) | TLL | C | 6 | 3.00 | 100.0% | 0.7500 | 0.7143 |
| Synthetic 2 (Clustered) | LL | A | 6 | 1.17 | 100.0% | 0.9792 | 0.9762 |
| Synthetic 2 (Clustered) | LL | B1 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 2 (Clustered) | LL | B2 | 6 | 1.17 | 100.0% | 0.9792 | 0.9762 |
| Synthetic 2 (Clustered) | LL | C | 6 | 3.50 | 100.0% | 0.6875 | 0.6429 |
| Synthetic 2 (Clustered) | ALL | A | 6 | 1.17 | 100.0% | 0.9792 | 0.9762 |
| Synthetic 2 (Clustered) | ALL | B1 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 2 (Clustered) | ALL | B2 | 6 | 1.17 | 100.0% | 0.9792 | 0.9762 |
| Synthetic 2 (Clustered) | ALL | C | 6 | 3.50 | 100.0% | 0.6875 | 0.6429 |
| Synthetic 2 (Clustered) | CF | A | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 2 (Clustered) | CF | B1 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 2 (Clustered) | CF | B2 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 2 (Clustered) | CF | C | 6 | 1.17 | 100.0% | 0.9792 | 0.9762 |
| Synthetic 2 (Clustered) | TR | A | 6 | 1.50 | 100.0% | 0.9375 | 0.9286 |
| Synthetic 2 (Clustered) | TR | B1 | 6 | 1.50 | 100.0% | 0.9375 | 0.9286 |
| Synthetic 2 (Clustered) | TR | B2 | 6 | 2.50 | 100.0% | 0.8125 | 0.7857 |
| Synthetic 2 (Clustered) | TR | C | 6 | 3.00 | 100.0% | 0.7500 | 0.7143 |
| Synthetic 2 (Clustered) | TLL | A | 6 | 1.50 | 100.0% | 0.9375 | 0.9286 |
| Synthetic 2 (Clustered) | TLL | B1 | 6 | 1.50 | 100.0% | 0.9375 | 0.9286 |
| Synthetic 2 (Clustered) | TLL | B2 | 6 | 2.33 | 100.0% | 0.8333 | 0.8095 |
| Synthetic 2 (Clustered) | TLL | C | 6 | 2.83 | 100.0% | 0.7708 | 0.7381 |
| Synthetic 3 (Polarised) | LL | A | 6 | 1.33 | 100.0% | 0.9583 | 0.9524 |
| Synthetic 3 (Polarised) | LL | B1 | 6 | 2.67 | 100.0% | 0.7917 | 0.7619 |
| Synthetic 3 (Polarised) | LL | B2 | 6 | 1.50 | 100.0% | 0.9375 | 0.9286 |
| Synthetic 3 (Polarised) | LL | C | 6 | 3.83 | 100.0% | 0.6458 | 0.5952 |
| Synthetic 3 (Polarised) | ALL | A | 6 | 1.33 | 100.0% | 0.9583 | 0.9524 |
| Synthetic 3 (Polarised) | ALL | B1 | 6 | 2.67 | 100.0% | 0.7917 | 0.7619 |
| Synthetic 3 (Polarised) | ALL | B2 | 6 | 1.50 | 100.0% | 0.9375 | 0.9286 |
| Synthetic 3 (Polarised) | ALL | C | 6 | 3.83 | 100.0% | 0.6458 | 0.5952 |
| Synthetic 3 (Polarised) | CF | A | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 3 (Polarised) | CF | B1 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 3 (Polarised) | CF | B2 | 6 | 1.17 | 100.0% | 0.9792 | 0.9762 |
| Synthetic 3 (Polarised) | CF | C | 6 | 1.83 | 100.0% | 0.8958 | 0.8810 |
| Synthetic 3 (Polarised) | TR | A | 6 | 1.50 | 100.0% | 0.9375 | 0.9286 |
| Synthetic 3 (Polarised) | TR | B1 | 6 | 2.00 | 100.0% | 0.8750 | 0.8571 |
| Synthetic 3 (Polarised) | TR | B2 | 6 | 2.00 | 100.0% | 0.8750 | 0.8571 |
| Synthetic 3 (Polarised) | TR | C | 6 | 3.00 | 100.0% | 0.7500 | 0.7143 |
| Synthetic 3 (Polarised) | TLL | A | 6 | 1.50 | 100.0% | 0.9375 | 0.9286 |
| Synthetic 3 (Polarised) | TLL | B1 | 6 | 2.00 | 100.0% | 0.8750 | 0.8571 |
| Synthetic 3 (Polarised) | TLL | B2 | 6 | 2.00 | 100.0% | 0.8750 | 0.8571 |
| Synthetic 3 (Polarised) | TLL | C | 6 | 2.83 | 100.0% | 0.7708 | 0.7381 |
| Synthetic 4 (High-CPI) | LL | A | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 4 (High-CPI) | LL | B1 | 6 | 2.00 | 100.0% | 0.8750 | 0.8571 |
| Synthetic 4 (High-CPI) | LL | B2 | 6 | 1.17 | 100.0% | 0.9792 | 0.9762 |
| Synthetic 4 (High-CPI) | LL | C | 6 | 1.67 | 100.0% | 0.9167 | 0.9048 |
| Synthetic 4 (High-CPI) | ALL | A | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 4 (High-CPI) | ALL | B1 | 6 | 2.00 | 100.0% | 0.8750 | 0.8571 |
| Synthetic 4 (High-CPI) | ALL | B2 | 6 | 1.17 | 100.0% | 0.9792 | 0.9762 |
| Synthetic 4 (High-CPI) | ALL | C | 6 | 1.67 | 100.0% | 0.9167 | 0.9048 |
| Synthetic 4 (High-CPI) | CF | A | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 4 (High-CPI) | CF | B1 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 4 (High-CPI) | CF | B2 | 6 | 1.00 | 100.0% | 1.0000 | 1.0000 |
| Synthetic 4 (High-CPI) | CF | C | 6 | 1.83 | 100.0% | 0.8958 | 0.8810 |
| Synthetic 4 (High-CPI) | TR | A | 6 | 1.33 | 100.0% | 0.9583 | 0.9524 |
| Synthetic 4 (High-CPI) | TR | B1 | 6 | 2.33 | 100.0% | 0.8333 | 0.8095 |
| Synthetic 4 (High-CPI) | TR | B2 | 6 | 2.33 | 100.0% | 0.8333 | 0.8095 |
| Synthetic 4 (High-CPI) | TR | C | 6 | 3.67 | 100.0% | 0.6667 | 0.6190 |
| Synthetic 4 (High-CPI) | TLL | A | 6 | 1.33 | 100.0% | 0.9583 | 0.9524 |
| Synthetic 4 (High-CPI) | TLL | B1 | 6 | 2.33 | 100.0% | 0.8333 | 0.8095 |
| Synthetic 4 (High-CPI) | TLL | B2 | 6 | 2.33 | 100.0% | 0.8333 | 0.8095 |
| Synthetic 4 (High-CPI) | TLL | C | 6 | 3.50 | 100.0% | 0.6875 | 0.6429 |

## 2. Advisor Metrics — Per Dataset

| Dataset | Policy | Avg MSES ↓ | Avg LUR | Equity Ret% ↑ | CPI Skewness *(diag)* |
|---------|--------|-----------|---------|---------------|----------------------|
| 2019 Cohort | LL | 2.2174 | 60.9% | 60.0% | -0.6584 |
| 2019 Cohort | ALL | 3.3800 | 56.0% | 33.3% | -0.7343 |
| 2019 Cohort | CF | 3.8000 | 56.0% | 66.7% | -0.5969 |
| 2019 Cohort | TR | 1.3810 | 66.7% | 71.4% | -0.9482 |
| 2019 Cohort | TLL | 3.6400 | 56.0% | 33.3% | -0.5947 |
|  |  |  |  |  |  |
| 2020 Cohort | LL | 4.0806 | 71.0% | 76.9% | 0.4597 |
| 2020 Cohort | ALL | 4.0806 | 71.0% | 76.9% | 0.4597 |
| 2020 Cohort | CF | 5.0484 | 71.0% | 76.9% | 0.2033 |
| 2020 Cohort | TR | 1.7600 | 88.0% | 84.2% | -0.3863 |
| 2020 Cohort | TLL | 5.2742 | 71.0% | 76.9% | 0.0681 |
|  |  |  |  |  |  |
| Synthetic 1 (Random) | LL | 1.7917 | 75.0% | 68.5% | -0.6476 |
| Synthetic 1 (Random) | ALL | 1.7917 | 75.0% | 68.5% | -0.6476 |
| Synthetic 1 (Random) | CF | 1.0729 | 75.0% | 76.1% | 0.1610 |
| Synthetic 1 (Random) | TR | 2.2396 | 75.0% | 86.3% | 0.5135 |
| Synthetic 1 (Random) | TLL | 2.2396 | 75.0% | 86.3% | 0.5135 |
|  |  |  |  |  |  |
| Synthetic 2 (Clustered) | LL | 1.7083 | 75.0% | 79.0% | 0.5864 |
| Synthetic 2 (Clustered) | ALL | 1.7083 | 75.0% | 79.0% | 0.5864 |
| Synthetic 2 (Clustered) | CF | 1.0312 | 75.0% | 66.7% | -0.0693 |
| Synthetic 2 (Clustered) | TR | 2.0833 | 75.0% | 80.0% | 0.2567 |
| Synthetic 2 (Clustered) | TLL | 2.0000 | 75.0% | 77.0% | -0.5748 |
|  |  |  |  |  |  |
| Synthetic 3 (Polarised) | LL | 2.3333 | 75.0% | 50.7% | -0.2191 |
| Synthetic 3 (Polarised) | ALL | 2.3333 | 75.0% | 50.7% | -0.2191 |
| Synthetic 3 (Polarised) | CF | 1.2812 | 75.0% | 32.2% | -0.1304 |
| Synthetic 3 (Polarised) | TR | 2.0417 | 75.0% | 50.5% | -0.0886 |
| Synthetic 3 (Polarised) | TLL | 2.0104 | 75.0% | 58.0% | -0.0741 |
|  |  |  |  |  |  |
| Synthetic 4 (High-CPI) | LL | 1.4583 | 75.0% | 73.7% | -0.4853 |
| Synthetic 4 (High-CPI) | ALL | 1.4583 | 75.0% | 73.7% | -0.4853 |
| Synthetic 4 (High-CPI) | CF | 1.2812 | 75.0% | 69.3% | -0.7336 |
| Synthetic 4 (High-CPI) | TR | 2.2604 | 75.0% | 70.0% | 0.7821 |
| Synthetic 4 (High-CPI) | TLL | 2.1979 | 75.0% | 63.8% | 1.1267 |
|  |  |  |  |  |  |

## 3. `tiered_ll` Critical Round k

| Dataset | k_crit | Notes |
|---------|--------|-------|
| 2019 Cohort | 1 | — |
| 2020 Cohort | 1 | — |
| Synthetic 1 (Random) | 3 | — |
| Synthetic 2 (Clustered) | 2 | — |
| Synthetic 3 (Polarised) | 2 | — |
| Synthetic 4 (High-CPI) | 3 | — |

## 4. Aggregate Statistics (mean ± std across 5 datasets)

> Values are mean ± std across the 5 datasets. With only 5 datasets
> these comparisons are descriptive, not inferential. Only 2 cohorts are real data;
> significance testing would require more cohorts.

| Metric | LL | ALL | CF | TR | TLL | Best |
|--------|--------|--------|--------|--------|--------|------|
| NPSS | 0.923 ± 0.039 | 0.917 ± 0.034 | 0.963 ± 0.035 | 0.896 ± 0.066 | 0.877 ± 0.033 | **CF** |
| PSI | 0.902 ± 0.051 | 0.894 ± 0.045 | 0.953 ± 0.043 | 0.873 ± 0.081 | 0.850 ± 0.040 | **CF** |
| Overflow | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.333 ± 0.816 | 0.167 ± 0.408 | 0.333 ± 0.816 | **LL** |
| % In Window | 100.000 ± 0.000 | 100.000 ± 0.000 | 98.810 ± 2.916 | 99.621 ± 0.928 | 98.810 ± 2.916 | **LL** |
| Empty Labs | 0.333 ± 0.816 | 0.000 ± 0.000 | 0.000 ± 0.000 | 1.667 ± 2.658 | 0.000 ± 0.000 | **ALL** |
| Avg MSES | 2.265 ± 0.947 | 2.459 ± 1.049 | 2.253 ± 1.731 | 1.961 ± 0.336 | 2.894 ± 1.320 | **TR** |
| Equity Ret% | 68.125 ± 10.919 | 63.681 ± 18.011 | 64.649 ± 16.524 | 73.753 ± 13.159 | 65.899 ± 18.923 | **TR** |
| Avg LUR | 71.973 ± 5.674 | 71.161 ± 7.601 | 71.161 ± 7.601 | 75.778 ± 6.853 | 71.161 ± 7.601 | **TR** |
| |CPI Skewness| | 0.509 ± 0.164 | 0.522 ± 0.180 | 0.316 ± 0.278 | 0.496 ± 0.323 | 0.492 ± 0.394 | **CF** |

## 5. Per-Dataset Deltas vs `least_loaded` (baseline)

Positive Δ = better than LL for higher-is-better metrics; negative = worse.  
Empty labs and overflow: negative Δ = fewer (better).  

### 5a. NPSS

| Dataset | LL | ΔALL | ΔCF | ΔTR | ΔTLL |
|---------|----|--------|--------|--------|--------|
| 2019 Cohort | 0.962 | -0.038 | -0.048 | +0.020 | -0.047 |
| 2020 Cohort | 0.938 | +0.000 | -0.013 | +0.036 | -0.026 |
| Synthetic 1 (Random) | 0.913 | +0.000 | +0.078 | -0.068 | -0.068 |
| Synthetic 2 (Clustered) | 0.931 | +0.000 | +0.065 | -0.056 | -0.048 |
| Synthetic 3 (Polarised) | 0.851 | +0.000 | +0.124 | +0.018 | +0.023 |
| Synthetic 4 (High-CPI) | 0.943 | +0.000 | +0.033 | -0.115 | -0.110 |

### 5b. PSI

| Dataset | LL | ΔALL | ΔCF | ΔTR | ΔTLL |
|---------|----|--------|--------|--------|--------|
| 2019 Cohort | 0.955 | -0.045 | -0.060 | +0.024 | -0.057 |
| 2020 Cohort | 0.925 | +0.000 | -0.022 | +0.046 | -0.034 |
| Synthetic 1 (Random) | 0.887 | +0.000 | +0.101 | -0.077 | -0.077 |
| Synthetic 2 (Clustered) | 0.899 | +0.000 | +0.095 | -0.060 | -0.048 |
| Synthetic 3 (Polarised) | 0.810 | +0.000 | +0.155 | +0.030 | +0.036 |
| Synthetic 4 (High-CPI) | 0.935 | +0.000 | +0.036 | -0.137 | -0.131 |

### 5c. Overflow

| Dataset | LL | ΔALL | ΔCF | ΔTR | ΔTLL |
|---------|----|--------|--------|--------|--------|
| 2019 Cohort | 0.000 | +0.000 | +2.000 | +0.000 | +2.000 |
| 2020 Cohort | 0.000 | +0.000 | +0.000 | +1.000 | +0.000 |
| Synthetic 1 (Random) | 0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Synthetic 2 (Clustered) | 0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Synthetic 3 (Polarised) | 0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Synthetic 4 (High-CPI) | 0.000 | +0.000 | +0.000 | +0.000 | +0.000 |

### 5d. Empty Labs

| Dataset | LL | ΔALL | ΔCF | ΔTR | ΔTLL |
|---------|----|--------|--------|--------|--------|
| 2019 Cohort | 2.000 | -2.000 | -2.000 | +2.000 | -2.000 |
| 2020 Cohort | 0.000 | +0.000 | +0.000 | +6.000 | +0.000 |
| Synthetic 1 (Random) | 0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Synthetic 2 (Clustered) | 0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Synthetic 3 (Polarised) | 0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Synthetic 4 (High-CPI) | 0.000 | +0.000 | +0.000 | +0.000 | +0.000 |

### 5e. Equity Ret%

| Dataset | LL | ΔALL | ΔCF | ΔTR | ΔTLL |
|---------|----|--------|--------|--------|--------|
| 2019 Cohort | 60.000 | -26.667 | +6.667 | +11.429 | -26.667 |
| 2020 Cohort | 76.923 | +0.000 | +0.000 | +7.287 | +0.000 |
| Synthetic 1 (Random) | 68.454 | +0.000 | +7.673 | +17.861 | +17.861 |
| Synthetic 2 (Clustered) | 78.969 | +0.000 | -12.248 | +1.047 | -1.930 |
| Synthetic 3 (Polarised) | 50.696 | +0.000 | -18.499 | -0.186 | +7.256 |
| Synthetic 4 (High-CPI) | 73.711 | +0.000 | -4.451 | -3.674 | -9.880 |

### 5f. Avg MSES

| Dataset | LL | ΔALL | ΔCF | ΔTR | ΔTLL |
|---------|----|--------|--------|--------|--------|
| 2019 Cohort | 2.217 | +1.163 | +1.583 | -0.836 | +1.423 |
| 2020 Cohort | 4.081 | +0.000 | +0.968 | -2.321 | +1.194 |
| Synthetic 1 (Random) | 1.792 | +0.000 | -0.719 | +0.448 | +0.448 |
| Synthetic 2 (Clustered) | 1.708 | +0.000 | -0.677 | +0.375 | +0.292 |
| Synthetic 3 (Polarised) | 2.333 | +0.000 | -1.052 | -0.292 | -0.323 |
| Synthetic 4 (High-CPI) | 1.458 | +0.000 | -0.177 | +0.802 | +0.740 |

## 6. Assigned Preference Rank Distributions

| Dataset | Policy | Min | Median | Mean | Max | Std |
|---------|--------|-----|--------|------|-----|-----|
| 2019 Cohort | LL | 1 | 1.0 | 2.07 | 16 | 3.24 |
| 2019 Cohort | ALL | 1 | 1.0 | 3.14 | 20 | 4.92 |
| 2019 Cohort | CF | 1 | 1.0 | 3.50 | 20 | 5.03 |
| 2019 Cohort | TR | 1 | 1.0 | 1.50 | 6 | 1.04 |
| 2019 Cohort | TLL | 1 | 1.0 | 3.43 | 18 | 5.02 |
| 2020 Cohort | LL | 1 | 1.0 | 3.25 | 30 | 6.27 |
| 2020 Cohort | ALL | 1 | 1.0 | 3.25 | 30 | 6.27 |
| 2020 Cohort | CF | 1 | 1.0 | 3.91 | 31 | 6.77 |
| 2020 Cohort | TR | 1 | 1.0 | 1.86 | 7 | 1.42 |
| 2020 Cohort | TLL | 1 | 1.0 | 4.27 | 31 | 6.75 |
| Synthetic 1 (Random) | LL | 1 | 1.0 | 1.79 | 7 | 1.44 |
| Synthetic 1 (Random) | ALL | 1 | 1.0 | 1.79 | 7 | 1.44 |
| Synthetic 1 (Random) | CF | 1 | 1.0 | 1.08 | 2 | 0.28 |
| Synthetic 1 (Random) | TR | 1 | 2.0 | 2.33 | 5 | 1.24 |
| Synthetic 1 (Random) | TLL | 1 | 2.0 | 2.33 | 5 | 1.24 |
| Synthetic 2 (Clustered) | LL | 1 | 1.0 | 1.71 | 8 | 1.68 |
| Synthetic 2 (Clustered) | ALL | 1 | 1.0 | 1.71 | 8 | 1.68 |
| Synthetic 2 (Clustered) | CF | 1 | 1.0 | 1.04 | 2 | 0.20 |
| Synthetic 2 (Clustered) | TR | 1 | 2.0 | 2.12 | 4 | 0.99 |
| Synthetic 2 (Clustered) | TLL | 1 | 2.0 | 2.04 | 3 | 0.86 |
| Synthetic 3 (Polarised) | LL | 1 | 1.5 | 2.33 | 5 | 1.69 |
| Synthetic 3 (Polarised) | ALL | 1 | 1.5 | 2.33 | 5 | 1.69 |
| Synthetic 3 (Polarised) | CF | 1 | 1.0 | 1.25 | 4 | 0.68 |
| Synthetic 3 (Polarised) | TR | 1 | 2.0 | 2.12 | 4 | 1.03 |
| Synthetic 3 (Polarised) | TLL | 1 | 2.0 | 2.08 | 4 | 0.97 |
| Synthetic 4 (High-CPI) | LL | 1 | 1.0 | 1.46 | 4 | 0.72 |
| Synthetic 4 (High-CPI) | ALL | 1 | 1.0 | 1.46 | 4 | 0.72 |
| Synthetic 4 (High-CPI) | CF | 1 | 1.0 | 1.21 | 3 | 0.51 |
| Synthetic 4 (High-CPI) | TR | 1 | 2.0 | 2.42 | 5 | 1.21 |
| Synthetic 4 (High-CPI) | TLL | 1 | 2.0 | 2.38 | 4 | 1.13 |

---

## 7. Summary and Policy Guidance

### 7a. Win counts (best policy per dataset per metric)

A win is counted only when the best policy exceeds the runner-up by ≥ threshold.

| Metric | Threshold | LL | ALL | CF | TR | TLL | Draw |
|--------|-----------|---|---|---|---|---|-----|
| NPSS | ≥ 0.04 | 0 | 0 | 3 | 0 | 0 | 3 |
| PSI | ≥ 0.025 | 0 | 0 | 4 | 1 | 0 | 1 |
| Avg MSES | ≥ 0.5 | 0 | 0 | 3 | 2 | 0 | 1 |
| Equity Ret% | ≥ 5.0 | 0 | 0 | 0 | 1 | 1 | 4 |

---

## 8. Real-Cohort Findings

> The 2019 and 2020 cohorts are the only real datasets in this study.
> All other datasets are synthetic. Real-cohort results reflect actual
> student preference structure and carry greater practical weight.

### 2019 Cohort (S=28, F=25, S/F=1.1)

**NPSS ranking (all students assigned in all runs):**

| Rank | Policy | NPSS | PSI | Empty Labs | Note |
|------|--------|------|-----|------------|------|
| 1 | `tiered_rounds` (TR) | 0.9817 | 0.9792 | 4 | ⚠ 4 empty lab(s) |
| 2 | `least_loaded` (LL) | 0.9616 | 0.9554 | 2 | ⚠ 2 empty lab(s) |
| 3 | `adaptive_ll` (ALL) | 0.9240 | 0.9107 | 0 |  |
| 4 | `tiered_ll` (TLL) | 0.9146 | 0.8988 | 0 | k_crit=1 |
| 5 | `cpi_fill` (CF) | 0.9132 | 0.8958 | 0 |  |

- `tiered_rounds` achieves the highest NPSS (0.9817) but leaves **4 empty lab(s)**.
- Among policies with zero empty labs, `adaptive_ll` leads NPSS (0.9240).
- `least_loaded` leaves 2 empty lab(s); `adaptive_ll` eliminates them at the cost of ΔNPSS=-0.0375.
- `tiered_ll` (k_crit=1) trades ΔNPSS=-0.0671 vs `tiered_rounds` to eliminate its 4 empty lab(s).

**Per-student assignments — 2019 Cohort** *(faculty name, rank in brackets)*

| # | Student | CPI | LL | ALL | CF | TR | TLL |
|---|---------|-----|-----|-----|-----|-----|-----|
| 1 | student02 | 9.96 | Prof02 (1) | Prof02 (1) | Prof02 (1) | Prof02 (1) | Prof02 (1) |
| 2 | student01 | 9.56 | Prof01 (1) | Prof01 (1) | Prof01 (1) | Prof01 (1) | Prof01 (1) |
| 3 | student09 | 9.52 | Prof09 (1) | Prof09 (1) | Prof09 (1) | Prof09 (1) | Prof09 (1) |
| 4 | student07 | 9.29 | Prof07 (1) | Prof07 (1) | Prof07 (1) | Prof07 (1) | Prof07 (1) |
| 5 | student15 | 9.18 | Prof13 (1) | Prof13 (1) | Prof13 (1) | Prof13 (1) | Prof13 (1) |
| 6 | student16 | 9.08 | Prof09 (1) | Prof09 (1) | Prof09 (1) | Prof07 (2) | Prof07 (2) |
| 7 | student18 | 8.95 | Prof14 (1) | Prof14 (1) | Prof14 (1) | Prof14 (1) | Prof14 (1) |
| 8 | student04 | 8.93 | Prof04 (1) | Prof04 (1) | Prof04 (1) | Prof04 (1) | Prof04 (1) |
| 9 | student08 | 8.82 | Prof08 (1) | Prof08 (1) | Prof08 (1) | Prof08 (1) | Prof08 (1) |
| 10 | student21 | 8.79 | Prof15 (1) | Prof15 (1) | Prof15 (1) | Prof15 (1) | Prof15 (1) |
| 11 | student11 | 8.72 | Prof10 (1) | Prof10 (1) | Prof10 (1) | Prof10 (1) | Prof10 (1) |
| 12 | student12 | 8.68 | Prof06 (1) | Prof06 (1) | Prof06 (1) | Prof06 (1) | Prof06 (1) |
| 13 | student17 | 8.63 | Prof14 (1) | Prof22 (8) | Prof14 (1) | Prof11 (2) | Prof11 (2) |
| 14 | student20 | 8.50 | Prof13 (1) | Prof25 (9) | Prof13 (1) | Prof10 (3) | Prof10 (3) |
| 15 | student05 | 8.45 | Prof05 (1) | Prof05 (1) | Prof05 (1) | Prof05 (1) | Prof05 (1) |
| 16 | student06 | 8.40 | Prof20 (2) | Prof20 (2) | Prof20 (2) | Prof20 (2) | Prof20 (2) |
| 17 | student13 | 8.16 | Prof11 (1) | Prof11 (1) | Prof11 (1) | Prof11 (1) | Prof11 (1) |
| 18 | student26 | 8.05 | Prof19 (1) | Prof19 (1) | Prof19 (1) | Prof19 (1) | Prof19 (1) |
| 19 | student14 | 7.99 | Prof12 (1) | Prof12 (1) | Prof12 (1) | Prof12 (1) | Prof12 (1) |
| 20 | student19 | 7.83 | Prof05 (3) | Prof13 (2) | Prof22 (11) | Prof13 (2) | Prof22 (11) |
| 21 | student10 | 7.82 | Prof07 (3) | Prof05 (1) | Prof18 (9) | Prof09 (2) | Prof24 (10) |
| 22 | student24 | 7.81 | Prof21 (16) | Prof21 (16) | Prof17 (10) | Prof08 (2) | Prof21 (16) |
| 23 | student22 | 7.62 | Prof16 (1) | Prof16 (1) | Prof16 (1) | Prof16 (1) | Prof16 (1) |
| 24 | student25 | 7.62 | Prof18 (1) | Prof18 (1) | Prof25 (14) | Prof18 (1) | Prof18 (1) |
| 25 | student03 | 7.56 | Prof03 (1) | Prof03 (1) | Prof03 (1) | Prof03 (1) | Prof03 (1) |
| 26 | student27 | 6.74 | Prof24 (10) | Prof24 (10) | Prof24 (10) | Prof01 (6) | Prof23 (13) |
| 27 | student28 | 6.32 | Prof22 (2) | Prof23 (20) | Prof23 (20) | Prof22 (2) | Prof25 (18) |
| 28 | student23 | 6.03 | Prof17 (1) | Prof17 (1) | Prof21 (2) | Prof17 (1) | Prof17 (1) |

### 2020 Cohort (S=44, F=31, S/F=1.4)

**NPSS ranking (all students assigned in all runs):**

| Rank | Policy | NPSS | PSI | Empty Labs | Note |
|------|--------|------|-----|------------|------|
| 1 | `tiered_rounds` (TR) | 0.9739 | 0.9712 | 6 | ⚠ 6 empty lab(s) |
| 2 | `least_loaded` (LL) | 0.9379 | 0.9250 | 0 |  |
| 3 | `adaptive_ll` (ALL) | 0.9379 | 0.9250 | 0 |  |
| 4 | `cpi_fill` (CF) | 0.9253 | 0.9030 | 0 |  |
| 5 | `tiered_ll` (TLL) | 0.9118 | 0.8909 | 0 | k_crit=1 |

- `tiered_rounds` achieves the highest NPSS (0.9739) but leaves **6 empty lab(s)**.
- Among policies with zero empty labs, `least_loaded` leads NPSS (0.9379).
- `least_loaded` scores NPSS=0.9379 with zero empty labs — the best fully-automatic, coverage-guaranteed option.
- `tiered_ll` (k_crit=1) trades ΔNPSS=-0.0621 vs `tiered_rounds` to eliminate its 6 empty lab(s).

**Per-student assignments — 2020 Cohort** *(faculty name, rank in brackets)*

| # | Student | CPI | LL | ALL | CF | TR | TLL |
|---|---------|-----|-----|-----|-----|-----|-----|
| 1 | student31 | 9.66 | Prof26 (1) | Prof26 (1) | Prof26 (1) | Prof26 (1) | Prof26 (1) |
| 2 | student29 | 9.47 | Prof01 (1) | Prof01 (1) | Prof01 (1) | Prof01 (1) | Prof01 (1) |
| 3 | student58 | 9.38 | Prof01 (1) | Prof01 (1) | Prof01 (1) | Prof11 (2) | Prof11 (2) |
| 4 | student62 | 9.32 | Prof05 (1) | Prof05 (1) | Prof05 (1) | Prof05 (1) | Prof05 (1) |
| 5 | student36 | 9.01 | Prof07 (1) | Prof07 (1) | Prof07 (1) | Prof07 (1) | Prof07 (1) |
| 6 | student49 | 8.92 | Prof16 (1) | Prof16 (1) | Prof16 (1) | Prof16 (1) | Prof16 (1) |
| 7 | student37 | 8.76 | Prof10 (1) | Prof10 (1) | Prof10 (1) | Prof10 (1) | Prof10 (1) |
| 8 | student60 | 8.66 | Prof09 (1) | Prof09 (1) | Prof09 (1) | Prof09 (1) | Prof09 (1) |
| 9 | student61 | 8.66 | Prof05 (1) | Prof05 (1) | Prof05 (1) | Prof20 (2) | Prof20 (2) |
| 10 | student48 | 8.62 | Prof08 (1) | Prof08 (1) | Prof08 (1) | Prof08 (1) | Prof08 (1) |
| 11 | student39 | 8.39 | Prof13 (1) | Prof13 (1) | Prof13 (1) | Prof13 (1) | Prof13 (1) |
| 12 | student63 | 8.32 | Prof18 (1) | Prof18 (1) | Prof18 (1) | Prof18 (1) | Prof18 (1) |
| 13 | student51 | 8.06 | Prof30 (3) | Prof30 (3) | Prof07 (1) | Prof14 (2) | Prof14 (2) |
| 14 | student53 | 8.03 | Prof14 (1) | Prof14 (1) | Prof14 (1) | Prof14 (1) | Prof14 (1) |
| 15 | student45 | 7.91 | Prof20 (1) | Prof20 (1) | Prof20 (1) | Prof20 (1) | Prof20 (1) |
| 16 | student32 | 7.85 | Prof11 (1) | Prof11 (1) | Prof11 (1) | Prof11 (1) | Prof11 (1) |
| 17 | student38 | 7.82 | Prof04 (1) | Prof04 (1) | Prof04 (1) | Prof04 (1) | Prof04 (1) |
| 18 | student42 | 7.75 | Prof26 (1) | Prof26 (1) | Prof26 (1) | Prof21 (7) | Prof09 (3) |
| 19 | student69 | 7.67 | Prof09 (1) | Prof09 (1) | Prof09 (1) | Prof08 (2) | Prof08 (2) |
| 20 | student43 | 7.61 | Prof04 (1) | Prof04 (1) | Prof04 (1) | Prof26 (2) | Prof26 (2) |
| 21 | student72 | 7.47 | Prof22 (1) | Prof22 (1) | Prof22 (1) | Prof22 (1) | Prof22 (1) |
| 22 | student34 | 7.43 | Prof06 (1) | Prof06 (1) | Prof06 (1) | Prof06 (1) | Prof06 (1) |
| 23 | student35 | 7.36 | Prof11 (2) | Prof11 (2) | Prof11 (2) | Prof16 (5) | Prof01 (3) |
| 24 | student50 | 7.28 | Prof10 (1) | Prof10 (1) | Prof10 (1) | Prof28 (4) | Prof23 (3) |
| 25 | student41 | 7.11 | Prof25 (5) | Prof25 (5) | Prof16 (1) | Prof23 (2) | Prof28 (3) |
| 26 | student44 | 7.05 | Prof14 (1) | Prof14 (1) | Prof14 (1) | Prof09 (2) | Prof27 (3) |
| 27 | student70 | 7.03 | Prof21 (1) | Prof21 (1) | Prof21 (1) | Prof21 (1) | Prof21 (1) |
| 28 | student46 | 6.97 | Prof27 (1) | Prof27 (1) | Prof27 (1) | Prof27 (1) | Prof27 (1) |
| 29 | student71 | 6.93 | Prof23 (1) | Prof23 (1) | Prof23 (1) | Prof23 (1) | Prof23 (1) |
| 30 | student68 | 6.87 | Prof19 (1) | Prof19 (1) | Prof19 (1) | Prof19 (1) | Prof19 (1) |
| 31 | student66 | 6.80 | Prof13 (5) | Prof13 (5) | Prof13 (5) | Prof01 (2) | Prof13 (5) |
| 32 | student59 | 6.63 | Prof03 (1) | Prof03 (1) | Prof03 (1) | Prof03 (1) | Prof03 (1) |
| 33 | student54 | 6.56 | Prof12 (2) | Prof12 (2) | Prof12 (2) | Prof12 (2) | Prof12 (2) |
| 34 | student47 | 6.54 | Prof28 (1) | Prof28 (1) | Prof28 (1) | Prof28 (1) | Prof28 (1) |
| 35 | student30 | 6.51 | Prof02 (11) | Prof02 (11) | Prof03 (1) | Prof05 (5) | Prof19 (4) |
| 36 | student33 | 6.45 | Prof29 (12) | Prof29 (12) | Prof19 (1) | Prof06 (2) | Prof29 (12) |
| 37 | student40 | 6.38 | Prof24 (10) | Prof24 (10) | Prof24 (10) | Prof07 (2) | Prof24 (10) |
| 38 | student56 | 6.28 | Prof17 (28) | Prof17 (28) | Prof15 (13) | Prof13 (2) | Prof02 (22) |
| 39 | student67 | 6.18 | Prof31 (30) | Prof31 (30) | Prof02 (6) | Prof02 (6) | Prof25 (16) |
| 40 | student64 | 6.16 | Prof18 (1) | Prof18 (1) | Prof29 (10) | Prof02 (3) | Prof17 (19) |
| 41 | student55 | 5.91 | Prof15 (1) | Prof15 (1) | Prof25 (19) | Prof15 (1) | Prof15 (1) |
| 42 | student57 | 5.82 | Prof16 (1) | Prof16 (1) | Prof30 (18) | Prof10 (2) | Prof30 (18) |
| 43 | student65 | 5.76 | Prof12 (1) | Prof12 (1) | Prof17 (23) | Prof12 (1) | Prof12 (1) |
| 44 | student52 | 5.64 | Prof19 (2) | Prof19 (2) | Prof31 (31) | Prof19 (2) | Prof31 (31) |

**Cross-cohort pattern:**

- `tiered_rounds` leads NPSS on both real cohorts but cannot guarantee coverage.
- `least_loaded` is the highest-NPSS fully-automatic policy with an implicit coverage
  guarantee on the 2019 cohort (2 empty labs) and a full guarantee on 2020.
- `adaptive_ll` reliably closes the empty-lab gap at a modest NPSS cost (~0.04).
- `cpi_fill` underperforms on real data relative to synthetic — real preference
  structures are not random, so strict CPI ordering does not align with actual
  preferences as well as round-based or load-balancing approaches.
- `tiered_ll` k_crit=1 on both cohorts, meaning the dry-run switches to CPI-Fill
  backfill after just one round. This collapses its behaviour toward `cpi_fill`
  and explains why its NPSS tracks close to (but slightly above) `cpi_fill`.

---

### 7b. Policy guidance

| Policy | Best when… | Empty-lab guarantee | Operator involvement |
|--------|-----------|---------------------|----------------------|
| `least_loaded` | Load balance is paramount; best automatic policy on real cohorts | Indirect | None |
| `adaptive_ll` | Structural empty-lab risk detected in Phase 0 | Yes (S ≥ F) | None |
| `cpi_fill` | Random/synthetic preference structure; merit-first goal | Yes (S ≥ F) | None |
| `tiered_rounds` | Maximum preference satisfaction; operator can accept empty labs | No | GUI: manual tie-break |
| `tiered_ll` | Transparent early rounds + coverage guarantee (k_crit > 1 needed for benefit) | Yes (S ≥ F) | GUI: manual tie-break in rounds |

---

*Report generated by `stats/run_study.py` — IISER-B MS Thesis Allocator engine.*