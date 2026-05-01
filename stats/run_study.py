"""
run_study.py — 5-policy comparison study.

Runs least_loaded, adaptive_ll, cpi_fill, tiered_rounds, and tiered_ll on
five datasets (the sample data + 4 synthetic scenarios), collects all metrics,
and writes a Markdown report to stats/policy_report.md.

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

REPO_ROOT = Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from allocator.data_loader import load_students, load_faculty, preprocess_students
from allocator.allocation import run_full_allocation
from allocator.state import Student, Faculty

STATS_DIR = REPO_ROOT / "stats"
STATS_DIR.mkdir(exist_ok=True)

BASE_STUDENTS = REPO_ROOT / "data" / "sample_students.csv"
FACULTY_FILE  = REPO_ROOT / "data" / "sample_faculty.csv"

# test/ data lives in the main repo root (may differ from worktree root)
import subprocess as _sp
_git_common = _sp.check_output(
    ["git", "rev-parse", "--git-common-dir"],
    cwd=str(REPO_ROOT), text=True
).strip()
_main_repo = Path(_git_common).parent  # .git → repo root
TEST_DIR = _main_repo / "test"

POLICIES = ["least_loaded", "adaptive_ll", "cpi_fill", "tiered_rounds", "tiered_ll"]

# Short labels for report tables
ABBREV = {
    "least_loaded":  "LL",
    "adaptive_ll":   "ALL",
    "cpi_fill":      "CF",
    "tiered_rounds": "TR",
    "tiered_ll":     "TLL",
}

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
    n_students = len(template_students)
    n_faculty  = len(faculty_ids)
    rows = ["student_id,name,cpi," + ",".join(f"pref_{i}" for i in range(1, n_faculty + 1))]

    for tmpl in template_students:
        sid  = tmpl.id
        name = tmpl.name
        cpi  = round(rng.uniform(5.5, 10.0), 2)
        prefs = faculty_ids.copy()

        if scenario == "random":
            rng.shuffle(prefs)

        elif scenario == "clustered":
            popular = faculty_ids[:8]
            rest    = faculty_ids[8:]
            if rng.random() < 0.70:
                rng.shuffle(popular)
                rng.shuffle(rest)
                prefs = popular + rest
            else:
                rng.shuffle(prefs)

        elif scenario == "polarised":
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
            cpi = round(rng.uniform(8.0, 10.0), 2)
            rng.shuffle(prefs)

        rows.append(f"{sid},{name},{cpi}," + ",".join(prefs))

    output_path.write_text("\n".join(rows) + "\n")
    return output_path


# ---------------------------------------------------------------------------
# Run allocations
# ---------------------------------------------------------------------------

def run_dataset(students_path: Path, faculty_path: Path, label: str) -> dict:
    results = {}
    for policy in POLICIES:
        students = load_students(str(students_path))
        faculty  = load_faculty(str(faculty_path))
        import warnings
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assignments, snapshots, meta, metrics = run_full_allocation(
                students, faculty, policy=policy
            )
        n_assigned    = sum(1 for v in assignments.values() if v is not None)
        empty_labs    = sum(
            1 for fid in set(f.id for f in faculty)
            if all(a != fid for a in assignments.values())
        )
        results[policy] = {
            "assignments": assignments,
            "meta":        meta,
            "metrics":     metrics,
            "n_students":  len(students),
            "n_faculty":   len(faculty),
            "n_assigned":  n_assigned,
            "empty_labs":  empty_labs,
            "k_crit":      meta.get("k_crit_static"),
            "warnings":    [str(w.message) for w in caught],
        }
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v, decimals=4):
    if v is None:
        return "N/A"
    return f"{v:.{decimals}f}"

def _pct(v):
    return f"{v:.1f}%" if v is not None else "N/A"

def stdev(vals: List[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))

def mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0

def _best(by_policy: Dict[str, float], higher_better: bool) -> str:
    """Return the policy name with the best value."""
    if not by_policy:
        return ""
    fn = max if higher_better else min
    return fn(by_policy, key=lambda p: by_policy[p])


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(all_results: Dict[str, dict], scenario_labels: Dict[str, str]) -> str:
    lines: List[str] = []
    abbr_legend = ", ".join(f"{v} = `{k}`" for k, v in ABBREV.items())

    lines += [
        "# Allocation Policy Comparison Study — 5-Policy Matrix",
        "",
        f"**Policies:** {abbr_legend}  ",
        "**Datasets:** 2019 cohort, 2020 cohort + 4 synthetic (random, clustered, polarised, uniform_high_cpi)  ",
        "**Tie-breaking:** `tiered_rounds` and `tiered_ll` use automatic CPI tie-breaking (CLI mode)  ",
        "**Seed:** `RANDOM_SEED=42` for reproducibility  ",
        "",
        "**Metric hierarchy:**",
        "  1. NPSS — primary student metric (CPI-weighted preference satisfaction)  ",
        "  2. PSI — secondary student metric (equal-weighted)  ",
        "  3. MSES — advisor satisfaction (mean rank students placed their advisor; lower = better)  ",
        "  4. Equity Retention Rate — % of achievable load-entropy preserved; [0, 100%]  ",
        "  5. CPI Skewness — diagnostic (asymmetry in advisor mean-CPI distribution)  ",
        "",
        "---",
        "",
    ]

    # ------------------------------------------------------------------ #
    # Section 1 — Per-dataset student metrics
    # ------------------------------------------------------------------ #
    policy_header = " | ".join(f"NPSS ({ABBREV[p]}) | PSI ({ABBREV[p]})" for p in POLICIES)
    lines += [
        "## 1. Student Satisfaction — Per Dataset",
        "",
        "### 1a. NPSS and PSI (higher is better)",
        "",
    ]

    # Build a flat table: dataset × policy rows
    lines += [
        "| Dataset | Policy | NPSS ↑ | PSI ↑ | Overflow ↓ | Assigned | Empty Labs ↓ |",
        "|---------|--------|--------|-------|------------|----------|--------------|",
    ]
    for ds_key, policy_results in all_results.items():
        label = scenario_labels[ds_key]
        for policy, res in policy_results.items():
            m  = res["metrics"]
            lines.append(
                f"| {label} | {ABBREV[policy]} "
                f"| {_fmt(m['npss'])} "
                f"| {_fmt(m['mean_psi'])} "
                f"| {m['overflow_count']} "
                f"| {res['n_assigned']}/{res['n_students']} "
                f"| {res['empty_labs']} |"
            )
        lines.append("|  |  |  |  |  |  |  |")

    lines += [""]

    lines += [
        "### 1b. Per-Tier Student Satisfaction",
        "",
        "| Dataset | Policy | Tier | Count | Mean Rank ↓ | Within-Window % ↑ | Mean NPSS ↑ | Mean PSI ↑ |",
        "|---------|--------|------|-------|-------------|-------------------|-------------|------------|",
    ]
    for ds_key, policy_results in all_results.items():
        label = scenario_labels[ds_key]
        for policy, res in policy_results.items():
            per_tier = res["metrics"]["per_tier"]
            for tier in ["A", "B", "B1", "B2", "C"]:
                td = per_tier.get(tier, {})
                if not td or td.get("count", 0) == 0:
                    continue
                lines.append(
                    f"| {label} | {ABBREV[policy]} | {tier} "
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
        "## 2. Advisor Metrics — Per Dataset",
        "",
        "| Dataset | Policy | Avg MSES ↓ | Avg LUR | Equity Ret% ↑ | CPI Skewness *(diag)* |",
        "|---------|--------|-----------|---------|---------------|----------------------|",
    ]
    for ds_key, policy_results in all_results.items():
        label = scenario_labels[ds_key]
        for policy, res in policy_results.items():
            adv = res["metrics"]["advisor"]
            lines.append(
                f"| {label} | {ABBREV[policy]} "
                f"| {_fmt(adv.get('avg_mses'))} "
                f"| {_pct(adv.get('avg_lur', 0) * 100 if adv.get('avg_lur') is not None else None)} "
                f"| {adv.get('equity_retention', 100.0):.1f}% "
                f"| {_fmt(adv.get('cpi_skewness'))} |"
            )
        lines.append("|  |  |  |  |  |  |")

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 3 — tiered_ll k_crit
    # ------------------------------------------------------------------ #
    lines += [
        "## 3. `tiered_ll` Critical Round k",
        "",
        "| Dataset | k_crit | Notes |",
        "|---------|--------|-------|",
    ]
    for ds_key, policy_results in all_results.items():
        label = scenario_labels[ds_key]
        tll = policy_results.get("tiered_ll", {})
        k = tll.get("k_crit")
        warns = "; ".join(tll.get("warnings", [])) or "—"
        lines.append(f"| {label} | {k if k is not None else 'N/A'} | {warns} |")

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 4 — Aggregate mean ± std across all datasets
    # ------------------------------------------------------------------ #
    lines += [
        "## 4. Aggregate Statistics (mean ± std across 5 datasets)",
        "",
        "> Values are mean ± std across the 5 datasets. With only 5 datasets",
        "> these comparisons are descriptive, not inferential. Only 2 cohorts are real data;",
        "> significance testing would require more cohorts.",
        "",
    ]

    metric_keys = [
        ("NPSS",             True,  lambda m, adv, n: m["npss"]),
        ("PSI",              True,  lambda m, adv, n: m["mean_psi"]),
        ("Overflow",         False, lambda m, adv, n: m["overflow_count"]),
        ("% In Window",      True,  lambda m, adv, n: (1 - m["overflow_count"]/n)*100 if n else 0),
        ("Empty Labs",       False, None),  # handled separately
        ("Avg MSES",         False, lambda m, adv, n: adv.get("avg_mses")),
        ("Equity Ret%",      True,  lambda m, adv, n: adv.get("equity_retention", 100.0)),
        ("Avg LUR",          True,  lambda m, adv, n: (adv.get("avg_lur") or 0) * 100),
        ("|CPI Skewness|",   False, lambda m, adv, n: abs(adv["cpi_skewness"]) if adv["cpi_skewness"] is not None else None),
    ]

    collectors: Dict[str, Dict[str, List[float]]] = {
        name: {p: [] for p in POLICIES} for name, _, _ in metric_keys
    }
    for ds_key, policy_results in all_results.items():
        for policy, res in policy_results.items():
            m   = res["metrics"]
            adv = m["advisor"]
            n   = res["n_students"]
            for name, higher_better, fn in metric_keys:
                if name == "Empty Labs":
                    collectors[name][policy].append(res["empty_labs"])
                elif fn is not None:
                    v = fn(m, adv, n)
                    if v is not None:
                        collectors[name][policy].append(v)

    header = " | ".join(f"{ABBREV[p]}" for p in POLICIES)
    lines.append(f"| Metric | {header} | Best |")
    lines.append("|--------|" + "--------|" * len(POLICIES) + "------|")

    for name, higher_better, _ in metric_keys:
        by_policy = collectors[name]
        means_map = {p: mean(v) for p, v in by_policy.items() if v}
        row_cells = []
        for p in POLICIES:
            vals = by_policy[p]
            if vals:
                row_cells.append(f"{mean(vals):.3f} ± {stdev(vals):.3f}")
            else:
                row_cells.append("N/A")
        best = ABBREV.get(_best(means_map, higher_better), "—") if means_map else "—"
        lines.append(f"| {name} | " + " | ".join(row_cells) + f" | **{best}** |")

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 5 — Deltas vs least_loaded (baseline)
    # ------------------------------------------------------------------ #
    lines += [
        "## 5. Per-Dataset Deltas vs `least_loaded` (baseline)",
        "",
        "Positive Δ = better than LL for higher-is-better metrics; negative = worse.  ",
        "Empty labs and overflow: negative Δ = fewer (better).  ",
        "",
    ]

    other_policies = [p for p in POLICIES if p != "least_loaded"]
    delta_header = " | ".join(f"Δ{ABBREV[p]}" for p in other_policies)

    delta_metrics = [
        ("NPSS",        True,  lambda res: res["metrics"]["npss"]),
        ("PSI",         True,  lambda res: res["metrics"]["mean_psi"]),
        ("Overflow",    False, lambda res: float(res["metrics"]["overflow_count"])),
        ("Empty Labs",  False, lambda res: float(res["empty_labs"])),
        ("Equity Ret%", True,  lambda res: res["metrics"]["advisor"].get("equity_retention", 100.0)),
        ("Avg MSES",    False, lambda res: res["metrics"]["advisor"].get("avg_mses") or 0.0),
    ]
    for idx, (metric_name, higher_better, fn) in enumerate(delta_metrics):
        sub = chr(ord('a') + idx)
        lines.append(f"### 5{sub}. {metric_name}")
        lines.append("")
        lines.append(f"| Dataset | LL | {delta_header} |")
        lines.append("|---------|----" + "|--------" * len(other_policies) + "|")
        for ds_key, policy_results in all_results.items():
            label = scenario_labels[ds_key]
            ll_val = fn(policy_results["least_loaded"])
            cells = [f"{ll_val:.3f}"]
            for p in other_policies:
                if p in policy_results:
                    delta = fn(policy_results[p]) - ll_val
                    cells.append(f"{delta:+.3f}")
                else:
                    cells.append("N/A")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines += [""]

    # ------------------------------------------------------------------ #
    # Section 6 — Rank distributions
    # ------------------------------------------------------------------ #
    lines += [
        "## 6. Assigned Preference Rank Distributions",
        "",
        "| Dataset | Policy | Min | Median | Mean | Max | Std |",
        "|---------|--------|-----|--------|------|-----|-----|",
    ]
    for ds_key, policy_results in all_results.items():
        label = scenario_labels[ds_key]
        for policy, res in policy_results.items():
            ps = res["metrics"]["per_student"]
            ranks = sorted(v["assigned_rank"] for v in ps.values() if v["assigned_rank"] is not None)
            if not ranks:
                lines.append(f"| {label} | {ABBREV[policy]} | — | — | — | — | — |")
                continue
            n   = len(ranks)
            med = ranks[n // 2] if n % 2 == 1 else (ranks[n//2-1] + ranks[n//2]) / 2
            mn  = sum(ranks) / n
            sd  = math.sqrt(sum((r - mn)**2 for r in ranks) / max(n-1, 1))
            lines.append(
                f"| {label} | {ABBREV[policy]} "
                f"| {ranks[0]} | {med:.1f} | {mn:.2f} | {ranks[-1]} | {sd:.2f} |"
            )

    lines += [""]

    # ------------------------------------------------------------------ #
    # Section 7 — Win counts and recommendation
    # ------------------------------------------------------------------ #
    THRESHOLDS = {"NPSS": 0.04, "PSI": 0.025, "Avg MSES": 0.5, "Equity Ret%": 5.0}
    win_counts: Dict[str, Dict[str, int]] = {
        name: {p: 0 for p in POLICIES + ["draw"]}
        for name in THRESHOLDS
    }

    for ds_key, policy_results in all_results.items():
        metrics_by_policy = {p: res["metrics"] for p, res in policy_results.items()}
        for metric_name, threshold in THRESHOLDS.items():
            higher_better = metric_name != "Avg MSES"
            vals = {}
            for p, m in metrics_by_policy.items():
                if metric_name == "NPSS":
                    vals[p] = m["npss"]
                elif metric_name == "PSI":
                    vals[p] = m["mean_psi"]
                elif metric_name == "Avg MSES":
                    vals[p] = m["advisor"].get("avg_mses")
                elif metric_name == "Equity Ret%":
                    vals[p] = m["advisor"].get("equity_retention", 100.0)
            vals = {p: v for p, v in vals.items() if v is not None}
            if not vals:
                continue
            best_p = _best(vals, higher_better)
            best_v = vals[best_p]
            # check if best is clearly ahead of all others by threshold
            runner_up = sorted(vals.items(), key=lambda x: x[1], reverse=higher_better)
            if len(runner_up) > 1:
                second_v = runner_up[1][1]
                gap = abs(best_v - second_v)
                if gap >= threshold:
                    win_counts[metric_name][best_p] += 1
                else:
                    win_counts[metric_name]["draw"] += 1
            else:
                win_counts[metric_name][best_p] += 1

    lines += [
        "---",
        "",
        "## 7. Summary and Policy Guidance",
        "",
        "### 7a. Win counts (best policy per dataset per metric)",
        "",
        "A win is counted only when the best policy exceeds the runner-up by ≥ threshold.",
        "",
    ]
    win_header = " | ".join(ABBREV[p] for p in POLICIES)
    lines.append(f"| Metric | Threshold | {win_header} | Draw |")
    lines.append("|--------|-----------|" + "---|" * len(POLICIES) + "-----|")
    for metric_name, threshold in THRESHOLDS.items():
        wc = win_counts[metric_name]
        counts = " | ".join(str(wc[p]) for p in POLICIES)
        lines.append(f"| {metric_name} | ≥ {threshold} | {counts} | {wc['draw']} |")

    lines += [
        "",
        "### 7b. Policy guidance",
        "",
        "| Policy | Best when… | Empty-lab guarantee | Operator involvement |",
        "|--------|-----------|---------------------|----------------------|",
        "| `least_loaded` | Load balance is paramount; safe default | Indirect | None |",
        "| `adaptive_ll` | Structural empty-lab risk detected in Phase 0 | Yes (S ≥ F) | None |",
        "| `cpi_fill` | Merit-first access is an explicit goal | Yes (S ≥ F) | None |",
        "| `tiered_rounds` | Full transparency and auditability required | No | GUI: manual tie-break |",
        "| `tiered_ll` | Transparent early rounds + coverage guarantee | Yes (S ≥ F) | GUI: manual tie-break in rounds |",
        "",
        "---",
        "",
        "*Report generated by `stats/run_study.py` — IISER-B MS Thesis Allocator engine.*",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _run_policy(students, faculty, policy):
    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assignments, snapshots, meta, metrics = run_full_allocation(
            students, faculty, policy=policy
        )
    fids = {f.id for f in faculty}
    n_assigned = sum(1 for v in assignments.values() if v is not None)
    empty_labs = sum(1 for fid in fids if all(a != fid for a in assignments.values()))
    return {
        "assignments": assignments,
        "meta":        meta,
        "metrics":     metrics,
        "n_students":  len(students),
        "n_faculty":   len(faculty),
        "n_assigned":  n_assigned,
        "empty_labs":  empty_labs,
        "k_crit":      meta.get("k_crit_static"),
        "warnings":    [str(w.message) for w in caught],
    }


def _run_dataset_from_files(students_path, faculty_path, label, all_results, key, scenario_labels):
    print(f"\n[{label}]")
    all_results[key] = {}
    faculty = load_faculty(str(faculty_path))
    for p in POLICIES:
        print(f"  {p}…", end=" ", flush=True)
        students = load_students(str(students_path))
        res = _run_policy(students, faculty, p)
        all_results[key][p] = res
        print(f"NPSS={res['metrics']['npss']:.4f} empty={res['empty_labs']}")
    scenario_labels[key] = label


def _run_dataset_raw(students_raw_path, faculty_path, label, all_results, key, scenario_labels,
                     preprocessed_out: Path):
    """Load a raw Google Form export via preprocess_students, save cleaned CSV, then run."""
    print(f"\n[{label}]")
    faculty = load_faculty(str(faculty_path))
    cleaned_df, warns, _ = preprocess_students(students_raw_path, faculty)
    cleaned_df.to_csv(preprocessed_out, index=False)
    if warns:
        for w in warns:
            print(f"    [preprocess warn] {w}")
    all_results[key] = {}
    for p in POLICIES:
        print(f"  {p}…", end=" ", flush=True)
        students = load_students(str(preprocessed_out))
        res = _run_policy(students, faculty, p)
        all_results[key][p] = res
        print(f"NPSS={res['metrics']['npss']:.4f} empty={res['empty_labs']}")
    scenario_labels[key] = label


def main():
    rng = random.Random(RANDOM_SEED)

    template_students = load_students(str(BASE_STUDENTS))
    faculty_raw       = load_faculty(str(FACULTY_FILE))
    faculty_ids       = [f.id for f in faculty_raw]

    synthetic_specs = [
        ("random",           "Synthetic 1 (Random)"),
        ("clustered",        "Synthetic 2 (Clustered)"),
        ("polarised",        "Synthetic 3 (Polarised)"),
        ("uniform_high_cpi", "Synthetic 4 (High-CPI)"),
    ]

    synthetic_paths = {}
    print("Generating synthetic datasets…")
    for scenario_key, label in synthetic_specs:
        out_path = STATS_DIR / f"students_{scenario_key}.csv"
        generate_random_preference_sheet(
            template_students, faculty_ids, rng, scenario_key, out_path
        )
        synthetic_paths[scenario_key] = (out_path, label)
        print(f"  {out_path.name}")

    all_results     = {}
    scenario_labels = {}

    n_datasets = 2 + len(synthetic_specs)  # 2019, 2020, + 4 synthetic
    print(f"\nRunning {len(POLICIES)} policies × {n_datasets} datasets…")

    # Real cohort data — 2019
    _run_dataset_raw(
        TEST_DIR / "2019" / "anonymized_preferences.csv",
        TEST_DIR / "2019" / "faculty.csv",
        "2019 Cohort",
        all_results, "2019", scenario_labels,
        preprocessed_out=STATS_DIR / "students_2019_cleaned.csv",
    )

    # Real cohort data — 2020
    _run_dataset_raw(
        TEST_DIR / "2020" / "anonymized_preferences.csv",
        TEST_DIR / "2020" / "faculty.csv",
        "2020 Cohort",
        all_results, "2020", scenario_labels,
        preprocessed_out=STATS_DIR / "students_2020_cleaned.csv",
    )

    # Synthetic datasets
    for scenario_key, (students_path, label) in synthetic_paths.items():
        _run_dataset_from_files(
            students_path, FACULTY_FILE, label,
            all_results, scenario_key, scenario_labels,
        )

    print("\nBuilding report…")
    report_text = build_report(all_results, scenario_labels)
    report_path = STATS_DIR / "policy_report.md"
    report_path.write_text(report_text)
    print(f"Report written to: {report_path}")

    # Quick console summary
    print(f"\n{'Dataset':<26} {'Policy':<15} {'NPSS':>8} {'PSI':>8} {'Overflow':>9} {'Empty':>6}")
    print("-" * 80)
    for ds_key, policy_results in all_results.items():
        ds_label = scenario_labels[ds_key]
        for policy, res in policy_results.items():
            m = res["metrics"]
            k = f" k={res['k_crit']}" if res["k_crit"] is not None else ""
            print(
                f"{ds_label:<26} {policy:<15} {m['npss']:>8.4f} {m['mean_psi']:>8.4f} "
                f"{m['overflow_count']:>9} {res['empty_labs']:>6}{k}"
            )
        print()


if __name__ == "__main__":
    main()
