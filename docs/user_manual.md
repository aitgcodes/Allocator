# MS Thesis Advisor Allocation — User Manual

---

## 1. Installation

### 1.1 Prerequisites

Two tools must be installed before you begin.

| Tool | Mac | Linux | Windows |
|------|-----|-------|---------|
| **Git** | `brew install git` or [git-scm.com](https://git-scm.com) | `sudo apt install git` / `sudo dnf install git` | [git-scm.com](https://git-scm.com) — install with default options |
| **Conda** | [Miniconda](https://docs.conda.io/en/latest/miniconda.html) (recommended) | Same | Same — use **Anaconda Prompt** for all commands below |

> **Windows users:** run every command in this manual from **Anaconda Prompt**, not the default Command Prompt.

---

### 1.2 Step 1 — Clone the repository

**Mac / Linux:**
```bash
git clone https://github.com/aitgcodes/Allocator.git
cd Allocator
```

**Windows:**
```bat
git clone https://github.com/aitgcodes/Allocator.git
cd Allocator
```

---

### 1.3 Step 2 — Create the Conda environment

This installs Python 3.11 and all required packages into an isolated environment named `allocator`. It only needs to be done once.

```bash
conda env create -f environment.yml
```

> This may take a few minutes on the first run.

---

### 1.4 Step 3 — Activate the environment

**Mac / Linux:**
```bash
conda activate allocator
```

**Windows:**
```bat
conda activate allocator
```

Your prompt will change to show `(allocator)` on the left, confirming the environment is active.

---

### 1.5 Step 4 — Launch the app

**Mac / Linux:**
```bash
PYTHONPATH=src python -m allocator.app
```

**Windows:**
```bat
set PYTHONPATH=src && python -m allocator.app
```

You should see:
```
Dash is running on http://127.0.0.1:8050/
```

Open **http://localhost:8050** in Chrome, Firefox, or Edge. Keep the terminal open while using the app — closing it stops the server.

---

### 1.6 Stopping and restarting

Press **`Ctrl+C`** in the terminal to stop the app.

To restart later, the environment is already installed — only steps 3 and 4 are needed:

**Mac / Linux:**
```bash
cd Allocator
conda activate allocator
PYTHONPATH=src python -m allocator.app
```

**Windows:**
```bat
cd Allocator
conda activate allocator
set PYTHONPATH=src && python -m allocator.app
```

---

### 1.7 Troubleshooting installation

| Symptom | Fix |
|---------|-----|
| `conda: command not found` | Miniconda/Anaconda is not installed or not on PATH — reinstall and restart your terminal |
| `ModuleNotFoundError: No module named 'allocator'` | `PYTHONPATH=src` was not set — re-run the launch command exactly as shown |
| Browser shows "This site can't be reached" | The app is not running — check the terminal for errors and ensure Step 4 completed successfully |
| Port 8050 already in use | Another instance is running; stop it with `Ctrl+C`, or run `lsof -i :8050` (Mac/Linux) to find and kill it |
| `CondaEnvException: prefix already exists` | Environment already created — skip Step 2 and go straight to Step 3 |

---

## 2. Usage Guide

### 2.1 Preparing input files

The app requires two CSV files: one for students and one for faculty.

#### Option A — Convert a Google Form export

If students submitted preferences via Google Forms (or a compatible export), the bundled script produces both files automatically:

```bash
python scripts/make_preference_sheet.py form_responses.csv
```

This generates:

| Output file | Contents |
|-------------|----------|
| `preference_sheet.csv` | One row per student — `student_id`, `name`, `cpi`, `pref_1 … pref_N` |
| `faculty_list.csv` | One row per faculty — `faculty_id`, `name`, `max_load` (blank; fill in manually) |

The script handles flexible column naming, deduplicates repeated preferences, and fills trailing slots alphabetically so every student's list covers all faculty.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `-o / --output` | `preference_sheet.csv` | Student output path |
| `-f / --faculty-output` | `faculty_list.csv` | Faculty output path |
| `--cpi-col COLUMN` | auto-detect | Override CPI column name if auto-detection fails |

#### Option B — Create files manually

**students.csv**

| Column | Description |
|--------|-------------|
| `student_id` | Unique identifier |
| `name` | Full name |
| `cpi` | Cumulative Performance Index (numeric) |
| `pref_1`, `pref_2`, … | Faculty IDs in preference order |

**faculty.csv**

| Column | Description |
|--------|-------------|
| `faculty_id` | Unique ID (must match values used in student preference columns) |
| `name` | Full name |
| `max_load` | *(optional)* Maximum students this advisor can take; leave blank to use the formula value `floor(S/F) + 1` |

Sample files are provided in `data/` (`sample_students.csv`, `sample_faculty.csv`).

---

### 2.2 Running an allocation

#### Step 1 — Open the app

Navigate to **http://localhost:8050**. The landing page displays a brief overview and lets you select an allocation policy before proceeding.

#### Step 2 — Select a policy

Choose one of the two main policies on the landing page:

- **Least Loaded (`least_loaded`)** — the default; prioritises balanced advisor loads.
- **CPI Fill (`cpi_fill`)** — merit-first; processes students in strict descending CPI order.

A full discussion of both policies is in Section 3.

#### Step 3 — Load input files

Use the file upload controls on the main page to upload your `students.csv` and `faculty.csv`. The app validates both files and reports any errors (missing columns, mismatched faculty IDs, etc.) before proceeding.

#### Step 4 — Run Phase 0

Click **Run Phase 0**. The app tiers all students by CPI percentile and computes faculty `max_load` values. A Phase-0 report is shown summarising tier assignments and load parameters.

#### Step 5 — Run the full allocation

Click **Run Allocation**. The app executes the selected policy and populates the replay panel with all allocation steps.

---

### 2.3 The allocation replay panel

After the allocation runs, the replay panel at the bottom of the page shows five tabs, all linked to the **step slider**. Drag the slider or click **Play** to step through every assignment decision.

| Tab | What it shows |
|-----|---------------|
| **Assignment Graph** | Bipartite graph: students (left, sorted by CPI) connected to their assigned advisor (right). The most recently assigned edge is highlighted in purple. |
| **Advisor Loads** | Horizontal bar chart of current student count per advisor. Bars are coloured green / yellow / red by utilisation; the advisor just assigned is highlighted. A dashed red line marks `max_load`. |
| **Statistics** | Per-tier assignment counts and percentages, plus faculty load statistics (min, max, mean). |
| **Step Log** | Table of every allocation event up to the current step — step number, phase, and a one-line description of the assignment made. |
| **CPI Distribution** | Histogram of advisor-averaged CPIs (mean CPI of each advisor's assigned students). Advisors with no students yet appear in the 0 bin. The distribution shifts and spreads as the allocation progresses. |
| **Tier Heatmap** | Advisor × CPI-tier heatmap showing row-normalized proportions. Rows are sorted by entropy ascending (most segregated advisors first). Diagnostic view for advisor equity — use together with Avg CPI Entropy. Broad color across a row = mixed-tier cohort; concentration in one column = tier segregation. |

---

### 2.4 Exporting results

Once the allocation is complete:

- **CSV report** — click **Save report** to download a CSV containing every student's assignment, preference rank, tier, and advisor load.
- **HTML snapshot** — click **Export HTML** to save a self-contained HTML file of the current visualisation state.

---

### 2.5 CLI usage (no GUI)

For scripted or batch runs, the allocation engine can be driven entirely from the command line.

**Phase 0 only:**
```bash
PYTHONPATH=src python -m allocator.allocation --phase0-only \
  --students data/sample_students.csv \
  --faculty  data/sample_faculty.csv \
  --out      reports/
```

**Full allocation:**
```bash
PYTHONPATH=src python -m allocator.allocation \
  --students data/sample_students.csv \
  --faculty  data/sample_faculty.csv \
  --policy   least_loaded \
  --out      reports/
```

The `--policy` flag accepts `least_loaded` or `cpi_fill`.

---

## 3. Allocation Policies and Metrics

### 3.1 Shared foundation — Phase 0

Both policies begin with **Phase 0**, which classifies students into tiers and sets advisor capacities. The output of Phase 0 is identical regardless of which policy follows.

#### Tiering

Students are divided into tiers based on cohort CPI percentiles:

| Tier | Percentile threshold | Preference window `N_tier` (S/F <= 4) | `N_tier` (S/F > 4) |
|------|---------------------|---------------------------------------|---------------------|
| A | >= 90th (±0.1 grace) | 3 | 4 |
| B | 70th – 90th | 5 | 6 |
| C | < 70th | Full list | Full list |

If more than 40% of students cluster in one band, tiering switches to **quartile mode** (A / B1 / B2 / C). If the cohort has fewer than 10 students, all are placed in Class A with `N_tier = 2`.

#### Faculty capacity

Each advisor's `max_load` is set to `floor(S/F) + 1` unless a value is provided in the faculty CSV, where S is the number of students and F is the number of faculty.

---

### 3.2 Policy: Least Loaded (`least_loaded`)

#### Overview

`least_loaded` is the default policy. It treats load balance as a co-equal constraint alongside preference satisfaction: at every assignment step, a student is directed to the **least-loaded eligible advisor** within their preference-protection window.

#### Pipeline

```
Phase 0  →  Round 1  →  Main Allocation (Class A → B → C)
```

#### Round 1 — Global first-choice pass

Each advisor with at least one first-choice applicant selects exactly one student from that list, defaulting to the highest-CPI applicant (tie-broken by student ID). Manual overrides are supported. This initial pass seats top-tier students at popular advisors and establishes a baseline load distribution.

#### Main allocation

Unassigned students are processed class by class:

1. **Class A** — each student is matched to the least-loaded advisor within their top `N_A` preferences that still has capacity. Students with no eligible advisor within `N_A` are promoted to Class B's pool.
2. **Class B** (original B plus any promoted Class A students) — same rule, window extends to `N_B`.
3. **Class C** (everyone remaining) — no window cap; all advisors with remaining capacity are eligible.

#### Assignment rule

Given a student and their eligible advisors (within `N_tier`, with remaining capacity):

1. Find the **minimum current load** among eligible advisors.
2. If multiple advisors share that minimum, pick the one **earliest in the student's preference list**.
3. Assign the student and increment that advisor's load counter.

Load balance is the **primary criterion**; preference rank is the **tiebreaker**.

#### Properties

| Property | Behaviour |
|----------|-----------|
| Load balance | Strong — advisors are filled as evenly as possible at every step |
| Preference satisfaction (PSI) | Good — low-load advisors often coincide with early preferences |
| Merit sensitivity (NPSS) | Moderate — high-CPI students benefit from Round 1 and the tier window, but are not given explicit priority in the main allocation |
| Empty-lab guarantee | Indirect — the Class C full-list fallback keeps overflows near zero |
| Advisor CPI diversity (entropy) | High — load-spreading tends to distribute different CPI tiers across advisors |
| Robustness | High — performs consistently across random, clustered, and polarised cohorts |

#### When to prefer `least_loaded`

- When **advisor equity** is a departmental priority and no advisor should be significantly more or less loaded than peers.
- In cohorts with **diverse preferences**, where load-balancing and preference satisfaction naturally align.
- As the **safe default** when cohort structure is unknown.

#### Known limitations

- In **clustered cohorts** (many students competing for the same few advisors), load-balancing may route a student to their 2nd or 3rd choice even when their 1st choice still has capacity, if that advisor's load is already higher than an alternative.
- Does **not explicitly reward academic merit** beyond the tier window — two students with very different CPIs within the same tier are treated identically.

---

### 3.3 Policy: CPI Fill (`cpi_fill`)

#### Overview

`cpi_fill` is a merit-first policy. It skips Round 1 and replaces the class-wise main allocation with a two-phase procedure built around a single principle: **students are processed in strict descending CPI order**. Academically stronger students always gain access to their preferred advisors before lower-CPI peers.

#### Pipeline

```
Phase 0  →  CPI-Fill Phase 1  →  CPI-Fill Phase 2
```

Round 1 is not run. The tier information from Phase 0 is computed but not used during assignment — all students draw from their full preference list.

#### Phase 1 — CPI-ordered greedy assignment

**Goal:** assign students in CPI order, stopping precisely when the number of remaining unassigned students equals the number of still-empty labs.

**Stopping condition:** `|unassigned| == |empty labs|`

Steps:

1. Sort all students by CPI, descending (ties broken by student ID).
2. For each student in that order:
   - Scan their preference list from rank 1 onward.
   - Assign the student to the **first advisor in their list with remaining capacity**.
   - Update loads. If `|unassigned| == |empty labs|`, stop Phase 1 immediately.
3. If all labs are already non-empty at the start, Phase 1 runs to completion with no stopping condition.
4. If `|unassigned| == |empty labs|` at the start, Phase 1 is skipped entirely.

The assignment criterion in Phase 1 is **earliest in the student's preference list with capacity** — not least-loaded.

#### Phase 2 — Empty-lab fill

**Goal:** assign each remaining student to their most preferred advisor who currently has zero students (an empty lab).

Steps:

1. Sort remaining unassigned students by CPI, descending.
2. For each student, scan their preference list and assign them to the **first advisor with `load == 0`**.

#### Why the stopping condition works

Each Phase 1 assignment reduces `|unassigned|` by exactly 1 and reduces `|empty labs|` by at most 1. Phase 1 stops when `|unassigned| == |empty labs|`, leaving exactly as many students as there are empty labs. Phase 2 consumes one student and one empty lab per step, so both reach zero simultaneously — guaranteeing full assignment with no empty labs.

#### Properties

| Property | Behaviour |
|----------|-----------|
| Merit sensitivity (NPSS) | High — high-CPI students claim top choices before any lower-CPI student is considered |
| Preference satisfaction (PSI) | Mixed — top students get excellent matches; lower-CPI students may land further down their list |
| Load balance | Weaker — popular advisors can fill up quickly in Phase 1; less popular ones wait for Phase 2 |
| Empty-lab guarantee | Very strong — structurally impossible to leave an advisor empty (when S >= F) |
| Advisor CPI diversity (entropy) | Cohort-dependent — CPI-ordered processing can concentrate high-CPI students at popular advisors, but the effect varies by cohort structure |

#### When to prefer `cpi_fill`

- When **academic merit should explicitly determine priority** and the institution wants high-CPI students to have unambiguous first access to preferred advisors.
- When **no empty labs is a hard requirement** — the Phase 2 design makes this structurally guaranteed.
- In cohorts with **random or weakly correlated preferences**, where Phase 1's greedy rule gives most students their top pick with little competition.

#### Known limitations

- In **clustered preference cohorts**, high-CPI students rapidly fill popular advisors, pushing lower-CPI students far down their lists. This increases overflow and reduces PSI.
- **No tier window** — unlike `least_loaded`, a Class A student whose top advisors are full is not redirected to a broader pool; they continue down their full preference list.
- **Load imbalance** — because Phase 1 uses highest-preference-with-capacity (not least-loaded), popular advisors can absorb many students while unpopular ones wait for Phase 2.

---

### 3.4 Policy comparison

| Aspect | `least_loaded` | `cpi_fill` |
|--------|----------------|------------|
| Round 1 | Yes | No |
| Processing order | Tier-by-tier, arbitrary within tier | Strict descending CPI across all tiers |
| Preference window | `N_tier` per tier (3 / 5 / full) | Full list (no window) |
| Primary assignment criterion | Minimum current load | Earliest preference with capacity |
| Empty-lab guarantee | Indirect (Class C fallback) | Explicit (Phase 2 design) |
| Merit sensitivity (NPSS) | Moderate | High |
| Equal-weighted satisfaction (PSI) | Cohort-dependent | Cohort-dependent |
| Load balance | Strong | Variable |
| Advisor CPI entropy | Cohort-dependent | Cohort-dependent |

> **Note:** Metric outcomes for PSI and advisor entropy are cohort-sensitive. In a five-dataset comparative study, the two policies produce draws on these metrics in most scenarios; neither dominates consistently. See Section 3.6 for guidance on interpretation.

---

### 3.5 Metrics

The app reports four metrics after the allocation completes. They are visible in the **Statistics** tab of the replay panel.

#### NPSS — Normalized Preference Satisfaction Score

NPSS is the **primary metric**. It measures how well student preferences were honoured, weighted by CPI and bounded by each student's protection window.

**Per-student score:**

$$
\text{score}_i =
\begin{cases}
\dfrac{N_{\text{tier},i} - p_i + 1}{N_{\text{tier},i}} & \text{if assigned within the } 1 \to N_{\text{tier}} \text{ window} \\[8pt]
0 & \text{if assigned outside the window}
\end{cases}
$$

where $p_i$ is the rank of the advisor the student was assigned to (1 = 1st choice) and $N_{\text{tier},i}$ is their protection window size.

**Aggregate:**

$$
\text{NPSS} = \sum_{i=1}^{S} \frac{\text{CPI}_i}{\sum_j \text{CPI}_j} \cdot \text{score}_i
$$

NPSS lies in [0, 1]. Normalising by $N_{\text{tier}}$ makes scores comparable across tiers — a Class A student at their last protected rank (3rd) scores the same as a Class B student at their last protected rank (5th). The CPI weighting reflects the protocol's philosophy that failures to honour top-tier preferences should penalise the score more.

| NPSS range | Interpretation |
|------------|----------------|
| 0.90 – 1.00 | Excellent — most students are at or near their 1st choice |
| 0.75 – 0.89 | Good — some preference compromise, likely due to popular advisors filling up |
| 0.60 – 0.74 | Moderate — meaningful preference loss; check per-tier breakdown |
| < 0.60 | Poor — systematic mismatch; review capacity parameters or preference diversity |

#### PSI — Preference Satisfaction Index

PSI is a **complementary, equal-weighted metric**. It treats every student identically and asks simply: on average, how close to the top of their list did each student land?

**Per-student score:**

$$
\text{PSI}_i = 1 - \frac{p_i - 1}{F - 1}
$$

where $F$ is the total number of faculty. This maps 1st choice → 1.0 and last choice → 0.0, with comparisons valid across cohorts of different sizes because the rank is normalised by $F - 1$.

**Aggregate:**

$$
\text{mean PSI} = \frac{1}{S} \sum_{i=1}^{S} \text{PSI}_i
$$

PSI is particularly useful when comparing `least_loaded` and `cpi_fill`: because `cpi_fill` processes students in CPI order, it can boost NPSS for high-CPI students while simultaneously lowering mean PSI for lower-CPI students. Whether this trade-off actually materialises depends on cohort structure — it is most pronounced in clustered or high-CPI cohorts. PSI makes this redistribution visible.

| Mean PSI range | Interpretation |
|----------------|----------------|
| 0.90 – 1.00 | Excellent — students are landing very near their 1st or 2nd choice on average |
| 0.75 – 0.89 | Good — most students are in their top quarter of preferences |
| 0.60 – 0.74 | Moderate — noticeable preference compromise across the cohort |
| < 0.60 | Poor — students are on average landing in the lower half of their list |

**Reading NPSS and PSI together:**

| Pattern | Meaning |
|---------|---------|
| NPSS high, PSI lower than expected | Top-CPI students well served; lower-CPI students landing further down their lists |
| PSI high, NPSS lower | Cohort lands near top preferences on average, but some high-CPI students fell outside their window |
| Both high | Allocation working well across all dimensions |
| Both low | Systematic preference mismatch; investigate capacity and preference diversity |

#### Advisor CPI Entropy

This metric measures **CPI diversity within each advisor's cohort** — whether each advisor received a mix of students from different academic tiers, rather than one advisor attracting all top-CPI students and another receiving only low-CPI students.

For each advisor $a$, bucket assigned students by tier label and compute the Shannon entropy of the tier distribution, normalised to [0, 1]:

$$
H_{\text{norm}}(a) = \frac{-\sum_k p_k(a) \log p_k(a)}{\log K}
$$

where $K$ is the number of tier labels and $p_k(a)$ is the fraction of advisor $a$'s students in tier $k$.

The **system-level score** is the mean of $H_{\text{norm}}(a)$ across all advisors with at least one student. A value near 1.0 indicates most advisors received a mixed-tier cohort; a value near 0 indicates widespread tier segregation.

Entropy is the **preferred advisor-equity metric** because it directly captures tier diversity within each advisor's cohort and is easy to interpret. In the five-dataset comparative study, the two policies produce draws on entropy in most scenarios. The one threshold-crossing difference favours `least_loaded` on the polarised cohort; all other datasets are draws. Use entropy as the primary basis for advisor-equity conclusions rather than CPI skewness.

#### CPI Skewness of Advisor Mean CPIs

This metric measures whether the **distribution of advisor-averaged CPIs** is symmetric or whether a few advisors are receiving a disproportionately high- or low-CPI cohort.

For each advisor $a$, compute the mean CPI of their assigned students. Collect these mean CPIs across all advisors and compute Fisher's adjusted sample skewness:

$$
\gamma = \frac{A}{(A-1)(A-2)} \sum_{a=1}^{A} \left(\frac{\bar{x}_a - \bar{\bar{x}}}{s}\right)^3
$$

| Skewness | Meaning |
|----------|---------|
| ~ 0 | Symmetric — no systematic CPI concentration at any advisor |
| > 0 (positive) | A few advisors have notably higher mean CPIs than the bulk |
| < 0 (negative) | A few advisors have notably lower mean CPIs than the bulk |

An absolute skewness below 0.5 is generally acceptable. Values above 1.0 warrant investigation into whether the allocation is systematically concentrating high- (or low-) CPI students at particular advisors.

**CPI skewness is a diagnostic metric only.** It is highly sensitive to cohort structure — the direction and magnitude of the difference between policies can reverse across different datasets. In the five-dataset comparative study, neither policy shows a consistent skewness advantage: wins are split across cohort types, and on the uniform high-CPI cohort the direction reverses relative to the structured cohorts. Do not use skewness alone to declare a policy winner; always interpret it alongside entropy and the primary NPSS result.

---

### 3.6 How to read the metrics together

When interpreting a single run or comparing the two policies, use this hierarchy:

1. **NPSS** *(primary deciding metric)* — start here. It directly measures whether the allocation honours the protocol's protected student preferences and is CPI-weighted to reflect the protocol's intent. It is the most stable basis for policy comparison.

2. **PSI** *(secondary student metric)* — check for redistribution effects. If NPSS and PSI move in opposite directions across policies, the allocation is trading higher CPI-weighted satisfaction for lower equal-weighted satisfaction (or vice versa). This is a value judgement, not a failure.

3. **Advisor CPI Entropy** *(preferred advisor-equity metric)* — check whether advisors are receiving a mixed or homogeneous tier composition. Prefer entropy over skewness for advisor-equity conclusions because it is easier to interpret and less vulnerable to sign-flip ambiguity.

4. **Advisor Tier Distribution Heatmap** *(visual diagnostic for advisor equity)* — shows which tiers each advisor's cohort contains, row-normalized so advisors with different loads are comparable. Rows sorted by entropy ascending so the most segregated advisors appear first. Broad color across a row = high tier diversity (high entropy). Concentration in one column = tier segregation (low entropy). Use it to understand *why* entropy is high or low — it reveals whether concentration is top-heavy, bottom-heavy, or scattered across individual advisors. It is explanatory only; do not use it to declare a policy winner.

5. **CPI Skewness** *(diagnostic only)* — use as a cross-check for CPI concentration in the advisor mean-CPI distribution. Do not declare a policy winner from skewness alone; results are cohort-sensitive and the direction of the difference can reverse depending on cohort structure.

6. **Overflow Count and % Assigned in Window** *(diagnostic columns)* — these explain *why* NPSS changes in stressed cohorts. Out-of-window assignments already score 0 in NPSS, so these columns add no independent evidential weight beyond what NPSS already captures.

**If metrics disagree:** this is normal. The two policies trade off across dimensions rather than one uniformly dominating the other. The choice between them is a value judgement about institutional priorities — merit-weighted access (`cpi_fill`) versus equitable treatment across tiers (`least_loaded`) — not a metric-determined optimum.

---

*For further details see `MSThesisAllocationProtocol.md` (full protocol specification) and `stats/policy_report.md` (empirical comparison across five synthetic datasets).*
