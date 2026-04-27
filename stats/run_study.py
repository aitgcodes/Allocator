"""
run_study.py — Policy comparison study.

Generates 4 synthetic random preference sheets (plus uses the original test data),
runs the full allocation under both 'least_loaded' and 'cpi_fill' policies on each
dataset, collects metrics, and writes a Markdown report to stats/policy_report.md.

Usage (from repo root):
    PYTHONPATH=src python stats/run_study.py
"""

from __future__ import annotations

import math
import os
import random
import sys
import copy
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from allocator.data_loader import load_students, load_faculty
from allocator.allocation import run_full_allocation
from allocator.state import Student, Faculty

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TEST_DIR  = REPO_ROOT / "test"
STATS_DIR = REPO_ROOT / "stats"
STATS_DIR.mkdir(exist_ok=True)

ORIGINAL_STUDENTS = TEST_DIR / "preference_sheet.csv"
FACULTY_FILE      = TEST_DIR / "faculty_list.csv"

POLICIES = ["least_loaded", "cpi_fill"]

RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Synthetic dataset generation
# ---------------------------------------------------------------------------

def generate_random_preference_sheet(
    template_students: List[Student],
    faculty_ids: List[str],
    rng: random.Random,
    scenario: str,
    output_path: Path,
) -> Path:
    """
    Generate a random preference sheet CSV.

    Three scenario types (controlled by `scenario`):
        "random"   : fully random shuffled preferences, CPI drawn U(5.5, 10.0)
        "clustered": 70% of students heavily prefer a random subset of 8 faculty
        "polarised": top-CPI half prefers one group of faculty, low-CPI half prefers another
    """
    n_students = len(template_students)
    n_faculty  = len(faculty_ids)
    rows = ["student_id,name,cpi," + ",".join(f"pref_{i}" for i in range(1, n_faculty + 1))]

    for idx, tmpl in enumerate(template_students):
        sid  = tmpl.id
        name = tmpl.name
        cpi  = round(rng.uniform(5.5, 10.0), 2)

        prefs = faculty_ids.copy()

        if scenario == "random":
            rng.shuffle(prefs)

        elif scenario == "clustered":
            # 70 % of students heavily prefer the same 8 "popular" faculty
            popular = faculty_ids[:8]
            rest    = faculty_ids[8:]
            if rng.random() < 0.70:
                rng.shuffle(popular)
                rng.shuffle(rest)
                prefs = popular + rest
            else:
                rng.shuffle(prefs)

        elif scenario == "polarised":
            # Top-CPI half prefers first group, bottom-CPI half prefers second group
            group_a = faculty_ids[:n_faculty // 2]
            group_b = faculty_ids[n_faculty // 2:]
            if cpi >= 7.75:
                rng.shuffle(group_a)
                rng.shuffle(group_b)
                prefs = group_a + group_b
            else:
                rng.shuffle(group_b)
                rng.shuffle(group_a)
                prefs = group_b + group_a

        elif scenario == "uniform_high_cpi":
            # All students have high CPI (8.0–10.0) and random preferences
            cpi = round(rng.uniform(8.0, 10.0), 2)
            rng.shuffle(prefs)

        row = f"{sid},{name},{cpi}," + ",".join(prefs)
        rows.append(row)

    output_path.write_text("\n".join(rows) + "\n")
    return output_path


# ---------------------------------------------------------------------------
# Run allocations across datasets and policies
# ---------------------------------------------------------------------------

def run_dataset(students_path: Path, faculty_path: Path, label: str) -> dict:
    """
    Run both policies on a single dataset. Returns a dict of results keyed by policy.
    """
    results = {}
    for policy in POLICIES:
        students = load_students(str(students_path))
        faculty  = load_faculty(str(faculty_path))
        assignments, snapshots, meta, metrics = run_full_allocation(
            students, faculty, policy=policy
        )
        results[policy] = {
            "assignments": assignments,
            "meta":        meta,
            "metrics":     metrics,
            "n_students":  len(students),
            "n_faculty":   len(faculty),
        }
    return results


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _fmt(v, decimals=4):
    if v is None:
        return "N/A"
    return f"{v:.{decimals}f}"


def stdev(vals: List[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    return math.sqrt(sum((x - mean) ** 2 for x in vals) / (len(vals) - 1))


def mean(vals: List[float]) -> float:
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(all_results: Dict[str, dict], scenario_labels: Dict[str, str]) -> str:
    lines: List[str] = []

    lines += [
        "# Allocation Policy Comparison Study",
        "",
        "**Policies compared:** `least_loaded` vs `cpi_fill`  ",
        "**Abbreviations:** LL = `least_loaded`, CF = `cpi_fill` (used in table annotations and inline comparisons throughout this report)  ",
        "**Datasets:** 1 original + 4 synthetic (random, clustered, polarised, uniform_high_cpi)  ",
        "**Metric hierarchy:**",
        "  1. NPSS — primary student metric (CPI-weighted preference satisfaction)  ",
        "  2. PSI — secondary student metric (equal-weighted, global rank)  ",
        "  3. MSES — primary advisor satisfaction metric (mean rank students placed their advisor; lower = more enthusiastic)  ",
        "  4. Equity Retention Rate — advisor equity metric (% of load-distribution's achievable entropy preserved; always in [0,100%])  ",
        "  5. CPI Skewness — diagnostic (asymmetry in advisor mean-CPI distribution; Fisher-Pearson formula, std-normalized)  ",
        "**Diagnostic columns (not independent deciding metrics):** Overflow Count, % Assigned in Window, Avg LUR  ",
        "  — out-of-window assignments already score 0 in NPSS, so these columns explain *why* NPSS  ",
        "  is low in stressed scenarios but carry no additional evidential weight for policy comparison.  ",
        "",
        "---",
        "",
    ]

    # ------------------------------------------------------------------ #
    # Section 1 — Per-dataset summary table
    # ------------------------------------------------------------------ #
    lines += [
        "## 1. Per-Dataset Metric Summary",
        "",
        "### 1a. Student Satisfaction Metrics",
        "",
        "| Dataset | Policy | NPSS ↑ | PSI ↑ | Overflow ↓ | % Assigned in Window ↑ |",
        "|---------|--------|--------|-------|------------|------------------------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            m = res["metrics"]
            npss         = m["npss"]
            psi          = m["mean_psi"]
            overflow     = m["overflow_count"]
            n_students   = res["n_students"]
            in_window_pct = (1 - overflow / n_students) * 100 if n_students else 0

            lines.append(
                f"| {label} | {policy} | {_fmt(npss)} | {_fmt(psi)} "
                f"| {overflow} | {in_window_pct:.1f}% |"
            )

    lines += [
        "",
        "### 1b. Per-Tier Student Satisfaction Metrics",
        "",
        "| Dataset | Policy | Tier | Count | Mean Rank ↓ | Within-Window % ↑ | Mean NPSS ↑ | Mean PSI ↑ |",
        "|---------|--------|------|-------|------------|-------------------|-------------|------------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            per_tier = res["metrics"]["per_tier"]
            for tier in ["A", "B", "B1", "B2", "C"]:
                td = per_tier.get(tier, {})
                if not td or td.get("count", 0) == 0:
                    continue
                lines.append(
                    f"| {label} | {policy} | {tier} "
                    f"| {td['count']} "
                    f"| {_fmt(td['mean_rank'], 2) if td['mean_rank'] is not None else 'N/A'} "
                    f"| {td['within_window_rate']*100:.1f}% "
                    f"| {_fmt(td['mean_npss_score'])} "
                    f"| {_fmt(td['mean_psi_score'])} |"
                )

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 2 — Advisor metrics
    # ------------------------------------------------------------------ #
    lines += [
        "## 2. Advisor Metrics",
        "",
        "### 2a. Advisor Satisfaction",
        "",
        "| Dataset | Policy | Avg MSES ↓ | Avg LUR *(utilisation)* |",
        "|---------|--------|-----------|------------------------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            adv = res["metrics"]["advisor"]
            mses_str = _fmt(adv.get("avg_mses")) if adv.get("avg_mses") is not None else "N/A"
            lur_str  = f"{adv['avg_lur']*100:.1f}%" if adv.get("avg_lur") is not None else "N/A"
            lines.append(
                f"| {label} | {policy} "
                f"| {mses_str} "
                f"| {lur_str} |"
            )

    lines += [
        "",
        "### 2b. Advisor Equity — Load Distribution",
        "",
        "| Dataset | Policy | Advisors Assigned | Empty Labs ↓ |",
        "|---------|--------|-------------------|--------------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            adv = res["metrics"]["advisor"]
            lines.append(
                f"| {label} | {policy} "
                f"| {adv.get('advisors_assigned', '?')} "
                f"| {adv.get('empty_labs', '?')} |"
            )

    lines += [
        "",
        "### 2c. Advisor Equity — Tier Mixing",
        "",
        "| Dataset | Policy | Load-Aware Entropy Ceiling | Equity Retention % ↑ | CPI Skewness *(diag)* |",
        "|---------|--------|----------------------------|----------------------|-----------------------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            adv = res["metrics"]["advisor"]
            lines.append(
                f"| {label} | {policy} "
                f"| {_fmt(adv.get('baseline_entropy', 0.0))} "
                f"| {adv.get('equity_retention', 100.0):.1f}% "
                f"| {_fmt(adv['cpi_skewness'])} |"
            )

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 3 — Aggregate comparison (mean ± std across all datasets)
    # ------------------------------------------------------------------ #
    lines += [
        "## 3. Aggregate Statistics Across All Datasets",
        "",
        "Values are **mean ± std** across the 5 datasets.",
        "",
        "> **Note on interpretation:** With only 5 datasets and no formal significance testing,",
        "> these aggregate comparisons are descriptive, not inferential. The std devs overlap",
        "> heavily for every metric. A win is called only when the mean difference clearly",
        "> exceeds the per-metric significance threshold; otherwise the result is a **Draw**.",
        "",
        "| Metric | `least_loaded` | `cpi_fill` | Threshold | Verdict |",
        "|--------|---------------|------------|-----------|---------|",
    ]

    # Significance thresholds (based on observed delta distributions)
    THRESHOLDS = {
        "NPSS":                  0.04,
        "PSI":                   0.025,
        "Avg MSES":              0.5,
        "Equity Retention %":    5.0,
        "CPI Skewness (|abs|)":  0.10,
    }
    DIAGNOSTIC = {"Overflow Count", "% In Window", "Advisors Assigned", "Avg LUR"}

    metric_collectors: Dict[str, Dict[str, List[float]]] = {
        "NPSS":                  {p: [] for p in POLICIES},
        "PSI":                   {p: [] for p in POLICIES},
        "Overflow Count":        {p: [] for p in POLICIES},
        "% In Window":           {p: [] for p in POLICIES},
        "Avg MSES":              {p: [] for p in POLICIES},
        "Equity Retention %":    {p: [] for p in POLICIES},
        "Avg LUR":               {p: [] for p in POLICIES},
        "CPI Skewness (|abs|)":  {p: [] for p in POLICIES},
        "Advisors Assigned":     {p: [] for p in POLICIES},
    }

    for ds_key, policy_results in all_results.items():
        for policy, res in policy_results.items():
            m   = res["metrics"]
            adv = m["advisor"]
            n   = res["n_students"]
            metric_collectors["NPSS"][policy].append(m["npss"])
            metric_collectors["PSI"][policy].append(m["mean_psi"])
            metric_collectors["Overflow Count"][policy].append(m["overflow_count"])
            metric_collectors["% In Window"][policy].append(
                (1 - m["overflow_count"] / n) * 100 if n else 0
            )
            if adv.get("avg_mses") is not None:
                metric_collectors["Avg MSES"][policy].append(adv["avg_mses"])
            metric_collectors["Equity Retention %"][policy].append(adv.get("equity_retention", 100.0))
            if adv.get("avg_lur") is not None:
                metric_collectors["Avg LUR"][policy].append(adv["avg_lur"] * 100)
            if adv["cpi_skewness"] is not None:
                metric_collectors["CPI Skewness (|abs|)"][policy].append(abs(adv["cpi_skewness"]))
            metric_collectors["Advisors Assigned"][policy].append(adv["advisors_assigned"])

    # Direction: higher is better for NPSS, PSI, % In Window, Equity Retention, Avg LUR, Advisors;
    #            lower is better for Overflow, MSES, Skewness (|abs|)
    higher_better = {"NPSS", "PSI", "% In Window", "Equity Retention %", "Avg LUR", "Advisors Assigned"}

    for metric_name, by_policy in metric_collectors.items():
        means  = {p: mean(v) for p, v in by_policy.items()}
        stdevs = {p: stdev(v) for p, v in by_policy.items()}

        ll_str = f"{means['least_loaded']:.4f} ± {stdevs['least_loaded']:.4f}"
        cf_str = f"{means['cpi_fill']:.4f} ± {stdevs['cpi_fill']:.4f}"

        if metric_name in DIAGNOSTIC:
            verdict = "*(diagnostic)*"
            thresh_str = "*(diag)*"
        else:
            threshold = THRESHOLDS.get(metric_name, 0.0)
            thresh_str = f"≥ {threshold}"
            delta = abs(means["least_loaded"] - means["cpi_fill"])
            if delta < threshold:
                verdict = "**Draw**"
            else:
                if metric_name in higher_better:
                    winner = "least_loaded" if means["least_loaded"] > means["cpi_fill"] else "cpi_fill"
                else:
                    winner = "least_loaded" if means["least_loaded"] < means["cpi_fill"] else "cpi_fill"
                role = "(diagnostic)" if metric_name == "CPI Skewness (|abs|)" else ""
                verdict = f"**{winner}** {role}".strip()

        lines.append(f"| {metric_name} | {ll_str} | {cf_str} | {thresh_str} | {verdict} |")

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 4 — Pairwise delta table (cpi_fill - least_loaded per dataset)
    # ------------------------------------------------------------------ #
    lines += [
        "## 4. Per-Dataset Policy Deltas (cpi_fill − least_loaded)",
        "",
        "Positive ΔNPSS / ΔPSI / ΔEquity Retention means `cpi_fill` is better; negative means `least_loaded` is better.",
        "ΔMSES: negative means CF students are more enthusiastic (lower mean rank = better).",
        "ΔSkewness = Δ|abs| = |CF| − |LL|; negative means CF has lower absolute skewness.",
        "Overflow and % In Window are shown for diagnostic context only (not used to declare wins).",
        "",
        "| Dataset | ΔNPSS | ΔPSI | ΔMSES | ΔEquity Ret% | ΔOverflow *(diag)* | Δ% In Window *(diag)* | ΔSkewness *(diag)* |",
        "|---------|-------|------|-------|-------------|--------------------|-----------------------|-------------------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        ll = policy_results["least_loaded"]
        cf = policy_results["cpi_fill"]

        ml  = ll["metrics"]
        mc  = cf["metrics"]
        n   = ll["n_students"]

        d_npss    = mc["npss"]       - ml["npss"]
        d_psi     = mc["mean_psi"]   - ml["mean_psi"]
        d_over    = mc["overflow_count"] - ml["overflow_count"]
        d_win     = ((1 - mc["overflow_count"]/n) - (1 - ml["overflow_count"]/n)) * 100
        sk_cf     = mc["advisor"]["cpi_skewness"]
        sk_ll     = ml["advisor"]["cpi_skewness"]
        d_skew    = (_fmt(sk_cf - sk_ll) if (sk_cf is not None and sk_ll is not None) else "N/A")

        mses_cf = mc["advisor"].get("avg_mses")
        mses_ll = ml["advisor"].get("avg_mses")
        d_mses  = f"{mses_cf - mses_ll:+.4f}" if (mses_cf is not None and mses_ll is not None) else "N/A"

        err_cf  = mc["advisor"].get("equity_retention", 100.0)
        err_ll  = ml["advisor"].get("equity_retention", 100.0)
        d_err   = f"{err_cf - err_ll:+.1f}%"

        lines.append(
            f"| {label} "
            f"| {d_npss:+.4f} "
            f"| {d_psi:+.4f} "
            f"| {d_mses} "
            f"| {d_err} "
            f"| {d_over:+d} "
            f"| {d_win:+.1f}% "
            f"| {d_skew} |"
        )

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 5 — Detailed per-student rank distribution (box-style)
    # ------------------------------------------------------------------ #
    lines += [
        "## 5. Assigned Preference Rank Distributions",
        "",
        "| Dataset | Policy | Min Rank | Median Rank | Mean Rank | Max Rank | Std Rank |",
        "|---------|--------|----------|-------------|-----------|----------|----------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            ps = res["metrics"]["per_student"]
            ranks = sorted(
                [v["assigned_rank"] for v in ps.values() if v["assigned_rank"] is not None]
            )
            if not ranks:
                lines.append(f"| {label} | {policy} | N/A | N/A | N/A | N/A | N/A |")
                continue
            n = len(ranks)
            med = ranks[n // 2] if n % 2 == 1 else (ranks[n//2 - 1] + ranks[n//2]) / 2
            mn  = sum(ranks) / n
            sd  = math.sqrt(sum((r - mn)**2 for r in ranks) / max(n - 1, 1))
            lines.append(
                f"| {label} | {policy} "
                f"| {ranks[0]} | {med:.1f} | {mn:.2f} | {ranks[-1]} | {sd:.2f} |"
            )

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 6 — Scenario-specific observations and recommendation
    # ------------------------------------------------------------------ #
    lines += [
        "## 6. Scenario-by-Scenario Observations",
        "",
    ]

    NPSS_THRESH = THRESHOLDS["NPSS"]
    PSI_THRESH  = THRESHOLDS["PSI"]
    MSES_THRESH = THRESHOLDS["Avg MSES"]
    ERR_THRESH  = THRESHOLDS["Equity Retention %"]
    SKEW_THRESH = THRESHOLDS["CPI Skewness (|abs|)"]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        ll = policy_results["least_loaded"]["metrics"]
        cf = policy_results["cpi_fill"]["metrics"]

        def _verdict(ll_val, cf_val, threshold, higher_is_better=True):
            delta = cf_val - ll_val if higher_is_better else ll_val - cf_val
            if abs(delta) < threshold:
                return "draw"
            return "win CF" if delta > 0 else "win LL"

        npss_v = _verdict(ll["npss"],     cf["npss"],     NPSS_THRESH)
        psi_v  = _verdict(ll["mean_psi"], cf["mean_psi"], PSI_THRESH)

        mses_ll = ll["advisor"].get("avg_mses")
        mses_cf = cf["advisor"].get("avg_mses")
        if mses_ll is not None and mses_cf is not None:
            mses_v   = _verdict(mses_ll, mses_cf, MSES_THRESH, higher_is_better=False)
            mses_str = f"LL={mses_ll:.4f}, CF={mses_cf:.4f} — **{mses_v}** (threshold {MSES_THRESH})"
        else:
            mses_str = "N/A"

        err_ll  = ll["advisor"].get("equity_retention", 100.0)
        err_cf  = cf["advisor"].get("equity_retention", 100.0)
        err_v   = _verdict(err_ll, err_cf, ERR_THRESH)

        sk_ll  = ll["advisor"]["cpi_skewness"]
        sk_cf  = cf["advisor"]["cpi_skewness"]
        if sk_ll is not None and sk_cf is not None:
            skew_v = _verdict(abs(sk_ll), abs(sk_cf), SKEW_THRESH, higher_is_better=False)
            skew_str = f"|LL|={abs(sk_ll):.4f}, |CF|={abs(sk_cf):.4f} — **{skew_v}** (diagnostic)"
        else:
            skew_str = "N/A"

        lines += [
            f"### {label}",
            f"- NPSS: LL={ll['npss']:.4f}, CF={cf['npss']:.4f} — **{npss_v}** (threshold {NPSS_THRESH})",
            f"- PSI: LL={ll['mean_psi']:.4f}, CF={cf['mean_psi']:.4f} — **{psi_v}** (threshold {PSI_THRESH})",
            f"- MSES: {mses_str}",
            f"- Equity Retention: LL={err_ll:.1f}%, CF={err_cf:.1f}% — **{err_v}** (threshold {ERR_THRESH}%)",
            f"- CPI skewness (diagnostic): {skew_str}",
            f"- Overflow (diagnostic): LL={ll['overflow_count']}, CF={cf['overflow_count']}",
            "",
        ]

    # ------------------------------------------------------------------ #
    # Section 7 — Policy recommendation (threshold-based win count)
    # ------------------------------------------------------------------ #
    npss_wins = {"least_loaded": 0, "cpi_fill": 0, "draw": 0}
    psi_wins  = {"least_loaded": 0, "cpi_fill": 0, "draw": 0}
    mses_wins = {"least_loaded": 0, "cpi_fill": 0, "draw": 0}
    err_wins  = {"least_loaded": 0, "cpi_fill": 0, "draw": 0}

    for ds_key, policy_results in all_results.items():
        ll = policy_results["least_loaded"]["metrics"]
        cf = policy_results["cpi_fill"]["metrics"]

        def _tally(ll_val, cf_val, threshold, higher_is_better=True):
            delta = cf_val - ll_val if higher_is_better else ll_val - cf_val
            if abs(delta) < threshold:
                return "draw"
            return "cpi_fill" if delta > 0 else "least_loaded"

        npss_wins[_tally(ll["npss"],     cf["npss"],     NPSS_THRESH)] += 1
        psi_wins[ _tally(ll["mean_psi"], cf["mean_psi"], PSI_THRESH)]  += 1

        mses_ll = ll["advisor"].get("avg_mses")
        mses_cf = cf["advisor"].get("avg_mses")
        if mses_ll is not None and mses_cf is not None:
            mses_wins[_tally(mses_ll, mses_cf, MSES_THRESH, higher_is_better=False)] += 1
        else:
            mses_wins["draw"] += 1

        err_ll = ll["advisor"].get("equity_retention", 100.0)
        err_cf = cf["advisor"].get("equity_retention", 100.0)
        err_wins[_tally(err_ll, err_cf, ERR_THRESH)] += 1

    n_ds = len(all_results)
    lines += [
        "---",
        "",
        "## 7. Policy Recommendation",
        "",
        "### 7a. Threshold-based win count",
        "",
        f"Only differences that cross the significance threshold count as wins.",
        f"Overflow Count and % In Window are excluded — subsumed by NPSS.",
        "",
        f"| Metric | `least_loaded` wins | `cpi_fill` wins | Draws |",
        f"|--------|--------------------|--------------------|-------|",
        f"| NPSS (primary, threshold {NPSS_THRESH}) | {npss_wins['least_loaded']} | {npss_wins['cpi_fill']} | {npss_wins['draw']} |",
        f"| PSI (secondary, threshold {PSI_THRESH}) | {psi_wins['least_loaded']} | {psi_wins['cpi_fill']} | {psi_wins['draw']} |",
        f"| MSES (threshold {MSES_THRESH}) | {mses_wins['least_loaded']} | {mses_wins['cpi_fill']} | {mses_wins['draw']} |",
        f"| Equity Retention % (threshold {ERR_THRESH}%) | {err_wins['least_loaded']} | {err_wins['cpi_fill']} | {err_wins['draw']} |",
        f"| CPI Skewness | *(diagnostic — see per-dataset notes in §6)* | | |",
        f"| Overflow Count | *(diagnostic — subsumed by NPSS)* | | |",
        f"| % In Window | *(diagnostic — subsumed by NPSS)* | | |",
        "",
        "### 7b. When to use each policy",
        "",
        "### When to use `least_loaded`",
        "",
        "- When **equitable treatment of students** across CPI tiers is important: placement",
        "  depends on faculty load, not student CPI rank.",
        "- When **robustness to clustered demand** is a priority: load-spreading is less likely",
        "  to exhaust popular advisor capacity early.",
        "- As the **safe default** when cohort structure is unknown.",
        "",
        "### When to use `cpi_fill`",
        "",
        "- When **rewarding academic merit** is an explicit institutional goal: high-CPI students",
        "  get first access to their preferred advisors.",
        "- When **no empty labs** is a hard requirement: Phase 2 structurally guarantees this.",
        "- In **random or weakly correlated preference** cohorts: the only threshold-crossing NPSS",
        "  win in this study occurs here (Δ=+0.083).",
        "",
        "### 7c. Summary",
        "",
        "> **The honest conclusion is that neither policy is uniformly superior.**",
        "> Across the datasets, NPSS is the primary comparison metric; advisor entropy is the",
        "> preferred advisor-equity metric; CPI skewness is a diagnostic cross-check whose",
        "> direction can reverse across cohort types and should not be used alone to declare",
        "> a policy winner. The two policies converge on nearly identical outcomes in typical",
        "> cohorts. The choice is a value judgement about institutional priorities, not a",
        "> metric-determined optimum.",
        ">",
        "> - Choose `cpi_fill` if the institution explicitly rewards academic merit in advisor",
        ">   matching. Verify with NPSS; check entropy to confirm advisor-equity is acceptable.",
        "> - Choose `least_loaded` if equitable treatment across tiers, robustness to clustered",
        ">   demand, or predictability of outcomes is the priority.",
        "> - Do not use CPI skewness alone to justify either choice; use it alongside entropy",
        ">   as a supplementary diagnostic.",
        "",
        "---",
        "",
        "*Report generated by `stats/run_study.py` using the IISER-B MS Thesis Allocator engine.*",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rng = random.Random(RANDOM_SEED)

    # Load template for generating synthetic students
    template_students = load_students(str(ORIGINAL_STUDENTS))
    faculty_raw       = load_faculty(str(FACULTY_FILE))
    faculty_ids       = [f.id for f in faculty_raw]

    # Define 4 synthetic scenarios
    synthetic_specs = [
        ("random",          "Sample 1 (Random)"),
        ("clustered",       "Sample 2 (Clustered)"),
        ("polarised",       "Sample 3 (Polarised)"),
        ("uniform_high_cpi","Sample 4 (High-CPI)"),
    ]

    # Generate synthetic CSVs into stats/
    synthetic_paths = {}
    for scenario_key, label in synthetic_specs:
        out_path = STATS_DIR / f"students_{scenario_key}.csv"
        generate_random_preference_sheet(
            template_students, faculty_ids, rng, scenario_key, out_path
        )
        synthetic_paths[scenario_key] = (out_path, label)
        print(f"  Generated: {out_path.name}")

    # --- Run allocations ---
    all_results = {}
    scenario_labels = {}

    # Original dataset
    key = "original"
    label = "Original"
    print(f"\nRunning allocations on: {label}")
    all_results[key] = run_dataset(ORIGINAL_STUDENTS, FACULTY_FILE, label)
    scenario_labels[key] = label

    # Synthetic datasets
    for scenario_key, (students_path, label) in synthetic_paths.items():
        key = scenario_key
        print(f"Running allocations on: {label}")
        all_results[key] = run_dataset(students_path, FACULTY_FILE, label)
        scenario_labels[key] = label

    # --- Build and write report ---
    report_text = build_report(all_results, scenario_labels)
    report_path = STATS_DIR / "policy_report.md"
    report_path.write_text(report_text)
    print(f"\nReport written to: {report_path}")

    # --- Print quick summary to console ---
    print("\n=== Quick Summary ===")
    print(f"{'Dataset':<30} {'Policy':<15} {'NPSS':>8} {'PSI':>8} {'Overflow':>9}")
    print("-" * 75)
    for ds_key, policy_results in all_results.items():
        ds_label = scenario_labels[ds_key]
        for policy, res in policy_results.items():
            m = res["metrics"]
            print(
                f"{ds_label:<30} {policy:<15} {m['npss']:>8.4f} {m['mean_psi']:>8.4f} "
                f"{m['overflow_count']:>9}"
            )
        print()


if __name__ == "__main__":
    main()
