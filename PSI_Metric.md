# Preference Satisfaction Index (PSI)

A secondary, policy-agnostic metric for evaluating the overall quality of an MS thesis advisor allocation from the perspective of raw student preference satisfaction.

---

## Motivation

The NPSS (Normalized Preference Satisfaction Score) is the primary metric and is deliberately designed to be CPI-weighted and tier-aware: it applies the protection-window constraint and assigns more weight to high-CPI students, in direct alignment with the protocol's design intent.

However, this means NPSS can obscure certain effects:

- A run where every Class C student lands far down their list but every Class A student gets their 1st choice will still score high on NPSS.
- Two policies that differ only in how they treat low-CPI students may look identical on NPSS.

The PSI provides a complementary view that is **equal-weighted** and **window-free** — it treats every student identically and asks simply: *on average, how close to the top of their list did each student land?*

---

## Definition

### Step 1 — Per-student PSI score

For each student *i*, let:

- `p_i` = the 1-based rank of the advisor they were assigned to within their own preference list (1 = 1st choice, 2 = 2nd choice, …)
- `F` = total number of faculty (i.e., the length of every student's complete preference list)

Compute:

$$
\text{PSI}_i = 1 - \frac{p_i - 1}{F - 1}
$$

This maps outcomes linearly onto `[0, 1]`:

| Outcome | PSI score |
|---------|-----------|
| Assigned to 1st choice (`p = 1`) | 1.0 |
| Assigned to last faculty (`p = F`) | 0.0 |
| Unassigned | 0.0 |

The denominator `F − 1` normalises the rank so that PSI is comparable across cohorts with different numbers of faculty.

### Step 2 — Equal-weighted aggregate

All students receive the same weight regardless of CPI or tier:

$$
\boxed{\text{mean PSI} = \frac{1}{S} \sum_{i=1}^{S} \text{PSI}_i}
$$

Mean PSI lies in `[0, 1]`. A score of **1.0** means every student was assigned their 1st choice. A score of **0.5** means students landed, on average, at the midpoint of their list.

---

## Key Differences from NPSS

| Aspect | NPSS | PSI |
|--------|------|-----|
| Student weights | CPI-proportional (`CPI_i / ΣCPIs`) | Equal (`1/S`) |
| Preference window | Enforced — score is 0 outside `N_tier` | Not enforced — every rank is scored |
| Tier awareness | Tier matters (window size differs by tier) | Tier-agnostic |
| Best suited for | Checking protocol compliance and merit-weighted quality | Comparing raw preference satisfaction across policies and cohorts |

---

## Complementary Breakdown

Report these alongside the aggregate mean PSI:

| Breakdown metric | What it reveals |
|-----------------|-----------------|
| **Mean PSI per tier** | Whether a particular tier is systematically landing further down their lists — the equal weighting can reveal tier-based disparities that NPSS's CPI weighting hides |
| **Mean preference rank per tier** | The raw average of `p_i` within each tier, interpretable without any normalisation |
| **PSI standard deviation** | Spread of individual PSI scores — high variance indicates that some students received excellent matches while others were placed far from their preferences |

---

## Interpretation Guide

| Mean PSI range | Interpretation |
|----------------|----------------|
| 0.90 – 1.00 | Excellent — on average, students are landing very near their 1st or 2nd choice |
| 0.75 – 0.89 | Good — typical outcome; most students are in their top quarter of preferences |
| 0.60 – 0.74 | Moderate — noticeable preference compromise across the cohort on average |
| < 0.60 | Poor — students are, on average, landing in the lower half of their list |

---

## Relationship to NPSS in Practice

In most well-functioning runs, NPSS and mean PSI move together. Divergence between them is informative:

- **NPSS high, PSI lower than expected** — top-CPI students are being well served (their strong weights pull NPSS up) but lower-CPI students are landing further down their lists. Check the per-tier PSI breakdown.
- **PSI high, NPSS lower** — the cohort on average lands near its top preferences, but some high-CPI students fell outside their protection window, penalising NPSS. Check the overflow count and per-tier NPSS scores.
- **Both high** — the allocation is working well across all dimensions.
- **Both low** — systematic preference mismatch; investigate capacity parameters and the distribution of student preferences.

---

## Notes

- **Why not just use mean rank?** Mean rank is interpretable but scales with `F`: a mean rank of 4 means something different in a 10-faculty cohort versus a 31-faculty cohort. PSI normalises by `F − 1` so comparisons are valid across cohorts and datasets.
- **Unassigned students** receive PSI = 0, which correctly penalises incomplete allocations.
- **Policy comparison**: PSI is particularly useful when comparing the `least_loaded` and `cpi_fill` policies. Because `cpi_fill` processes students in CPI order, it tends to boost NPSS (high-CPI students claim top picks) but can reduce mean PSI (lower-CPI students are pushed further). PSI makes this trade-off visible.
