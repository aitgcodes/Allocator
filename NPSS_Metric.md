# Normalized Preference Satisfaction Score (NPSS)

A metric for evaluating how well the MS thesis guide allocation matches the protocol's core goals.

---

## Motivation

The allocation protocol pursues three core goals:

1. **Preference protection** — students should land as close to the top of their list as possible.
2. **Load balance** — faculty loads should differ by at most 1.
3. **Full assignment** — no student is left unassigned; no faculty gets zero students.

Goals 2 and 3 are hard constraints enforced by the algorithm itself. The meaningful question for evaluation is: *how well does the system honour student preferences, and does it do so fairly across CPI tiers?* NPSS is designed to answer exactly this.

---

## Definition

### Step 1 — Per-student preference score

For each student *i*, let:

- `p_i` = the rank of the advisor they were assigned to (1 = 1st choice, 2 = 2nd choice, …)
- `F` = total number of faculty (= length of every student's full preference list)

Compute:

$$
\text{score}_i = \frac{F - p_i + 1}{F}
$$

This maps each student's outcome linearly onto `(0, 1]`:

| Outcome | Score |
|---|---|
| Assigned to 1st choice | 1.0 |
| Assigned to rank *k* | (F − k + 1) / F |
| Assigned to last choice (rank F) | 1 / F ≈ 0 |

Using the **full preference list length F** as the denominator is a deliberate design choice: it makes NPSS scores comparable across all four allocation policies, including `cpi_fill` and `tiered_rounds` which do not enforce tier-based preference windows during assignment. Every student is evaluated on the same scale regardless of tier.

### Step 2 — CPI-weighted aggregate

Weight each student's score by their CPI, reflecting the protocol's philosophy that higher-performing students should receive stronger preference satisfaction:

$$
w_i = \frac{\text{CPI}_i}{\displaystyle\sum_{j=1}^{S} \text{CPI}_j}
$$

$$
\boxed{\text{NPSS} = \sum_{i=1}^{S} w_i \cdot \text{score}_i}
$$

NPSS lies in `(0, 1]` for a fully assigned cohort (approaching 0 only when every student lands at or near their last choice). A score of **1.0** means every student received their 1st choice.

---

## Complementary Breakdown

The following statistics are reported alongside NPSS. They use the **tier window** (`N_tier`) as a diagnostic threshold — independently of the NPSS score — to pinpoint where preference protection is being traded away:

| Breakdown metric | Definition | What it reveals |
|---|---|---|
| **Within-window rate per tier** | Fraction of students in each tier placed at rank ≤ `N_tier` | Whether the tier protection windows are being honoured per tier |
| **Mean preference rank per tier** | Mean `p_i` within each tier | Whether one tier is systematically landing lower than another |
| **Overflow count** | Number of students with rank > `N_tier` | Placements beyond the tier-specific protection window — a diagnostic of how often the policy exceeds the window |

> **Note:** The overflow count is a **diagnostic**, not an NPSS input. Because NPSS now uses `F` as the denominator, out-of-window placements still receive a positive NPSS score proportional to their rank. The overflow count tells you *whether* placements exceed the tier window; NPSS tells you *how well* students were served overall.

---

## Interpretation Guide

With the full-list denominator, typical NPSS values in well-functioning allocations (with F ≈ 30 faculty) are higher than under the old tier-window formula, since no assignment is clipped to zero:

| NPSS range | Interpretation |
|---|---|
| 0.95 – 1.00 | Excellent — cohort is landing predominantly at ranks 1–2 |
| 0.85 – 0.94 | Good — most students land in their top 5; some further |
| 0.70 – 0.84 | Moderate — noticeable preference compromise; check per-tier breakdown |
| < 0.70 | Poor — systematic mismatch; review capacity parameters or preference diversity |

*Thresholds are cohort-size-sensitive.* For small F (e.g. F = 8), the score for a student at rank 4 is (8−4+1)/8 = 0.625, which is lower than for the same rank in a large cohort. Compare across runs with the same F.

---

## Notes

- **Why CPI weighting?** The protocol explicitly grants Class A students stronger preference protection. Weighting by CPI ensures that failures to honour top-tier preferences penalise the score more than equivalent failures for lower-CPI students, consistent with the protocol's design intent.

- **Why full list F, not N_tier?** Allocation policies differ in whether they enforce the tier cap during assignment. Using N_tier as the NPSS denominator would silently penalise policies that legitimately place students beyond the window (e.g. `cpi_fill`, `tiered_rounds`) while giving an inflated zero-cliff advantage to cap-enforcing policies. Using F creates a level playing field for cross-policy comparison. The overflow count is preserved as a separate diagnostic for cap compliance.

- **PSI vs NPSS:** PSI (`1 − (rank−1)/(F−1)`) uses a linear normalisation that maps rank 1 → 1.0 and rank F → 0.0, with equal weight for all students. NPSS uses `(F−rank+1)/F` with CPI weighting. The two are closely related but not identical: NPSS emphasises high-CPI students' outcomes; PSI weights all students equally. Use them together for a full picture.
