# Advisor Fairness Metrics

Metrics for evaluating the fairness of an MS thesis advisor allocation from the **advisor's perspective** — complementing the student-satisfaction metrics (NPSS and PSI) with a view of whether the allocation distributes students equitably across faculty.

---

## Motivation

Student satisfaction metrics (NPSS, PSI) capture how well student preferences are honoured but say nothing about whether the resulting advisor cohorts are fair. Two concerns arise in practice:

1. **CPI diversity within each advisor's cohort** — does each advisor receive a mix of students from different academic tiers, or do a few advisors consistently attract all the top-CPI students while others receive only low-CPI students? Advisors who supervise only high-CPI students carry a different workload and reputational profile than those supervising only low-CPI students.
2. **Skewness of advisor mean CPIs** — at the system level, is there a small number of advisors whose mean student CPI is much higher (or lower) than the departmental average? High skewness indicates systematic CPI concentration, which may reflect undesired structural bias in the allocation.

Both metrics are computed after the allocation is complete and are reported alongside the snapshot statistics in the Dash interface.

---

## Metric 1 — Normalised CPI Entropy per Advisor

### Definition

For each advisor *a* who has at least one assigned student:

1. Bucket the assigned students into the cohort's CPI tier labels (A / B / C in percentile mode, or A / B1 / B2 / C in quartile mode; see Phase 0 for tier rules).
2. Let *K* be the number of tier labels and `p_k(a)` the fraction of advisor *a*'s students who fall in tier *k*.
3. Compute the **Shannon entropy** of the tier distribution:

$$
H(a) = -\sum_{k=1}^{K} p_k(a) \log p_k(a), \quad \text{with } 0 \log 0 \equiv 0
$$

4. **Normalise** by `log K` so the score lies in `[0, 1]`:

$$
\boxed{H_{\text{norm}}(a) = \frac{H(a)}{\log K}}
$$

### Interpretation

| H_norm value | Meaning |
|--------------|---------|
| **1.0** | Students are distributed evenly across all *K* tiers — maximum diversity |
| **0.0** | All assigned students belong to the same single tier — no diversity |
| Intermediate | Partial diversity; the closer to 1, the more balanced the tier mix |

### Aggregate: Average Normalised Entropy

The system-level fairness score is the **mean of H_norm(a)** across all advisors who received at least one student:

$$
\overline{H}_{\text{norm}} = \frac{1}{|\mathcal{A}|} \sum_{a \in \mathcal{A}} H_{\text{norm}}(a)
$$

A high average entropy indicates that most advisors received a mixed-tier cohort; a low average entropy indicates that tier segregation is widespread across the department.

### Why Shannon entropy?

Shannon entropy is a well-established measure of diversity. It is sensitive to both the number of non-zero categories and the evenness of the distribution — an advisor with two tiers represented equally scores higher than one with two tiers represented 90/10. This mirrors the intuitive fairness notion that advisors should ideally supervise students from across the academic spectrum.

---

## Metric 2 — Skewness of Advisor Mean CPIs

### Definition

For each advisor *a*, compute the **mean CPI** of their assigned students:

$$
\bar{x}_a = \frac{1}{n_a} \sum_{i \in \mathcal{S}_a} \text{CPI}_i
$$

where `n_a` is the number of students assigned to advisor *a* and `S_a` is the set of those students.

Collect the vector of advisor mean CPIs `[x̄_1, x̄_2, …, x̄_A]` for all *A* advisors with at least one student. Compute the **sample skewness** of this vector:

$$
\boxed{\gamma = \frac{A}{(A-1)(A-2)} \sum_{a=1}^{A} \left(\frac{\bar{x}_a - \bar{\bar{x}}}{s}\right)^3}
$$

where:
- `x̄̄` = mean of the advisor mean CPIs
- `s` = sample standard deviation of the advisor mean CPIs
- This is Fisher's adjusted skewness formula (unbiased for normal populations)

Returns `None` if fewer than 3 advisors have students (skewness is undefined for A < 3), and `0.0` if all advisors share the same mean CPI (zero variance).

### Interpretation

| Skewness value | Meaning |
|----------------|---------|
| **≈ 0** | Symmetric distribution of mean CPIs — no systematic concentration of high or low-CPI students at particular advisors |
| **> 0** (positive skew) | A few advisors have notably higher mean CPIs than the bulk — a right-tailed distribution of advisor quality; some advisors are receiving a disproportionately high-CPI cohort |
| **< 0** (negative skew) | A few advisors have notably lower mean CPIs than the bulk — a left-tailed distribution; some advisors are receiving a disproportionately low-CPI cohort |

A small absolute skewness (|γ| < 0.5) generally indicates an acceptably symmetric distribution. Values in the range 0.5–1.0 suggest moderate concentration; values above 1.0 warrant investigation.

### Why skewness rather than variance?

Variance measures spread but not direction. A high-variance distribution of advisor mean CPIs could arise either from a few outlier advisors at the top (unfair to other advisors and to lower-CPI students) or at the bottom (low-CPI students concentrated at less-preferred advisors). Skewness distinguishes between these two patterns and is therefore more informative for diagnosing systemic bias.

---

## Reporting and Display

Both metrics are computed by `metrics.compute_advisor_metrics()` and exposed in the Dash interface under the **Statistics** tab of the replay panel after the allocation completes. The per-faculty breakdown is also available:

| Output | Where to find it |
|--------|-----------------|
| Average normalised entropy | Statistics panel → "Avg CPI entropy" |
| Per-advisor normalised entropy | Returned in `metrics["advisor"]["per_faculty"]` |
| CPI skewness (system level) | Statistics panel → "CPI skewness" |
| Per-advisor mean CPI | Returned in `metrics["advisor"]["per_faculty"]` |

---

## Relationship to Policy Choice

The two advisor metrics respond differently to the allocation policies:

| Metric | `least_loaded` | `cpi_fill` |
|--------|----------------|------------|
| **Avg entropy** | Generally higher — load-balancing spreads diverse-tier students across advisors | Can be lower — CPI-ordered processing tends to cluster high-CPI students at popular advisors |
| **CPI skewness** | Typically near 0 or moderate positive | Can exhibit higher positive skew — top advisors accumulate high-CPI cohorts |

See `stats/policy_report.md` for empirical values across five datasets.

---

## Notes

- **Advisors with a single student** will always have H_norm = 0 (a single student belongs to exactly one tier, yielding zero entropy). This is mathematically correct but should be interpreted cautiously: a single-student advisor is maximally "specialised" by definition, not necessarily by policy.
- **Tiny cohort mode** (`S < 10`): all students are assigned to Class A, so K = 1 and H_norm = 0 for all advisors by construction. The entropy metric is not meaningful in this mode.
- **Quartile vs percentile mode**: the value of K (3 vs 4) is detected automatically from the student tier labels. Comparing entropy values between a percentile-mode run and a quartile-mode run requires care because the denominators differ.
