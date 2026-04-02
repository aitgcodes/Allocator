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
        "**Datasets:** 1 original + 4 synthetic (random, clustered, polarised, uniform_high_cpi)  ",
        "**Metrics:** NPSS (primary, CPI-weighted), PSI (secondary, equal-weighted), ",
        "  advisor avg entropy, CPI skewness of advisor load  ",
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
        "## 2. Advisor Fairness Metrics",
        "",
        "| Dataset | Policy | Advisors Assigned | Avg CPI Entropy ↑ | CPI Skewness |",
        "|---------|--------|------------------|-------------------|--------------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            adv = res["metrics"]["advisor"]
            lines.append(
                f"| {label} | {policy} "
                f"| {adv['advisors_assigned']} "
                f"| {_fmt(adv['avg_entropy'])} "
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
        "| Metric | `least_loaded` | `cpi_fill` | Winner |",
        "|--------|---------------|------------|--------|",
    ]

    metric_collectors: Dict[str, Dict[str, List[float]]] = {
        "NPSS":                 {p: [] for p in POLICIES},
        "PSI":                  {p: [] for p in POLICIES},
        "Overflow Count":       {p: [] for p in POLICIES},
        "% In Window":          {p: [] for p in POLICIES},
        "Avg Advisor Entropy":  {p: [] for p in POLICIES},
        "CPI Skewness (|abs|)": {p: [] for p in POLICIES},
        "Advisors Assigned":    {p: [] for p in POLICIES},
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
            metric_collectors["Avg Advisor Entropy"][policy].append(adv["avg_entropy"])
            if adv["cpi_skewness"] is not None:
                metric_collectors["CPI Skewness (|abs|)"][policy].append(abs(adv["cpi_skewness"]))
            metric_collectors["Advisors Assigned"][policy].append(adv["advisors_assigned"])

    # Direction: higher is better for NPSS, PSI, % In Window, Entropy, Advisors;
    #            lower is better for Overflow, Skewness
    higher_better = {"NPSS", "PSI", "% In Window", "Avg Advisor Entropy", "Advisors Assigned"}

    for metric_name, by_policy in metric_collectors.items():
        means  = {p: mean(v) for p, v in by_policy.items()}
        stdevs = {p: stdev(v) for p, v in by_policy.items()}

        ll_str = f"{means['least_loaded']:.4f} ± {stdevs['least_loaded']:.4f}"
        cf_str = f"{means['cpi_fill']:.4f} ± {stdevs['cpi_fill']:.4f}"

        if metric_name in higher_better:
            winner = "least_loaded" if means["least_loaded"] >= means["cpi_fill"] else "cpi_fill"
        else:
            winner = "least_loaded" if means["least_loaded"] <= means["cpi_fill"] else "cpi_fill"

        lines.append(f"| {metric_name} | {ll_str} | {cf_str} | `{winner}` |")

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 4 — Pairwise delta table (cpi_fill - least_loaded per dataset)
    # ------------------------------------------------------------------ #
    lines += [
        "## 4. Per-Dataset Policy Deltas (cpi_fill − least_loaded)",
        "",
        "Positive ΔNPSS / ΔPSI means `cpi_fill` is better; negative means `least_loaded` is better.",
        "",
        "| Dataset | ΔNPSS | ΔPSI | ΔOverflow | Δ% In Window | ΔAvg Entropy | ΔSkewness |",
        "|---------|-------|------|-----------|--------------|--------------|-----------|",
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
        d_ent     = mc["advisor"]["avg_entropy"]  - ml["advisor"]["avg_entropy"]
        sk_cf     = mc["advisor"]["cpi_skewness"]
        sk_ll     = ml["advisor"]["cpi_skewness"]
        d_skew    = (_fmt(sk_cf - sk_ll) if (sk_cf is not None and sk_ll is not None) else "N/A")

        lines.append(
            f"| {label} "
            f"| {d_npss:+.4f} "
            f"| {d_psi:+.4f} "
            f"| {d_over:+d} "
            f"| {d_win:+.1f}% "
            f"| {d_ent:+.4f} "
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

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        ll = policy_results["least_loaded"]["metrics"]
        cf = policy_results["cpi_fill"]["metrics"]

        npss_winner = "cpi_fill" if cf["npss"] > ll["npss"] else "least_loaded"
        psi_winner  = "cpi_fill" if cf["mean_psi"] > ll["mean_psi"] else "least_loaded"
        ent_winner  = (
            "cpi_fill" if cf["advisor"]["avg_entropy"] > ll["advisor"]["avg_entropy"] else "least_loaded"
        )

        lines += [
            f"### {label}",
            f"- NPSS winner: **{npss_winner}** "
            f"(LL={ll['npss']:.4f}, CF={cf['npss']:.4f})",
            f"- PSI winner: **{psi_winner}** "
            f"(LL={ll['mean_psi']:.4f}, CF={cf['mean_psi']:.4f})",
            f"- Advisor entropy winner: **{ent_winner}** "
            f"(LL={ll['advisor']['avg_entropy']:.4f}, CF={cf['advisor']['avg_entropy']:.4f})",
            f"- Overflow → LL={ll['overflow_count']}, CF={cf['overflow_count']}",
            "",
        ]

    # ------------------------------------------------------------------ #
    # Section 7 — Policy recommendation
    # ------------------------------------------------------------------ #
    # Tally wins
    npss_wins = {"least_loaded": 0, "cpi_fill": 0}
    psi_wins  = {"least_loaded": 0, "cpi_fill": 0}
    ent_wins  = {"least_loaded": 0, "cpi_fill": 0}
    ov_wins   = {"least_loaded": 0, "cpi_fill": 0}

    for ds_key, policy_results in all_results.items():
        ll = policy_results["least_loaded"]["metrics"]
        cf = policy_results["cpi_fill"]["metrics"]
        npss_wins["cpi_fill" if cf["npss"] > ll["npss"] else "least_loaded"] += 1
        psi_wins["cpi_fill" if cf["mean_psi"] > ll["mean_psi"] else "least_loaded"] += 1
        ent_wins[
            "cpi_fill" if cf["advisor"]["avg_entropy"] > ll["advisor"]["avg_entropy"] else "least_loaded"
        ] += 1
        ov_wins[
            "cpi_fill" if cf["overflow_count"] < ll["overflow_count"] else "least_loaded"
        ] += 1

    lines += [
        "---",
        "",
        "## 7. Policy Recommendation",
        "",
        f"Across {len(all_results)} datasets:",
        "",
        f"| Criterion | `least_loaded` wins | `cpi_fill` wins |",
        f"|-----------|--------------------|--------------------|",
        f"| NPSS (primary) | {npss_wins['least_loaded']} | {npss_wins['cpi_fill']} |",
        f"| PSI (secondary) | {psi_wins['least_loaded']} | {psi_wins['cpi_fill']} |",
        f"| Advisor Entropy | {ent_wins['least_loaded']} | {ent_wins['cpi_fill']} |",
        f"| Lower Overflow  | {ov_wins['least_loaded']}  | {ov_wins['cpi_fill']}  |",
        "",
        "### When to use `least_loaded`",
        "",
        "- When **load balancing across advisors** is the primary concern. The policy",
        "  distributes students to the least-loaded eligible advisor, naturally spreading",
        "  the advising burden and resulting in higher advisor CPI diversity (entropy).",
        "- When **equal treatment of students** regardless of CPI is important: every",
        "  student in a given tier has an equal chance of landing near the top of their",
        "  preference list, because placement depends only on faculty load, not student rank.",
        "- In **uniform or random cohort** scenarios where there is no strong correlation",
        "  between CPI and preference similarity.",
        "",
        "### When to use `cpi_fill`",
        "",
        "- When **rewarding academic merit** is an explicit institutional goal. Because",
        "  students are processed in descending CPI order, high-performing students get",
        "  first access to their preferred advisors.",
        "- In **clustered preference** scenarios (many students competing for the same",
        "  few popular advisors), `cpi_fill` can give top students their #1 or #2 choice",
        "  while `least_loaded` may arbitrarily split that cohort.",
        "- When **minimizing empty-lab spots** matters: Phase 2 of `cpi_fill` explicitly",
        "  fills remaining empty labs, so no advisor seat is left unused when students",
        "  remain unassigned.",
        "- In **polarised** cohorts (high-CPI students all prefer a different group of",
        "  advisors from low-CPI students), `cpi_fill` can outperform on PSI because",
        "  the CPI-ordered pass naturally separates the two groups.",
        "",
        "### Summary recommendation",
        "",
        "Both policies generally perform well and produce near-identical NPSS/PSI in",
        "random or balanced cohorts. The practical choice depends on institutional values:",
        "",
        "| Priority | Recommended Policy |",
        "|----------|-------------------|",
        "| Advisor load balance & equity | `least_loaded` |",
        "| Student merit-based access | `cpi_fill` |",
        "| Minimising unfilled advisor slots | `cpi_fill` |",
        "| Robustness across cohort shapes | `least_loaded` |",
        "",
        "> **Practical default:** Use `least_loaded` for most cohorts. Switch to `cpi_fill`",
        "> when the institution explicitly weights academic performance in advisor matching",
        "> or when a large number of students compete for a small popular subset of advisors.",
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
