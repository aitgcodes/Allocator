# Normalized Preference Satisfaction Score (NPSS)

A metric for evaluating how well the MS thesis guide allocation matches the protocol's core goals.

---

## Motivation

The allocation protocol pursues three core goals:

1. **Preference protection** — students should land within their `1 → N_tier` window whenever possible.
2. **Load balance** — faculty loads should differ by at most 1.
3. **Full assignment** — no student is left unassigned; no faculty gets zero students.

Goals 2 and 3 are hard constraints enforced by the algorithm itself. The meaningful question for evaluation is therefore: *how well does the system honor student preferences, and does it do so fairly across tiers?* The NPSS is designed to answer exactly this.

---

## Definition

### Step 1 — Per-student preference score

For each student *i*, let:

- `p_i` = the rank of the advisor they were actually assigned to (1 = 1st choice, 2 = 2nd choice, …)
- `N_tier_i` = the preference-protection window for student *i*'s tier (3 for Class A, 5 for Class B, `F` for Class C; or scaled values if `S/F > 4`)

Compute:

$$
\text{score}_i =
\begin{cases}
\dfrac{N_{\text{tier},i} - p_i + 1}{N_{\text{tier},i}} & \text{if assigned within the } 1 \to N_{\text{tier}} \text{ window} \\[10pt]
0 & \text{if assigned outside the window (overflow case)}
\end{cases}
$$

This maps each student's outcome onto `[0, 1]`:

| Outcome | Score |
|---|---|
| Assigned to 1st choice | 1.0 |
| Assigned to last protected choice | `1 / N_tier` |
| Assigned outside protection window | 0.0 |

Normalizing by `N_tier_i` makes scores comparable across tiers — a Class A student assigned at rank 3 (their last protected choice) scores the same as a Class B student assigned at rank 5.

### Step 2 — CPI-weighted aggregate

Weight each student's score by their CPI, reflecting the protocol's philosophy that higher-performing students receive stronger protection:

$$
w_i = \frac{\text{CPI}_i}{\displaystyle\sum_{j=1}^{S} \text{CPI}_j}
$$

$$
\boxed{\text{NPSS} = \sum_{i=1}^{S} w_i \cdot \text{score}_i}
$$

NPSS lies in `[0, 1]`. A score of **1.0** means every student was assigned their 1st choice. A score of **0** means every student fell outside their protection window.

---

## Complementary Breakdown

Report these alongside the aggregate NPSS to pinpoint *where* preference satisfaction is being traded away:

| Breakdown metric | What it reveals |
|---|---|
| **Within-window rate per tier** | Fraction of Class A / B / C students who landed inside their `N_tier` window — shows whether the protocol's guarantees are holding per tier |
| **Mean preference rank per tier** | Raw average of `p_i` within each tier — flags if one tier is systematically landing at rank 2–3 versus rank 1 |
| **Overflow count** | Number of students assigned outside their protection window — should be 0 in a well-functioning run |

---

## Interpretation Guide

| NPSS range | Interpretation |
|---|---|
| 0.90 – 1.00 | Excellent — most students are at or near their 1st choice |
| 0.75 – 0.89 | Good — some preference compromise, likely due to popular advisors filling up |
| 0.60 – 0.74 | Moderate — meaningful preference loss; check per-tier breakdown for the source |
| < 0.60 | Poor — systematic mismatch; review capacity parameters or student preference diversity |

---

## Notes

- **Why CPI weighting?** The protocol explicitly grants Class A students a narrower but more strongly protected window. Weighting by CPI ensures that failures to honor top-tier preferences penalize the score more than equivalent failures for lower-tier students, consistent with the protocol's design intent.
- **Class C students** with `N_tier = All` (i.e., the entire faculty list) will almost always score > 0 unless the full assignment step itself fails. Their scores therefore mainly reflect how early in their list they landed, which is still meaningful.
- **Small cohorts** (`S < 10`): when all students are treated as Class A with `N_tier = 2`, interpret NPSS relative to this narrower window — a score of 0.5 then corresponds to everyone landing at their 2nd choice.
