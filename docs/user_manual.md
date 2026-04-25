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

**Option A1 — In-app (recommended):** Upload the raw form export directly to the app and click **Clean & Load**. The app normalises column names (`Roll No.` → `student_id`, `CPI (as on date)` → `cpi`, `Preference  N` → `pref_N`), maps faculty names to IDs, deduplicates repeated preferences, and backfills any missing faculty alphabetically — all in one step. A faculty CSV with IDs and names must still be uploaded alongside.

**Option A2 — Offline script:** Use the bundled script to produce both files before opening the app:

```bash
python scripts/make_preference_sheet.py form_responses.csv
```

This generates:

| Output file | Contents |
|-------------|----------|
| `preference_sheet.csv` | One row per student — `student_id`, `name`, `cpi`, `pref_1 … pref_N` (faculty IDs in preferences) |
| `faculty_list.csv` | One row per faculty — `faculty_id`, `name`, `max_load` (blank; fill in manually) |

The script applies the same cleaning steps as Clean & Load: flexible column naming, deduplication, and alphabetical backfill.

**Script options:**

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

Navigate to **http://localhost:8050**. The landing page shows a policy selector and two buttons:

- **Continue →** — proceed to the allocation workflow with the selected policy.
- **View Analysis** — jump directly to the Analysis page to load and compare previously saved runs, without starting a new allocation.

#### Step 2 — Select a policy

Choose one of the four allocation policies on the landing page:

- **Least Loaded (`least_loaded`)** — the default; assigns each student to the least-loaded eligible advisor within their tier preference window.
- **Highest Preferred with Vacancy (`nonempty`)** — like `least_loaded` but steers students toward empty labs first.
- **CPI Fill (`cpi_fill`)** — merit-first; processes students in strict descending CPI order; no tier window applied.
- **CPI-Tiered Preference Rounds (`tiered_rounds`)** — round-based; in round *n* each student offers their *n*-th preference; CPI breaks ties; manual pick required when top CPI is tied.

A full discussion of all policies is in Section 3. To switch policy mid-session, click **Home** (top-right of the allocation page) to return to the landing page.

#### Step 3 — Load input files

Use the file upload controls on the main page to upload your `students.csv` and `faculty.csv`. The app validates both files and reports any errors (missing columns, mismatched faculty IDs, etc.) before proceeding.

Two loading modes are available:

| Button | When to use |
|--------|-------------|
| **Clean & Load** | Raw Google Form export with faculty names in the preference columns — the app converts names to IDs automatically |
| **Load directly** | Pre-processed file with faculty IDs (`F01`, `F02`, …) already in the preference columns |

#### Step 4 — Run Phase 0

Click **Run Phase 0 only** to tier students and compute faculty capacities without running the allocation, or click **Run full allocation** to do both in one step.

#### Step 5 — Complete the allocation

- **`least_loaded` / `nonempty`:** Confirm Round-1 picks (default: highest-CPI student per advisor), then proceed to main allocation, making or confirming each assignment.
- **`cpi_fill`:** Run Phase 1 (manual or auto), then Phase 2.
- **`tiered_rounds`:** The engine runs rounds automatically until a CPI tie is detected. Resolve each tie using the dropdown; the engine resumes automatically.

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
| **Tier Heatmap** | Advisor × CPI-tier heatmap. Each cell = students in that tier × 100 / capacity (`max_load`), so the row sum equals the advisor's total load as a percentage of capacity. Rows sorted by load descending. Diagnostic view for advisor equity — use together with Avg CPI Entropy. |

---

### 2.4 Completion panel

When the allocation finalises, a completion panel appears above the replay panel. It contains:

**Summary alert** — total assigned, unassigned, and empty labs.

**Action buttons:**

| Button | Action |
|--------|--------|
| **Save report (CSV)** | Downloads a CSV with every student's assignment, preference rank, tier, and advisor load |
| **Save run (JSON)** | Saves the full run (assignments, metrics, metadata) to the `results/` folder on the server for later analysis; shows a confirmation message inline |
| **Export HTML** | Saves a self-contained HTML snapshot of the current visualisation to `reports/` |
| **Open Analysis** | Navigates to the Analysis page |

**Summary badge row** — always visible: `NPSS | PSI | Entropy | Load balance`. Load balance is the difference between the most-loaded and least-loaded advisor (including empty advisors), giving a quick measure of load spread.

**Collapsible sections** — both panels below are closed by default and can be expanded by clicking their header button:

- **[+] Advisor Popularity** — shows how many students listed each advisor as their 1st, 2nd, or 3rd choice, with tier breakdown.
- **[+] Metrics** — full metrics panel: NPSS, PSI, per-tier breakdown, advisor CPI entropy, and CPI skewness.

For `tiered_rounds`, the completion panel also includes a collapsible **Round-by-Round Trace** showing assignments, ties, and manual decisions per round.

---

### 2.5 Analysis page

The Analysis page (`/analysis`) is a dedicated post-allocation environment for comparing saved runs. It can be reached three ways:

- **Landing page** → **View Analysis** button
- **Completion panel** → **Open Analysis** button
- **Analysis page** → **Home** → re-select policy → **View Analysis**

#### Saving a run

After finalising an allocation, click **Save run (JSON)** in the completion panel. The run is written to the `results/` folder as `{policy}_{timestamp}.json` and a confirmation message appears inline. No file dialog opens.

#### Loading runs on the Analysis page

1. **Run A** (required) — select a saved run from the dropdown.
2. **Run B** (optional) — select a second run for side-by-side comparison; leave as "None" for single-run view.
3. Click **Load**.

The page renders:

| Section | What it shows |
|---------|---------------|
| **Metric scorecards** | NPSS, PSI, per-tier breakdown, and advisor fairness metrics for each loaded run (side by side when two runs are loaded) |
| **Per-Tier Mean Preference Rank chart** | Grouped bar chart — one group per tier, one bar per policy. Y-axis is mean assigned preference rank (lower = better). Bar labels show % of tier assigned within their protected window. |
| **Advisor Tier Heatmap** | Capacity-normalised heatmap for each loaded run, showing how each advisor's load is distributed across CPI tiers |

#### Navigation

- **← Back to allocation** — returns to the allocation page with all state intact.
- **Home** — returns to the landing page for policy switching.

---

### 2.6 CLI usage (no GUI)

For scripted or batch runs, the allocation engine can be driven entirely from the command line. Note that `tiered_rounds` requires the Dash UI for manual tie-breaking and is not available via CLI.

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

The `--policy` flag accepts `least_loaded`, `nonempty`, or `cpi_fill`.

---

## 3. Allocation Policies and Metrics

### 3.1 Shared foundation — Phase 0

All policies begin with **Phase 0**, which classifies students into tiers and sets advisor capacities. The output of Phase 0 is identical regardless of which policy follows.

#### Tiering

Students are divided into tiers based on cohort CPI percentiles:

| Tier | Percentile threshold | Preference window `N_tier` (S/F ≤ 4) | `N_tier` (S/F > 4) |
|------|---------------------|---------------------------------------|---------------------|
| A | ≥ 90th (±0.1 grace) | 3 | 4 |
| B | 70th – 90th | 5 | 6 |
| C | < 70th | Full list | Full list |

If more than 40% of students cluster in one band, tiering switches to **quartile mode** (A / B1 / B2 / C). If the cohort has fewer than 10 students, all are placed in Class A with `N_tier = 2`.

`N_tier` is used as the **assignment window** in `least_loaded` and `nonempty`. For `cpi_fill` and `tiered_rounds` it is computed but not applied during assignment — it appears in the per-tier diagnostics only.

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

---

### 3.3 Policy: Highest Preferred with Vacancy (`nonempty`)

#### Overview

`nonempty` is a **load-distribution variant** of `least_loaded`. It runs the same Phase 0 → Round 1 → Main Allocation pipeline but changes the advisor selection rule: instead of always choosing the advisor with the minimum current load, it **actively seeks out empty labs** first. Only if no empty lab exists within the student's preference window does it fall back to the least-loaded advisor.

#### Assignment rule

Given a student and their eligible candidate advisors (those within `N_tier` with remaining capacity):

1. **If any empty lab exists** within the eligible set: assign to the **highest-preferred empty lab** (earliest in the student's preference list).
2. **Otherwise:** assign to the **highest-preferred advisor** with remaining capacity (earliest in list, regardless of current load).

#### Properties

| Property | Behaviour |
|----------|-----------|
| Empty-lab guarantee | Strong — aggressively fills empty labs before considering non-empty ones |
| Preference satisfaction (PSI) | Similar to `least_loaded`; can be slightly better or worse depending on preference alignment |
| Load balance | Moderate — once all labs have students, degenerates to a pure highest-preference-within-window rule |
| Merit sensitivity (NPSS) | Similar to `least_loaded` — no explicit CPI ordering beyond the tier window |

---

### 3.4 Policy: CPI Fill (`cpi_fill`)

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

#### Phase 2 — Empty-lab fill

**Goal:** assign each remaining student to their most preferred advisor who currently has zero students.

Steps:

1. Sort remaining unassigned students by CPI, descending.
2. For each student, scan their preference list and assign to the **first advisor with `load == 0`**.

#### Properties

| Property | Behaviour |
|----------|-----------|
| Merit sensitivity (NPSS) | High — high-CPI students claim top choices before any lower-CPI student is considered |
| Preference satisfaction (PSI) | Mixed — top students get excellent matches; lower-CPI students may land further down their list |
| Load balance | Weaker — popular advisors can fill up quickly in Phase 1 |
| Empty-lab guarantee | Very strong — structurally impossible to leave an advisor empty (when S ≥ F) |
| Advisor CPI diversity (entropy) | Cohort-dependent |

---

### 3.5 Policy: CPI-Tiered Preference Rounds (`tiered_rounds`)

#### Overview

`tiered_rounds` is a **round-based, interactive policy**. In round *n*, every unassigned student simultaneously offers their *n*-th preference. Each participating advisor selects at most one student (the highest-CPI candidate). If two or more students share the top CPI at the same advisor, the operator resolves the tie manually. The process repeats until all students are assigned.

#### Pipeline

```
Phase 0  →  Preference Rounds (n = 1, 2, 3, …)
```

No separate Round 1 or class-wise main allocation. Phase 0 tier classification is computed but does not constrain round participation.

#### Selection rule

- **Unique highest CPI** → immediate assignment.
- **CPI tie at the top** → operator picks one; remaining candidates advance to round *n+1*.
- Advisors that became full in a previous round are skipped entirely.
- Each advisor allocates **at most one student per round**, even if it still has capacity > 1.

#### Properties

| Property | Behaviour |
|----------|-----------|
| Merit sensitivity (NPSS) | High — CPI determines priority within each round |
| Preference satisfaction (PSI) | High in balanced cohorts; students advance down their list only when earlier choices are taken |
| Transparency | Highest — every assignment and every tie-break decision is logged in the round trace |
| Operator involvement | Required for CPI ties; cannot run unattended if ties exist |
| Load balance | Implicit (one per advisor per round); not explicitly optimised |

---

### 3.6 Policy comparison

| Aspect | `least_loaded` | `nonempty` | `cpi_fill` | `tiered_rounds` |
|--------|----------------|------------|------------|-----------------|
| Round 1 | Yes | Yes | No | No |
| Processing order | Tier-by-tier | Tier-by-tier | Strict descending CPI | Round-by-preference-rank |
| Preference window | Applied per tier; overflow possible via promotion cascade | Applied per tier; overflow possible via promotion cascade | Full list | Full list (N_tier diagnostic only) |
| Primary assignment criterion | Min load | Emptiness → preference | First pref with capacity | Highest CPI in round |
| Tie-breaking | Preference rank | Preference rank | Student ID | Manual operator pick |
| Empty-lab guarantee | Indirect | Strong | Explicit (Phase 2) | Implicit |
| Merit sensitivity (NPSS) | Moderate | Moderate | High | High |
| Equal-weighted satisfaction (PSI) | Cohort-dependent | Cohort-dependent | Cohort-dependent | High in balanced cohorts |
| Load balance | Strong | Moderate | Variable | Implicit |
| CLI available | Yes | Yes | Yes | No (GUI only) |

> **Note:** PSI and advisor entropy outcomes are cohort-sensitive. Neither policy dominates consistently across all cohort types. See Section 3.8 for guidance on interpretation.

---

### 3.7 Metrics

The app reports metrics in two places: the **Statistics** tab of the replay panel (updated at each step) and the **completion panel summary badge row** (final state only).

#### NPSS — Normalized Preference Satisfaction Score

NPSS is the **primary metric**. It measures how well student preferences were honoured, weighted by CPI.

**Per-student score:**

$$
\text{score}_i = \frac{F - p_i + 1}{F}
$$

where $p_i$ is the preference rank of the advisor assigned to student *i* (1 = 1st choice) and $F$ is the total number of faculty (= the full preference list length, the same for all students).

**Aggregate:**

$$
\text{NPSS} = \sum_{i=1}^{S} \frac{\text{CPI}_i}{\sum_j \text{CPI}_j} \cdot \text{score}_i
$$

NPSS lies in (0, 1]. Using $F$ as the denominator — rather than the tier-specific `N_tier` — means all four policies are evaluated on the same scale, enabling fair cross-protocol comparison. A student assigned at rank 1 always scores 1.0; a student at rank $F$ scores $1/F \approx 0$.

| NPSS range | Interpretation |
|------------|----------------|
| 0.95 – 1.00 | Excellent — cohort is landing predominantly at ranks 1–2 |
| 0.85 – 0.94 | Good — most students in top 5; some further |
| 0.70 – 0.84 | Moderate — noticeable preference compromise; check per-tier breakdown |
| < 0.70 | Poor — systematic mismatch; review capacity parameters or preference diversity |

The CPI weighting reflects the protocol's philosophy that failures to honour high-CPI students' preferences should penalise the score more than equivalent failures for lower-CPI students.

#### PSI — Preference Satisfaction Index

PSI is a **complementary, equal-weighted metric**. It treats every student identically and asks: on average, how close to the top of their list did each student land?

**Per-student score:**

$$
\text{PSI}_i = 1 - \frac{p_i - 1}{F - 1}
$$

This maps 1st choice → 1.0 and last choice → 0.0, normalised by $F - 1$ so comparisons are valid across cohorts of different sizes.

**Aggregate:**

$$
\text{mean PSI} = \frac{1}{S} \sum_{i=1}^{S} \text{PSI}_i
$$

PSI is particularly useful when comparing policies: because `cpi_fill` processes students in CPI order, it can boost NPSS for high-CPI students while simultaneously lowering mean PSI for lower-CPI students. PSI makes this redistribution visible.

| Mean PSI range | Interpretation |
|----------------|----------------|
| 0.90 – 1.00 | Excellent — students landing very near their 1st or 2nd choice on average |
| 0.75 – 0.89 | Good — most students in their top quarter of preferences |
| 0.60 – 0.74 | Moderate — noticeable preference compromise across the cohort |
| < 0.60 | Poor — students landing in the lower half of their list on average |

**Reading NPSS and PSI together:**

| Pattern | Meaning |
|---------|---------|
| NPSS high, PSI lower than expected | Top-CPI students well served; lower-CPI students landing further down their lists |
| PSI high, NPSS lower | Cohort lands near top preferences on average, but CPI-weighted satisfaction is lower |
| Both high | Allocation working well across all dimensions |
| Both low | Systematic preference mismatch; investigate capacity and preference diversity |

#### Overflow Count (diagnostic)

The overflow count reports the number of students assigned **beyond their tier `N_tier` window** (rank > `N_tier`). This is a protocol-compliance diagnostic, tracked separately from NPSS. Because NPSS now uses $F$ as its denominator, out-of-window placements still receive a positive NPSS contribution — the overflow count is the only place where tier-cap compliance is flagged numerically.

All four policies can produce overflow, but through different mechanisms:

- **`least_loaded` / `nonempty`**: the N_tier window is applied first; a student is only promoted to a wider pool (B → C, or A → B → C) when every advisor within their current window is at capacity. Overflow occurs when the promotion chain ends at the Class C full-list round and the assigned rank exceeds the original N_tier. This is anomalous — it only happens under very tight capacity — and is flagged as a **red warning badge**.
- **`cpi_fill` / `tiered_rounds`**: no N_tier window is applied during assignment; overflow is a structural feature of the protocol. For `tiered_rounds` in particular, a student reaches round *n* naturally when their first *n*−1 preferences were claimed by others, so assignments beyond N_tier are expected and routine. These are shown as a **blue informational badge**, not an error.

#### Advisor CPI Entropy

This metric measures **CPI diversity within each advisor's cohort** — whether each advisor received a mix of students from different academic tiers.

For each advisor $a$, bucket assigned students by tier label and compute the Shannon entropy of the tier distribution, normalised to [0, 1]:

$$
H_{\text{norm}}(a) = \frac{-\sum_k p_k(a) \log p_k(a)}{\log K}
$$

where $K$ is the number of tier labels and $p_k(a)$ is the fraction of advisor $a$'s students in tier $k$.

The **system-level score** is the mean of $H_{\text{norm}}(a)$ across all advisors with at least one student. A value near 1.0 indicates most advisors received a mixed-tier cohort; a value near 0 indicates widespread tier segregation.

#### CPI Skewness of Advisor Mean CPIs

This metric measures whether the **distribution of advisor-averaged CPIs** is symmetric or skewed — whether a few advisors are receiving a disproportionately high- or low-CPI cohort.

For each advisor $a$, compute the mean CPI of their assigned students. Collect these mean CPIs across all advisors and compute Fisher's adjusted sample skewness:

$$
\gamma = \frac{A}{(A-1)(A-2)} \sum_{a=1}^{A} \left(\frac{\bar{x}_a - \bar{\bar{x}}}{s}\right)^3
$$

| Skewness | Meaning |
|----------|---------|
| ~ 0 | Symmetric — no systematic CPI concentration at any advisor |
| > 0 | A few advisors have notably higher mean CPIs than the bulk |
| < 0 | A few advisors have notably lower mean CPIs than the bulk |

An absolute skewness below 0.5 is generally acceptable. Values above 1.0 warrant investigation.

#### Load Balance

Load Balance = `max(advisor loads) − min(advisor loads)` across all advisors in the final allocation (including any with zero students). It appears only in the **completion panel summary badge row**. A value of 0 means identical loads. A value of 1 is the minimum non-zero spread and is typical in well-balanced runs.

---

### 3.8 How to read the metrics together

When interpreting a single run or comparing policies, use this hierarchy:

1. **NPSS** *(primary)* — start here. It directly measures whether the allocation honours student preferences and is CPI-weighted to reflect the protocol's intent. All four policies use the same full-list denominator, so NPSS values are directly comparable across policies.

2. **PSI** *(secondary student metric)* — check for redistribution effects. If NPSS and PSI move in opposite directions across policies, the allocation is trading higher CPI-weighted satisfaction for lower equal-weighted satisfaction (or vice versa). This is a value judgement, not a failure.

3. **Advisor CPI Entropy** *(preferred advisor-equity metric)* — check whether advisors are receiving a mixed or homogeneous tier composition.

4. **Advisor Tier Distribution Heatmap** *(visual diagnostic)* — shows which tiers each advisor's cohort contains, row-normalized by capacity. Use it to understand *why* entropy is high or low.

5. **Load Balance** *(sanity check)* — max minus min of final advisor loads. A quick scan; expand the Metrics or Advisor Loads panels for detail.

6. **CPI Skewness** *(diagnostic only)* — use as a cross-check for CPI concentration in the advisor mean-CPI distribution. Results are cohort-sensitive; do not declare a policy winner from skewness alone.

7. **Overflow Count** *(protocol-compliance diagnostic)* — reports placements beyond the tier `N_tier` window. For window-applying policies (`least_loaded`, `nonempty`) this signals near-overflow stress (promotion cascaded all the way to the full-list round). For `cpi_fill` and `tiered_rounds` — which apply no window during assignment — it is purely informational, and the UI shows it as a blue badge rather than a red one. It does not affect NPSS.

**If metrics disagree:** this is normal. The four policies trade off across dimensions rather than one uniformly dominating. The choice is a value judgement about institutional priorities — merit-weighted access, equitable treatment, load balance, or operator transparency — not a metric-determined optimum.

---

*For further details see `MSThesisAllocationProtocol.md` (full protocol specification), `NPSS_Metric.md` (NPSS/PSI definitions), `docs/policy_*.md` (per-policy deep-dives), and `stats/policy_report.md` (empirical comparison across five synthetic datasets).*
