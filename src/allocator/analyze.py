"""
analyze.py — Post-allocation metrics and multi-policy comparison CLI.

Subcommands
-----------
  metrics  : compute metrics for an existing allocation result
  compare  : run multiple policies on one dataset and compare
  study    : multi-dataset study (synthetic + optional real cohorts)

Usage
-----
  python -m allocator.analyze metrics \\
      --students data/students.csv \\
      --faculty  data/faculty.csv  \\
      --result   reports/allocation_result.csv \\
      [--out     reports/]

  python -m allocator.analyze compare \\
      --students data/students.csv \\
      --faculty  data/faculty.csv  \\
      [--policies least_loaded adaptive_ll cpi_fill tiered_rounds tiered_ll] \\
      [--out      reports/comparison/] \\
      [--format   md | json | csv]

  python -m allocator.analyze study \\
      --students data/students.csv \\
      --faculty  data/faculty.csv  \\
      [--policies least_loaded adaptive_ll cpi_fill] \\
      [--real-data students:faculty:label[:raw] ...] \\
      [--out     stats/]
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

_POLICIES_ALL = ["least_loaded", "adaptive_ll", "cpi_fill", "tiered_rounds", "tiered_ll"]
_ABBREV = {
    "least_loaded":  "LL",
    "adaptive_ll":   "ALL",
    "cpi_fill":      "CF",
    "tiered_rounds": "TR",
    "tiered_ll":     "TLL",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _fmt(v, d: int = 4) -> str:
    return f"{v:.{d}f}" if v is not None else "N/A"


def _run_one_policy(students_path: str, faculty_path: str, policy: str) -> dict:
    import warnings
    from .data_loader import load_students, load_faculty
    from .allocation import run_full_allocation

    students = load_students(str(students_path))
    faculty  = load_faculty(str(faculty_path))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assignments, _, meta, metrics = run_full_allocation(
            students, faculty, policy=policy
        )
    fids       = {f.id for f in faculty}
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


def _strip_tier_counts(metrics: dict) -> dict:
    """Return a JSON-safe copy of a metrics dict (removes tier_counts from per_faculty)."""
    out = dict(metrics)
    if "advisor" in out:
        adv = dict(out["advisor"])
        adv["per_faculty"] = {
            fid: {k: v for k, v in fd.items() if k != "tier_counts"}
            for fid, fd in adv.get("per_faculty", {}).items()
        }
        out["advisor"] = adv
    return out


# ---------------------------------------------------------------------------
# metrics subcommand
# ---------------------------------------------------------------------------

def cmd_metrics(args) -> None:
    from .data_loader import load_students, load_faculty
    from .allocation import phase0
    from .metrics import compute_metrics

    students = load_students(args.students)
    faculty  = load_faculty(args.faculty)

    # Load the allocation result CSV.
    assignments: Dict[str, Optional[str]] = {}
    with open(args.result, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            fid = row.get("faculty_id", "").strip()
            assignments[row["student_id"]] = fid if fid else None

    # Phase 0 sets tier / n_tier on students (deterministic; independent of policy).
    students, faculty, _, _ = phase0(students, faculty)

    metrics = compute_metrics(students, assignments, F=len(faculty), faculty=faculty)
    adv = metrics.get("advisor", {})

    print(f"NPSS              : {metrics['npss']:.4f}")
    print(f"PSI               : {metrics['mean_psi']:.4f}")
    print(f"Overflow          : {metrics['overflow_count']}")
    print(f"Empty labs        : {adv.get('empty_labs', 'N/A')}")
    print(f"MSES (avg)        : {_fmt(adv.get('avg_mses'))}")
    lur = adv.get("avg_lur")
    print(f"LUR (avg)         : {f'{lur*100:.1f}%' if lur is not None else 'N/A'}")
    eq = adv.get("equity_retention")
    print(f"Equity Retention  : {f'{eq:.1f}%' if eq is not None else 'N/A'}")
    print(f"CPI Skewness      : {_fmt(adv.get('cpi_skewness'))}")

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        metrics_path = os.path.join(args.out, "metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as fh:
            json.dump(_strip_tier_counts(metrics), fh, indent=2)
        print(f"\nMetrics written to: {metrics_path}")


# ---------------------------------------------------------------------------
# compare subcommand
# ---------------------------------------------------------------------------

def _build_comparison_report(
    results: Dict[str, dict],
    policies: List[str],
    label: str,
) -> str:
    lines: List[str] = []
    lines.append(f"# Comparison Report — {label}")
    lines.append("")

    abbrev_legend = "  ".join(f"`{p}` ({_ABBREV.get(p, p)})" for p in policies)
    lines.append(f"**Policies:** {abbrev_legend}  ")
    if results:
        first = next(v for v in results.values() if v)
        lines.append(f"**Cohort:** S={first['n_students']}, F={first['n_faculty']}  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Student satisfaction
    lines.append("## Student Satisfaction")
    lines.append("")
    lines.append("| Policy | NPSS ↑ | PSI ↑ | Overflow ↓ | Assigned | Empty Labs ↓ |")
    lines.append("|--------|--------|-------|------------|----------|--------------|")

    best_npss = max(
        (results[p]["metrics"]["npss"] for p in policies if p in results),
        default=None,
    )
    for policy in policies:
        if policy not in results:
            continue
        res = results[policy]
        m   = res["metrics"]
        flag = " **★**" if (best_npss is not None and m["npss"] == best_npss) else ""
        lines.append(
            f"| {_ABBREV.get(policy, policy)} "
            f"| {_fmt(m['npss'])}{flag} "
            f"| {_fmt(m['mean_psi'])} "
            f"| {m['overflow_count']} "
            f"| {res['n_assigned']}/{res['n_students']} "
            f"| {res['empty_labs']} |"
        )
    lines.append("")

    # Advisor metrics
    lines.append("## Advisor Metrics")
    lines.append("")
    lines.append("| Policy | Avg MSES ↓ | Avg LUR | Equity Ret% ↑ | CPI Skewness |")
    lines.append("|--------|-----------|---------|---------------|--------------|")
    for policy in policies:
        if policy not in results:
            continue
        adv = results[policy]["metrics"]["advisor"]
        lur = adv.get("avg_lur")
        eq  = adv.get("equity_retention")
        lines.append(
            f"| {_ABBREV.get(policy, policy)} "
            f"| {_fmt(adv.get('avg_mses'))} "
            f"| {f'{lur*100:.1f}%' if lur is not None else 'N/A'} "
            f"| {f'{eq:.1f}%' if eq is not None else 'N/A'} "
            f"| {_fmt(adv.get('cpi_skewness'))} |"
        )
    lines.append("")

    # tiered_ll k_crit
    tll = results.get("tiered_ll")
    if tll and tll.get("k_crit") is not None:
        lines.append(f"**tiered_ll k_crit:** {tll['k_crit']}  ")
        lines.append("")

    # Warnings
    warns = [
        f"- `{p}`: {w}"
        for p in policies if p in results
        for w in results[p].get("warnings", [])
    ]
    if warns:
        lines.append("## Warnings")
        lines.append("")
        lines += warns
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Generated by `python -m allocator.analyze compare`*")
    return "\n".join(lines)


def cmd_compare(args) -> None:
    policies = args.policies or _POLICIES_ALL

    # tiered_rounds / tiered_ll use auto CPI tie-breaking inside run_full_allocation.
    interactive = [p for p in policies if p in ("tiered_rounds", "tiered_ll")]
    if interactive:
        print(
            f"Note: {', '.join(interactive)} use automatic CPI tie-breaking in CLI mode.",
            file=sys.stderr,
        )

    print(f"Running {len(policies)} policies on {args.students}…")
    results: Dict[str, dict] = {}
    for policy in policies:
        print(f"  {policy}…", end=" ", flush=True)
        try:
            res = _run_one_policy(args.students, args.faculty, policy)
            results[policy] = res
            m = res["metrics"]
            print(f"NPSS={m['npss']:.4f}  empty={res['empty_labs']}")
        except Exception as exc:
            print(f"FAILED: {exc}", file=sys.stderr)

    label       = Path(args.students).stem
    report_text = _build_comparison_report(results, policies, label)

    if not args.out:
        print(report_text)
        return

    os.makedirs(args.out, exist_ok=True)

    report_path = os.path.join(args.out, "comparison_report.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_text)
    print(f"\nComparison report    : {report_path}")

    if args.format in ("json",):
        out_data = {
            policy: {
                "npss":           res["metrics"]["npss"],
                "mean_psi":       res["metrics"]["mean_psi"],
                "overflow_count": res["metrics"]["overflow_count"],
                "n_assigned":     res["n_assigned"],
                "n_students":     res["n_students"],
                "n_faculty":      res["n_faculty"],
                "empty_labs":     res["empty_labs"],
                "k_crit":         res["k_crit"],
                "advisor": {
                    k: v for k, v in res["metrics"]["advisor"].items()
                    if k != "per_faculty"
                },
            }
            for policy, res in results.items()
        }
        json_path = os.path.join(args.out, "comparison_report.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(out_data, fh, indent=2)
        print(f"Comparison (JSON)    : {json_path}")

    if args.format in ("csv",):
        csv_path = os.path.join(args.out, "comparison_report.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "policy", "npss", "mean_psi", "overflow_count",
                "n_assigned", "n_students", "n_faculty", "empty_labs",
                "avg_mses", "avg_lur", "equity_retention", "cpi_skewness",
                "k_crit",
            ])
            for policy in policies:
                if policy not in results:
                    continue
                res = results[policy]
                m   = res["metrics"]
                adv = m["advisor"]
                lur = adv.get("avg_lur")
                eq  = adv.get("equity_retention")
                writer.writerow([
                    policy,
                    f"{m['npss']:.6f}",
                    f"{m['mean_psi']:.6f}",
                    m["overflow_count"],
                    res["n_assigned"],
                    res["n_students"],
                    res["n_faculty"],
                    res["empty_labs"],
                    _fmt(adv.get("avg_mses")),
                    f"{lur:.4f}" if lur is not None else "",
                    f"{eq:.2f}" if eq is not None else "",
                    _fmt(adv.get("cpi_skewness")),
                    res["k_crit"] if res["k_crit"] is not None else "",
                ])
        print(f"Comparison (CSV)     : {csv_path}")


# ---------------------------------------------------------------------------
# study subcommand
# ---------------------------------------------------------------------------

def cmd_study(args) -> None:
    policies = args.policies or _POLICIES_ALL

    # Import run_study_with_params from stats/run_study.py.
    repo_root = Path(__file__).parent.parent.parent
    stats_dir = str(repo_root / "stats")
    if stats_dir not in sys.path:
        sys.path.insert(0, stats_dir)

    try:
        import run_study as rs
    except ImportError as exc:
        print(f"Error: cannot import stats/run_study.py: {exc}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)

    # Parse --real-data entries: "students_path:faculty_path:label[:raw]"
    real_datasets = []
    if args.real_data:
        for entry in args.real_data:
            parts = entry.split(":")
            if len(parts) < 3:
                print(
                    f"Warning: --real-data {entry!r} must be students:faculty:label[:raw]",
                    file=sys.stderr,
                )
                continue
            sp, fp, label = parts[0], parts[1], parts[2]
            is_raw = len(parts) > 3 and parts[3].lower() == "raw"
            real_datasets.append((sp, fp, label, is_raw))

    if hasattr(rs, "run_study_with_params"):
        rs.run_study_with_params(
            base_students_path=Path(args.students),
            faculty_path=Path(args.faculty),
            out_dir=out_dir,
            policies=policies,
            real_datasets=real_datasets,
        )
    else:
        # Fallback: call main() with hardcoded defaults from run_study.py.
        print(
            "Note: run_study.run_study_with_params() not found; calling main() with defaults.",
            file=sys.stderr,
        )
        rs.main()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m allocator.analyze",
        description="Post-allocation metrics and multi-policy comparison.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── metrics ──────────────────────────────────────────────────────────────
    p_metrics = sub.add_parser(
        "metrics",
        help="Compute metrics for an existing allocation result.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_metrics.add_argument("--students", required=True, help="Students CSV/Excel")
    p_metrics.add_argument("--faculty",  required=True, help="Faculty CSV/Excel")
    p_metrics.add_argument(
        "--result", required=True,
        help="allocation_result.csv produced by a prior allocation run.",
    )
    p_metrics.add_argument(
        "--out", default=None,
        help="Write metrics.json to this directory (omit to suppress file output).",
    )

    # ── compare ──────────────────────────────────────────────────────────────
    p_compare = sub.add_parser(
        "compare",
        help="Run multiple policies on one dataset and produce a comparison report.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_compare.add_argument("--students", required=True, help="Students CSV/Excel")
    p_compare.add_argument("--faculty",  required=True, help="Faculty CSV/Excel")
    p_compare.add_argument(
        "--policies",
        nargs="+",
        choices=_POLICIES_ALL,
        metavar="POLICY",
        default=None,
        help="Policies to compare (default: all five).",
    )
    p_compare.add_argument(
        "--out", default=None,
        help="Output directory for comparison_report.md (prints to stdout if omitted).",
    )
    p_compare.add_argument(
        "--format",
        choices=["md", "json", "csv"],
        default="md",
        metavar="FMT",
        help=(
            "Additional output format alongside the Markdown report.\n"
            "  md  : Markdown only (default)\n"
            "  json: Markdown + comparison_report.json\n"
            "  csv : Markdown + comparison_report.csv"
        ),
    )

    # ── study ─────────────────────────────────────────────────────────────────
    p_study = sub.add_parser(
        "study",
        help=(
            "Multi-dataset comparison study: generates synthetic datasets and\n"
            "optionally includes real cohorts. Produces policy_report.md in --out.\n"
            "Delegates to stats/run_study.py (run_study_with_params)."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_study.add_argument(
        "--students", required=True,
        help="Base students CSV for synthetic dataset generation.",
    )
    p_study.add_argument("--faculty", required=True, help="Faculty CSV")
    p_study.add_argument(
        "--policies",
        nargs="+",
        choices=_POLICIES_ALL,
        metavar="POLICY",
        default=None,
        help="Policies to run (default: all five).",
    )
    p_study.add_argument(
        "--real-data",
        nargs="+",
        metavar="S:F:LABEL[:raw]",
        default=None,
        help=(
            "Real cohort dataset(s) to include alongside synthetic data.\n"
            "Format: students_path:faculty_path:label[:raw]\n"
            "  raw = preprocess via preprocess_students (Google Form export)."
        ),
    )
    p_study.add_argument(
        "--out", default="stats",
        help="Output directory for policy_report.md (default: stats/).",
    )

    args = parser.parse_args()
    if args.command == "metrics":
        cmd_metrics(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "study":
        cmd_study(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    _cli()
