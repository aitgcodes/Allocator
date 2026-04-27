# Advisor Metrics

Advisor-side evaluation covers three dimensions: **satisfaction** (how well students were matched to advisors they genuinely sought), **load distribution equity** (whether students were spread fairly across advisors), and **tier mixing equity** (whether each advisor received a diverse cross-section of the CPI spectrum).

---

## Advisor Satisfaction Metrics

### MSES — Mean Student Enthusiasm Score

#### Definition

For each advisor *a*, compute the mean preference rank at which their assigned students listed them:

$$
\text{MSES}(a) = \frac{1}{n_a} \sum_{i \in \mathcal{S}_a} \text{rank}(a, i)
$$

where `rank(a, i)` is the 1-based position of advisor *a* in student *i*'s preference list, and $\mathcal{S}_a$ is the set of students assigned to *a*.

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

Reported as a percentage. A value of 100 % means every advisor is at full capacity.

#### Interpretation

LUR is a **capacity utilisation signal**, not an equity metric. It answers "how fully are allocated seats being used?" — not "how evenly are students distributed?". Two allocations with very different load spreads can have identical Avg LUR. For load equity, use the Load Distribution metrics below.

`max_load` represents the advisor's stated willingness to supervise. Per-advisor LUR is displayed in the **Tier Heatmap** y-axis labels; the metrics panel reports the system-level average.

---

## Advisor Equity — Load Distribution

These metrics measure whether students were spread fairly across advisors.

### Empty Labs

The count of advisors who received no students. Surfaced as a badge in the metrics panel.

| Empty Labs | Meaning |
|------------|---------|
| **0** | All advisors received at least one student |
| **> 0** | Some advisors were entirely bypassed — worth reviewing whether this was intentional (e.g. an advisor on leave) or a structural consequence of the policy |

### Load Balance

`max(advisor loads) − min(advisor loads)` across **all** advisors including empty labs (which contribute 0). A value of 0 means identical loads; 1 is the minimum non-zero spread and is typical in well-balanced runs. Values ≥ 2 indicate significant imbalance.

---

## Advisor Equity — Tier Mixing

These metrics measure whether each advisor received a diverse cross-section of CPI tiers, not just students from one end of the academic spectrum.

### Per-Advisor Entropy — $H_{\text{norm}}$

#### Definition

For each advisor *a* with $n_a$ assigned students, bucket those students into CPI tiers and compute the **normalized Shannon entropy** of the resulting distribution:

$$
\boxed{H_{\text{norm}}(a) = \frac{-\displaystyle\sum_{k=1}^{K} p_k(a)\,\log p_k(a)}{\log K}}
$$

where:

- $K$ = number of CPI tiers: **3** in percentile mode (A, B, C) or **4** in quartile mode (A, B1, B2, C), detected automatically from student tier labels
- $p_k(a) = n_{a,k} / n_a$ is the fraction of advisor *a*'s students in tier *k*
- $0 \cdot \log 0 \equiv 0$ by convention

$H_{\text{norm}}(a) \in [0, 1]$: it equals **0** when all of *a*'s students are in the same tier, and **1** when students are perfectly uniformly distributed across all *K* tiers.

The system-level average sums over **all** *F* faculty (empty labs contribute $H_{\text{norm}} = 0$):

$$
\overline{H}_{\text{norm}} = \frac{1}{F} \sum_{a=1}^{F} H_{\text{norm}}(a)
$$

---

### Load-Aware Entropy Ceiling — $H_{\text{max}}$ and $H_{\text{baseline}}$

#### Per-advisor ceiling

An advisor with $n$ students can represent at most $\min(n, K)$ distinct tiers simultaneously. The tightest upper bound on $H_{\text{norm}}(a)$ is therefore:

$$
\boxed{H_{\text{max}}(n) = \frac{\log \min(n,\, K)}{\log K}}
$$

This equals 0 when $n = 1$ (a single student occupies exactly one tier; no diversity is possible), and approaches 1 as $n \geq K$ (enough students to fill every tier uniformly).

#### System-level ceiling

The system-level baseline averages $H_{\text{max}}$ over all *F* advisors using their **actual assigned loads** (empty labs contribute 0):

$$
\boxed{H_{\text{baseline}} = \frac{1}{F} \sum_{a=1}^{F} H_{\text{max}}\!\left(\text{actual\_load}(a)\right)}
$$

Because $H_{\text{norm}}(a) \leq H_{\text{max}}(\text{actual\_load}(a))$ holds for every advisor by construction, we have $\overline{H}_{\text{norm}} \leq H_{\text{baseline}}$ always, guaranteeing the Equity Retention Rate lies in $[0\,\%, 100\,\%]$.

The ceiling is 1.0 only when every advisor receives at least *K* students; in moderate-sized cohorts with low loads per advisor, the ceiling is structurally below 1.0 regardless of the policy.

---

### Equity Retention Rate — ERR

$$
\boxed{\text{ERR} = \frac{\overline{H}_{\text{norm}}}{H_{\text{baseline}}} \times 100\,\%}
$$

ERR answers: *"Given how this policy distributed students across advisors, what fraction of the maximum possible tier mixing was actually achieved?"*

Because $H_{\text{baseline}}$ reflects the **actual load distribution** produced by the policy, ERR is specific to each run. Read it alongside the Load Distribution metrics: a high ERR under a low ceiling (few students per advisor, many empty labs) tells a different story from a high ERR under a high ceiling.

| ERR | Meaning |
|-----|---------|
| **≥ 80 %** | The policy used most of the tier-mixing headroom available given its load distribution |
| **60–80 %** | Moderate mixing; some tier concentration within advisors |
| **< 60 %** | Significant tier concentration — advisors are receiving students predominantly from one part of the CPI spectrum |

---

### CPI Skewness *(diagnostic)*

#### Definition

For each advisor *a*, compute the mean CPI of their assigned students:

$$
\bar{x}_a = \frac{1}{n_a} \sum_{i \in \mathcal{S}_a} \text{CPI}_i
$$

Collect the vector of advisor mean CPIs across all *A* assigned advisors and compute the **Fisher-Pearson sample skewness**:

$$
\boxed{\gamma = \frac{A}{(A-1)(A-2)} \sum_{a=1}^{A} \left(\frac{\bar{x}_a - \bar{\bar{x}}}{s}\right)^3}
$$

where $\bar{\bar{x}}$ is the grand mean and $s$ is the sample standard deviation of the advisor mean CPIs. Normalizing by $s$ makes this scale-invariant and cohort-scale-independent.

Returns `None` if fewer than 3 advisors have students (undefined for $A < 3$), and `0.0` if all advisor mean CPIs are identical.

#### Interpretation

| Skewness | Meaning |
|----------|---------|
| **≈ 0** | Symmetric distribution — no systematic CPI concentration at any advisors |
| **> 0** | A few advisors have notably higher mean CPIs — high-CPI students are clustering at popular advisors |
| **< 0** | A few advisors have notably lower mean CPIs — low-CPI students are systematically concentrated |

`|γ| < 0.5` is acceptable; `|γ| > 1.0` warrants investigation. CPI Skewness is a **diagnostic cross-check** — use it alongside ERR, not as a standalone equity verdict.

---

## Reporting

All metrics are computed by `metrics.compute_advisor_metrics()` and displayed in the **Metrics** panel after allocation finalization, grouped as:

- **Advisor Satisfaction** — MSES, LUR
- **Advisor Equity — Load Distribution** — Empty Labs, Load Balance, Advisors Assigned
- **Advisor Equity — Tier Mixing** — Entropy Ceiling, ERR, CPI Skewness

They also appear in the Analysis page for side-by-side policy comparison.

Per-advisor detail is available in `metrics["advisor"]["per_faculty"]`:

| Field | Description |
|-------|-------------|
| `mses` | Mean rank at which this advisor's students listed them |
| `lur` | `actual_load / max_load` |
| `entropy` | $H_{\text{norm}}(a)$ — normalized CPI entropy for this advisor's cohort |
| `mean_cpi` | Mean CPI of assigned students |
| `student_count` | Number of students assigned |

---

## Notes

- **Single-student advisors** always have $H_{\text{norm}} = 0$ (one student, one tier, zero entropy), and $H_{\text{max}} = 0$ as well — they contribute 0 to both numerator and denominator of ERR. This is mathematically correct; interpret with that context.
- **Tiny cohort mode** (`S < 10`): all students are Class A, so $K = 1$ and entropy is identically 0. Tier mixing metrics are not meaningful in this mode.
- **Quartile vs percentile mode**: $K$ is detected automatically from student tier labels (3 in percentile mode, 4 in quartile mode). Baseline entropy values are not directly comparable across modes.
