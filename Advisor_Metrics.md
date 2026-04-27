# Advisor Metrics

Two dimensions of advisor-side evaluation are tracked after each allocation: **satisfaction** (how well students and advisors are matched from the advisor's viewpoint) and **equity** (how fairly the student population is distributed across faculty).

---

## Advisor Satisfaction Metrics

### MSES — Mean Student Enthusiasm Score

#### Definition

For each advisor *a*, compute the mean preference rank at which their assigned students listed them:

$$
\text{MSES}(a) = \frac{1}{n_a} \sum_{i \in \mathcal{S}_a} \text{rank}(a, i)
$$

where `rank(a, i)` is the 1-based position of advisor *a* in student *i*'s preference list, and `S_a` is the set of students assigned to *a*.

The system-level score is the mean MSES across all assigned advisors:

$$
\overline{\text{MSES}} = \frac{1}{|\mathcal{A}|} \sum_{a \in \mathcal{A}} \text{MSES}(a)
$$

#### Interpretation

| Avg MSES | Meaning |
|----------|---------|
| **≤ 2.0** | Students assigned to each advisor predominantly listed that advisor as their 1st or 2nd choice — high mutual enthusiasm |
| **≤ 4.0** | Good match — students are within their top few choices |
| **> 4.0** | Students are being assigned to advisors they ranked lower — worth reviewing capacity or preference diversity |

Lower is better. A value of 1.0 means every student was assigned to their top choice.

#### Why MSES?

The protocol does not collect explicit advisor preferences over students. MSES uses the student preference list as a bilateral signal: a student who ranked an advisor highly sought out that person, making a high-enthusiasm match more likely to be mutually satisfying. It is the most informative proxy for advisor satisfaction available without additional data collection.

---

### LUR — Load Utilization Rate

#### Definition

For each advisor *a*:

$$
\text{LUR}(a) = \frac{\text{actual\_load}(a)}{\text{max\_load}(a)}
$$

The system-level score is the mean LUR across all assigned advisors:

$$
\overline{\text{LUR}} = \frac{1}{|\mathcal{A}|} \sum_{a \in \mathcal{A}} \text{LUR}(a)
$$

Reported as a percentage. A value of 100% means every advisor is at full capacity.

#### Interpretation

`max_load` represents the advisor's stated willingness to supervise. An advisor significantly below their max is underutilized; one at 100% is fully committed. The protocol enforces load balance (loads differ by at most 1), so LUR variation is mainly driven by heterogeneous `max_load` settings.

Per-advisor LUR is displayed in the **Tier Heatmap** y-axis labels; the metrics panel reports the system-level average.

---

## Advisor Equity Metrics

### Load-Aware Entropy Ceiling and Equity Retention Rate

#### Motivation

Any allocation faces two constraints on advisor tier diversity: the cohort's tier distribution, and the number of students each advisor actually receives. An advisor with only 3 students can span at most 3 distinct tiers regardless of the cohort composition — they cannot simultaneously represent all 4 tiers in quartile mode. The load-aware ceiling captures both constraints; the Equity Retention Rate measures what fraction of that ceiling the protocol preserved.

#### Load-Aware Entropy Ceiling

The maximum normalized entropy an advisor with *n* students can achieve is:

$$
H_{\text{max}}(n) = \frac{\log \min(n,\, K)}{\log K}
$$

since *n* students can span at most *min(n, K)* distinct tiers. Under the protocol's load balance guarantee, advisors receive either $\lfloor S/F \rfloor$ or $\lceil S/F \rceil$ students. The system-level ceiling is the weighted average:

$$
\boxed{H_{\text{baseline}} = \frac{(F - r)\cdot H_{\text{max}}(\lfloor S/F \rfloor)\;+\; r\cdot H_{\text{max}}(\lceil S/F \rceil)}{F}}
$$

where *S* is the number of students, *F* the **total** number of advisors (including any empty labs), and *r = S mod F*. Using the total faculty count ensures the ceiling is computed consistently across all policies — advisors who receive no students contribute 0 to the numerator but are counted in the denominator.

This ceiling is 1.0 only when $\lfloor S/F \rfloor \geq K$ — when each advisor receives enough students to potentially cover every tier. When loads are smaller than *K* (common in moderate-sized cohorts), the ceiling is below 1.0, reflecting the structural impossibility of perfect mixing.

#### Per-Advisor Entropy

For each advisor *a*, the normalized Shannon entropy of their assigned students' tier distribution:

$$
H_{\text{norm}}(a) = \frac{-\sum_{k=1}^{K} p_k(a) \log p_k(a)}{\log K}
$$

The system-level **average normalized entropy** `H̄_norm` is the mean across all assigned advisors.

#### Equity Retention Rate

$$
\boxed{\text{Equity Retention Rate} = \frac{\overline{H}_{\text{norm}}}{H_{\text{baseline}}} \times 100\%}
$$

This is the fraction of achievable equity the policy actually preserved, expressed as a percentage. It is cohort-scale-independent and protocol-attributable: two runs on different cohorts with the same ERR are directly comparable.

| ERR | Meaning |
|-----|---------|
| **≥ 80%** | The policy preserved most of the cohort's achievable equity |
| **60–80%** | Moderate equity preservation; some tier concentration introduced by the policy |
| **< 60%** | Significant tier concentration — the policy is distributing students much less evenly than the cohort structure would allow |

Both the baseline entropy (the cohort constraint) and the ERR (the protocol score) are reported together so that a high ERR on a low-ceiling cohort can be interpreted correctly.

---

### CPI Skewness

#### Definition

For each advisor *a*, compute the mean CPI of their assigned students:

$$
\bar{x}_a = \frac{1}{n_a} \sum_{i \in \mathcal{S}_a} \text{CPI}_i
$$

Collect the vector of advisor mean CPIs across all *A* assigned advisors and compute the **Fisher-Pearson sample skewness**:

$$
\boxed{\gamma = \frac{A}{(A-1)(A-2)} \sum_{a=1}^{A} \left(\frac{\bar{x}_a - \bar{\bar{x}}}{s}\right)^3}
$$

where `x̄̄` is the mean and `s` is the sample standard deviation of the advisor mean CPIs. The division by `s` inside the cube normalizes for the spread of the cohort's CPI distribution, making this metric scale-invariant and cohort-scale-independent.

Returns `None` if fewer than 3 advisors have students (undefined for *A* < 3), and `0.0` if all advisor mean CPIs are identical.

#### Interpretation

| Skewness | Meaning |
|----------|---------|
| **≈ 0** | Symmetric distribution — no systematic CPI concentration at any advisors |
| **> 0** | A few advisors have notably higher mean CPIs — high-CPI students are clustering at popular advisors |
| **< 0** | A few advisors have notably lower mean CPIs — low-CPI students are systematically concentrated |

`|γ| < 0.5` is acceptable; `|γ| > 1.0` warrants investigation.

---

## Reporting

All metrics are computed by `metrics.compute_advisor_metrics()` and displayed in the **Metrics** panel after allocation finalization (Allocation Area → Metrics collapse → Advisor Metrics section), split into Satisfaction and Equity sub-sections. They also appear in the Analysis page for side-by-side policy comparison.

Per-advisor detail is available in `metrics["advisor"]["per_faculty"]`:

| Field | Description |
|-------|-------------|
| `mses` | Mean rank at which this advisor's students listed them |
| `lur` | `actual_load / max_load` |
| `entropy` | Normalized CPI entropy for this advisor's cohort |
| `mean_cpi` | Mean CPI of assigned students |
| `student_count` | Number of students assigned |

---

## Notes

- **Single-student advisors** always have `H_norm = 0` (one student, one tier, zero entropy). This is mathematically correct; interpret with that context.
- **Tiny cohort mode** (`S < 10`): all students are Class A, so `K = 1` and entropy is identically 0. Entropy metrics are not meaningful in this mode.
- **Quartile vs percentile mode**: `K` is detected automatically from student tier labels (3 in percentile mode, 4 in quartile mode). Baseline entropy values are not directly comparable across modes.
