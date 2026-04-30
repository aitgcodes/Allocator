"""
analyze.py — Post-allocation analysis and cross-policy comparison CLI.

Usage:
    python -m allocator.analyze metrics  --students S --faculty F --result R [--out DIR]
    python -m allocator.analyze compare  --students S --faculty F [--policies P...] [--auto-tiebreak] [--out DIR] [--format md|json|csv]
    python -m allocator.analyze study    --students S --faculty F [--synthetic-seeds N...] [--policies P...] [--auto-tiebreak] [--out DIR]
"""

from __future__ import annotations

import copy
import csv
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v, decimals=4):
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


def _stdev(vals: List[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    return math.sqrt(sum((x - mean) ** 2 for x in vals) / (len(vals) - 1))


def _mean(vals: List[float]) -> float:
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


# ---------------------------------------------------------------------------
# Subcommand: metrics
# ---------------------------------------------------------------------------

def cmd_metrics(args) -> None:
    """Load an assignment CSV, recompute metrics, print table, write metrics.json."""
    from .data_loader import load_students, load_faculty
    from .metrics import compute_metrics

    students = load_students(args.students)
    faculty  = load_faculty(args.faculty)

    # Build student map for tier/n_tier info from Phase 0
    # We need to run Phase 0 to set student tiers before computing metrics.
    from .allocation import phase0
    students, faculty, meta, _ = phase0(students, faculty)

    # Load assignment CSV
    student_map = {s.id: s for s in students}
    faculty_map = {f.id: f for f in faculty}
    assignments: Dict[str, Optional[str]] = {s.id: None for s in students}

    with open(args.result, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            sid = row.get("student_id", "").strip()
            fid = row.get("assigned_faculty_id", "").strip()
            if sid in assignments:
                assignments[sid] = fid if fid else None

    metrics = compute_metrics(
        students, assignments,
        F=len(faculty),
        faculty_ids=[f.id for f in faculty],
        faculty=faculty,
    )

    # Print formatted table
    npss      = metrics["npss"]
    mean_psi  = metrics["mean_psi"]
    overflow  = metrics["overflow_count"]
    advisor   = metrics.get("advisor", {})
    empty_labs = advisor.get("empty_labs", "N/A")
    avg_mses  = advisor.get("avg_mses")
    avg_lur   = advisor.get("avg_lur")
    err       = advisor.get("equity_retention", 0.0)
    cpi_skew  = advisor.get("cpi_skewness")
    assigned  = sum(1 for v in assignments.values() if v is not None)

    print()
    print(f"{'Assigned':<16}: {assigned} / {len(students)}")
    print(f"{'Empty labs':<16}: {empty_labs}")
    print(f"{'NPSS':<16}: {npss:.4f}")
    print(f"{'PSI':<16}: {mean_psi:.4f}")
    print(f"{'Overflow count':<16}: {overflow}")
    if avg_mses is not None:
        print(f"{'Avg MSES':<16}: {avg_mses:.4f}")
    if avg_lur is not None:
        print(f"{'Avg LUR':<16}: {avg_lur*100:.1f}%")
    print(f"{'Equity Retention':<16}: {err:.1f}%")
    if cpi_skew is not None:
        print(f"{'CPI Skewness':<16}: {cpi_skew:.4f}")

    out_dir = getattr(args, "out", None) or "."
    os.makedirs(out_dir, exist_ok=True)
    metrics_path = os.path.join(out_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, default=str, indent=2)
    print(f"\nMetrics written to: {metrics_path}")


# ---------------------------------------------------------------------------
# Subcommand: compare
# ---------------------------------------------------------------------------

ALL_POLICIES = ["least_loaded", "adaptive_ll", "nonempty", "cpi_fill",
                "tiered_rounds", "tiered_ll"]
INTERACTIVE_POLICIES = {"tiered_rounds", "tiered_ll"}


def _run_policy(students_path: str, faculty_path: str, policy: str,
                auto_tiebreak: bool) -> dict:
    """Run a single policy on the given data. Returns result dict."""
    from .data_loader import load_students, load_faculty
    from .allocation import run_full_allocation

    students = load_students(students_path)
    faculty  = load_faculty(faculty_path)
    assignments, snapshots, meta, metrics = run_full_allocation(
        students, faculty, policy=policy, auto_tiebreak=auto_tiebreak
    )
    assigned = sum(1 for v in assignments.values() if v is not None)
    return {
        "assignments": assignments,
        "meta":        meta,
        "metrics":     metrics,
        "n_students":  len(students),
        "n_faculty":   len(faculty),
        "assigned":    assigned,
    }


def _build_comparison_table(policy_results: Dict[str, dict]) -> List[str]:
    """Build comparison table lines (Markdown)."""
    lines = [
        "| Policy | Assigned | Empty labs | NPSS | PSI | MSES | LUR | ERR | CPI skew | Notes |",
        "|--------|----------|------------|------|-----|------|-----|-----|----------|-------|",
    ]
    for policy, res in policy_results.items():
        m   = res["metrics"]
        adv = m.get("advisor", {})
        n   = res["n_students"]
        assigned = res["assigned"]
        empty_labs = adv.get("empty_labs", "?")
        npss  = m["npss"]
        psi   = m["mean_psi"]
        mses  = adv.get("avg_mses")
        lur   = adv.get("avg_lur")
        err   = adv.get("equity_retention", 0.0)
        skew  = adv.get("cpi_skewness")

        notes_parts = []
        if assigned < n:
            notes_parts.append(f"stall ({n - assigned} unassigned)")
        k_crit = res["meta"].get("k_crit_static")
        if k_crit is not None:
            notes_parts.append(f"k_crit={k_crit}")
        notes = "; ".join(notes_parts) if notes_parts else ""

        mses_str = f"{mses:.3f}" if mses is not None else "N/A"
        lur_str  = f"{lur*100:.1f}%" if lur is not None else "N/A"
        skew_str = f"{skew:.3f}" if skew is not None else "N/A"

        lines.append(
            f"| {policy} | {assigned}/{n} | {empty_labs} "
            f"| {npss:.3f} | {psi:.3f} | {mses_str} | {lur_str} "
            f"| {err:.1f}% | {skew_str} | {notes} |"
        )
    return lines


def cmd_compare(args) -> None:
    """Run multiple policies on the same cohort and compare."""
    policies = getattr(args, "policies", None) or ALL_POLICIES
    auto_tiebreak = getattr(args, "auto_tiebreak", False)
    out_dir = getattr(args, "out", None) or "."
    fmt = getattr(args, "format", "md")

    # Validate
    for p in policies:
        if p in INTERACTIVE_POLICIES and not auto_tiebreak:
            print(
                f"Error: policy '{p}' requires --auto-tiebreak for CLI use."
            )
            sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)

    policy_results: Dict[str, dict] = {}
    for policy in policies:
        print(f"Running policy: {policy} ...", flush=True)
        try:
            policy_results[policy] = _run_policy(
                args.students, args.faculty, policy, auto_tiebreak
            )
        except Exception as exc:
            print(f"  WARNING: policy '{policy}' failed: {exc}")
            continue

    # Print table to stdout
    table_lines = _build_comparison_table(policy_results)
    print()
    print("Policy Comparison")
    print("=================")
    for line in table_lines:
        print(line)

    # Write comparison_report.md
    report_lines = [
        "# Policy Comparison Report",
        "",
        f"Students: `{args.students}`  ",
        f"Faculty: `{args.faculty}`  ",
        "",
        "## Results",
        "",
    ] + table_lines + [""]

    report_path = os.path.join(out_dir, "comparison_report.md")
    Path(report_path).write_text("\n".join(report_lines))
    print(f"\nReport written to: {report_path}")

    # Write comparison_report.json if requested
    if fmt in ("json",):
        json_data = {}
        for policy, res in policy_results.items():
            json_data[policy] = {
                "assigned": res["assigned"],
                "n_students": res["n_students"],
                "n_faculty": res["n_faculty"],
                "meta": res["meta"],
                "metrics": res["metrics"],
            }
        json_path = os.path.join(out_dir, "comparison_report.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(json_data, fh, default=str, indent=2)
        print(f"JSON report written to: {json_path}")


# ---------------------------------------------------------------------------
# Subcommand: study
# ---------------------------------------------------------------------------

def _generate_random_preference_sheet(
    template_students,
    faculty_ids: List[str],
    rng: random.Random,
    scenario: str,
    output_path: Path,
) -> Path:
    """Generate a random preference sheet CSV."""
    n_faculty = len(faculty_ids)
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
        else:
            rng.shuffle(prefs)

        row = f"{sid},{name},{cpi}," + ",".join(prefs)
        rows.append(row)

    output_path.write_text("\n".join(rows) + "\n")
    return output_path


def _build_study_report(
    all_results: Dict[str, Dict[str, dict]],
    scenario_labels: Dict[str, str],
    policies: List[str],
) -> str:
    lines: List[str] = [
        "# Allocation Policy Comparison Study",
        "",
        f"**Policies compared:** {', '.join(f'`{p}`' for p in policies)}  ",
        f"**Datasets:** {len(all_results)} (original + synthetic)  ",
        "",
        "---",
        "",
        "## Per-Dataset Metric Summary",
        "",
        "| Dataset | Policy | Assigned | Empty labs | NPSS | PSI | Overflow |",
        "|---------|--------|----------|------------|------|-----|----------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            m = res["metrics"]
            adv = m.get("advisor", {})
            lines.append(
                f"| {label} | {policy} "
                f"| {res['assigned']}/{res['n_students']} "
                f"| {adv.get('empty_labs', '?')} "
                f"| {m['npss']:.4f} "
                f"| {m['mean_psi']:.4f} "
                f"| {m['overflow_count']} |"
            )

    lines += [
        "",
        "## Advisor Metrics",
        "",
        "| Dataset | Policy | MSES | LUR | Equity Retention % | CPI Skewness |",
        "|---------|--------|------|-----|--------------------|--------------|",
    ]

    for ds_key, policy_results in all_results.items():
        label = scenario_labels.get(ds_key, ds_key)
        for policy, res in policy_results.items():
            adv = res["metrics"].get("advisor", {})
            mses = adv.get("avg_mses")
            lur  = adv.get("avg_lur")
            err  = adv.get("equity_retention", 0.0)
            skew = adv.get("cpi_skewness")
            lines.append(
                f"| {label} | {policy} "
                f"| {_fmt(mses)} "
                f"| {f'{lur*100:.1f}%' if lur is not None else 'N/A'} "
                f"| {err:.1f}% "
                f"| {_fmt(skew)} |"
            )

    lines += [
        "",
        "---",
        "",
        "*Report generated by `allocator.analyze study`.*",
    ]
    return "\n".join(lines)


def cmd_study(args) -> None:
    """Subsume stats/run_study.py logic: run policies on real + synthetic datasets."""
    from .data_loader import load_students, load_faculty
    from .allocation import run_full_allocation

    policies      = getattr(args, "policies", None) or ["least_loaded", "cpi_fill"]
    auto_tiebreak = getattr(args, "auto_tiebreak", False)
    out_dir       = getattr(args, "out", None) or "stats/"
    seeds         = getattr(args, "synthetic_seeds", None) or [42, 7, 13, 99]

    # Validate
    for p in policies:
        if p in INTERACTIVE_POLICIES and not auto_tiebreak:
            print(f"Error: policy '{p}' requires --auto-tiebreak for CLI use.")
            sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)

    template_students = load_students(args.students)
    faculty_raw       = load_faculty(args.faculty)
    faculty_ids       = [f.id for f in faculty_raw]

    scenario_names = ["random", "clustered", "polarised", "uniform_high_cpi"]
    scenario_labels_map = {
        "random":           "Synthetic (Random)",
        "clustered":        "Synthetic (Clustered)",
        "polarised":        "Synthetic (Polarised)",
        "uniform_high_cpi": "Synthetic (High-CPI)",
    }

    synthetic_paths: Dict[str, Tuple[Path, str]] = {}
    for scenario, seed in zip(scenario_names, seeds):
        rng = random.Random(seed)
        out_path = Path(out_dir) / f"students_{scenario}.csv"
        _generate_random_preference_sheet(
            template_students, faculty_ids, rng, scenario, out_path
        )
        synthetic_paths[scenario] = (out_path, scenario_labels_map.get(scenario, scenario))
        print(f"  Generated: {out_path.name}")

    all_results: Dict[str, Dict[str, dict]] = {}
    scenario_labels: Dict[str, str] = {}

    # Original dataset
    key = "original"
    scenario_labels[key] = "Original"
    print(f"\nRunning allocations on: Original ({args.students})")
    all_results[key] = {}
    for policy in policies:
        print(f"  Policy: {policy} ...", flush=True)
        try:
            all_results[key][policy] = _run_policy(
                args.students, args.faculty, policy, auto_tiebreak
            )
        except Exception as exc:
            print(f"  WARNING: {exc}")

    # Synthetic datasets
    for scenario, (spath, label) in synthetic_paths.items():
        key = scenario
        scenario_labels[key] = label
        print(f"\nRunning allocations on: {label}")
        all_results[key] = {}
        for policy in policies:
            print(f"  Policy: {policy} ...", flush=True)
            try:
                all_results[key][policy] = _run_policy(
                    str(spath), args.faculty, policy, auto_tiebreak
                )
            except Exception as exc:
                print(f"  WARNING: {exc}")

    report_text = _build_study_report(all_results, scenario_labels, policies)
    report_path = Path(out_dir) / "policy_report.md"
    report_path.write_text(report_text)
    print(f"\nReport written to: {report_path}")

    # Quick console summary
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


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        description="Post-allocation analysis and cross-policy comparison.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # ---- metrics ----
    p_metrics = subparsers.add_parser(
        "metrics",
        help="Recompute metrics from an existing assignment CSV.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_metrics.add_argument("--students", required=True, help="Path to students CSV")
    p_metrics.add_argument("--faculty",  required=True, help="Path to faculty CSV")
    p_metrics.add_argument("--result",   required=True,
                           help="Assignment CSV (must have student_id + assigned_faculty_id columns)")
    p_metrics.add_argument("--out", default=".", help="Output directory (default: .)")

    # ---- compare ----
    p_compare = subparsers.add_parser(
        "compare",
        help="Run multiple policies on the same cohort and compare.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_compare.add_argument("--students", required=True, help="Path to students CSV")
    p_compare.add_argument("--faculty",  required=True, help="Path to faculty CSV")
    p_compare.add_argument(
        "--policies", nargs="+", default=None,
        choices=ALL_POLICIES,
        metavar="POLICY",
        help=(
            "Policies to compare (default: all five).\n"
            f"Choices: {', '.join(ALL_POLICIES)}"
        ),
    )
    p_compare.add_argument(
        "--auto-tiebreak", action="store_true",
        help="Auto-resolve tiered_rounds/tiered_ll ties by highest CPI.",
    )
    p_compare.add_argument("--out", default=".", help="Output directory (default: .)")
    p_compare.add_argument(
        "--format", choices=["md", "json", "csv"], default="md",
        help="Output format (default: md).",
    )

    # ---- study ----
    p_study = subparsers.add_parser(
        "study",
        help="Run policy study on real + synthetic datasets (replaces stats/run_study.py).",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_study.add_argument("--students", required=True, help="Path to real students CSV")
    p_study.add_argument("--faculty",  required=True, help="Path to faculty CSV")
    p_study.add_argument(
        "--synthetic-seeds", nargs="+", type=int, default=None, metavar="SEED",
        help="RNG seeds for synthetic datasets (default: 42 7 13 99).",
    )
    p_study.add_argument(
        "--policies", nargs="+", default=None,
        choices=ALL_POLICIES,
        metavar="POLICY",
        help=(
            f"Policies to run (default: least_loaded cpi_fill).\n"
            f"Choices: {', '.join(ALL_POLICIES)}"
        ),
    )
    p_study.add_argument(
        "--auto-tiebreak", action="store_true",
        help="Auto-resolve tiered_rounds/tiered_ll ties by highest CPI.",
    )
    p_study.add_argument("--out", default="stats/", help="Output directory (default: stats/)")

    return parser


def _cli():
    parser = _build_parser()
    args = parser.parse_args()

    # Normalise hyphen → underscore for auto_tiebreak
    if hasattr(args, "auto_tiebreak"):
        pass  # already set by argparse dest
    if not hasattr(args, "auto_tiebreak"):
        args.auto_tiebreak = False

    if args.subcommand == "metrics":
        cmd_metrics(args)
    elif args.subcommand == "compare":
        cmd_compare(args)
    elif args.subcommand == "study":
        cmd_study(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    _cli()
