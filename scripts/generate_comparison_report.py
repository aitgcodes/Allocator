#!/usr/bin/env python3
"""
Generate multi-policy allocation comparison report for 2019 and 2020 cohorts.
Policies: cpi_fill, least_loaded, tiered_rounds
Output: test/allocation_comparison_2019_2020.md
"""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from allocator.allocation import (
    phase0,
    run_full_allocation,
    tiered_rounds_resume,
    tiered_rounds_start,
)
from allocator.data_loader import load_faculty
from allocator.metrics import compute_metrics
from allocator.state import Student

POLICIES = ["cpi_fill", "least_loaded", "tiered_rounds"]
POLICY_LABELS = {
    "cpi_fill": "CPI-Fill",
    "least_loaded": "Least Loaded",
    "tiered_rounds": "Tiered Rounds",
}
YEAR_DIRS = {
    "2019": ROOT / "test" / "2019",
    "2020": ROOT / "test" / "2020",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_anonymized_students(
    students_path: Path,
    faculty_ids: list[str],
    original_pref_counts: dict[str, int] | None = None,
) -> list[Student]:
    """
    Load anonymized_preferences.csv into Student objects.

    - Uses student_name as student ID
    - Fixes CPI "8.93/10" → 8.93
    - Backfills preferences with remaining faculty in sorted order so that
      tiered_rounds and main_allocation always have a complete ranking.
    - Optionally records original (pre-backfill) pref counts into *original_pref_counts*.
    """
    df = pd.read_csv(students_path)
    pref_cols = sorted(
        [c for c in df.columns if c.startswith("pref_")],
        key=lambda c: int(c.split("_")[1]),
    )
    fac_set = set(faculty_ids)
    sorted_fac = sorted(faculty_ids)

    students = []
    for _, row in df.iterrows():
        sid = str(row["student_name"]).strip()

        cpi_raw = str(row["cpi"]).strip()
        if "/" in cpi_raw:
            cpi_raw = cpi_raw.split("/")[0]
        cpi = float(cpi_raw)

        explicit = [
            str(row[p]).strip()
            for p in pref_cols
            if pd.notna(row[p]) and str(row[p]).strip() in fac_set
        ]
        if original_pref_counts is not None:
            original_pref_counts[sid] = len(explicit)

        remaining = [fid for fid in sorted_fac if fid not in set(explicit)]
        prefs = explicit + remaining

        students.append(Student(id=sid, name=sid, cpi=cpi, preferences=prefs))

    return students


# ---------------------------------------------------------------------------
# Policy runners
# ---------------------------------------------------------------------------

def run_standard_policy(students_path: Path, faculty_path: Path, policy: str) -> dict:
    faculty = load_faculty(faculty_path)
    orig_counts: dict[str, int] = {}
    students = load_anonymized_students(students_path, [f.id for f in faculty], orig_counts)
    assignments, _, meta, metrics = run_full_allocation(students, faculty, policy=policy)
    return {
        "assignments": assignments,
        "students": students,
        "faculty": faculty,
        "meta": meta,
        "metrics": metrics,
        "original_pref_counts": orig_counts,
    }


def run_tiered_rounds(students_path: Path, faculty_path: Path) -> dict:
    faculty = load_faculty(faculty_path)
    orig_counts: dict[str, int] = {}
    students = load_anonymized_students(students_path, [f.id for f in faculty], orig_counts)

    students_ph0, faculty_ph0, meta, snapshots = phase0(students, faculty)
    state = tiered_rounds_start(students_ph0, faculty_ph0, snapshots)

    tie_log: list[dict] = []
    while state.status not in ("complete", "stalled"):
        if state.status == "awaiting_tie":
            pt = state.pending_tie
            chosen = sorted(
                pt.tied_ids,
                key=lambda s: int(re.sub(r"\D", "", s) or "0"),
            )[0]
            tie_log.append({
                "round": pt.round_no,
                "advisor": pt.advisor_id,
                "tied_students": pt.tied_ids,
                "chosen": chosen,
                "tied_cpi": pt.tied_cpi,
            })
            state = tiered_rounds_resume(state, chosen)

    stalled = state.status == "stalled"
    stall_unassigned = list(state.stall_unassigned) if stalled else []

    metrics = compute_metrics(
        state.students,
        state.assignments,
        F=len(faculty_ph0),
        faculty_ids=[f.id for f in faculty_ph0],
        faculty=faculty_ph0,
    )
    return {
        "assignments": state.assignments,
        "students": state.students,
        "faculty": faculty_ph0,
        "meta": meta,
        "metrics": metrics,
        "original_pref_counts": orig_counts,
        "tie_log": tie_log,
        "stalled": stalled,
        "stall_unassigned": stall_unassigned,
    }


def run_year(year_dir: Path) -> dict:
    sp = year_dir / "anonymized_preferences.csv"
    fp = year_dir / "faculty.csv"
    results = {}
    for policy in ("cpi_fill", "least_loaded"):
        print(f"    {policy}...", flush=True)
        results[policy] = run_standard_policy(sp, fp, policy)
    print("    tiered_rounds...", flush=True)
    results["tiered_rounds"] = run_tiered_rounds(sp, fp)
    return results


# ---------------------------------------------------------------------------
# Preference rank helper
# ---------------------------------------------------------------------------

def pref_rank(student: Student, faculty_id: str) -> int | None:
    try:
        return student.preferences.index(faculty_id) + 1
    except ValueError:
        return None


def rank_cell(
    student: Student,
    faculty_id: str | None,
    orig_count: int,
) -> str:
    if faculty_id is None:
        return "— *(unassigned)*"
    rank = pref_rank(student, faculty_id)
    if rank is None:
        return f"{faculty_id} (?)"
    marker = "†" if rank > orig_count else ""
    return f"{faculty_id} ({rank}){marker}"


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def build_allocation_table(
    students: list[Student],
    assignments_by_policy: dict[str, dict],
    orig_counts: dict[str, int],
) -> str:
    smap = {s.id: s for s in students}
    sorted_sids = sorted(smap, key=lambda sid: -smap[sid].cpi)

    pol_cols = " | ".join(f"{POLICY_LABELS[p]}" for p in POLICIES)
    lines = [
        f"| Student | CPI | Tier | {pol_cols} |",
        "|---------|-----|------|" + "----------------|" * len(POLICIES),
    ]
    for sid in sorted_sids:
        s = smap[sid]
        orig = orig_counts.get(sid, len(s.preferences))
        cells = [sid, f"{s.cpi:.2f}", s.tier or "?"]
        for policy in POLICIES:
            fid = assignments_by_policy[policy].get(sid)
            cells.append(rank_cell(s, fid, orig))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_heatmap_table(
    students: list[Student],
    faculty: list,
    assignments: dict[str, str | None],
) -> str:
    quartile_mode = any(s.tier in ("B1", "B2") for s in students if s.tier)
    tier_labels = ["A", "B1", "B2", "C"] if quartile_mode else ["A", "B", "C"]

    fmap = {f.id: f for f in faculty}
    smap = {s.id: s for s in students}

    counts: dict[str, dict[str, int]] = {}
    for sid, fid in assignments.items():
        if fid is None:
            continue
        s = smap.get(sid)
        if s is None or s.tier is None:
            continue
        if fid not in counts:
            counts[fid] = {t: 0 for t in tier_labels}
        t = s.tier if s.tier in tier_labels else tier_labels[-1]
        counts[fid][t] = counts[fid].get(t, 0) + 1

    if not counts:
        return "_No assignments._"

    active = sorted(counts.items(), key=lambda x: -sum(x[1].values()))
    tier_header = " | ".join(tier_labels)
    lines = [
        f"| Advisor | {tier_header} | Total | Cap |",
        "|---------|" + "-------|" * len(tier_labels) + "-------|-----|",
    ]
    for fid, tcounts in active:
        f = fmap.get(fid)
        cap = f.max_load if f else "?"
        total = sum(tcounts.values())
        tier_cells = []
        for t in tier_labels:
            cnt = tcounts.get(t, 0)
            if isinstance(cap, int) and cap > 0:
                tier_cells.append(f"{cnt} ({cnt*100//cap}%)")
            else:
                tier_cells.append(str(cnt))
        lines.append(f"| {fid} | " + " | ".join(tier_cells) + f" | {total} | {cap} |")
    return "\n".join(lines)


def fmt_val(val, spec=".4f") -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return format(val, spec)
    return str(val)


def build_student_metrics_table(policy_metrics: dict) -> str:
    pol_header = " | ".join(POLICY_LABELS[p] for p in POLICIES)
    lines = [
        f"| Metric | {pol_header} |",
        "|--------|" + "---------|" * len(POLICIES),
    ]

    for label, key, spec in [
        ("NPSS", "npss", ".4f"),
        ("Mean PSI", "mean_psi", ".4f"),
        ("Overflow Count", "overflow_count", "d"),
    ]:
        cells = [label]
        for p in POLICIES:
            val = policy_metrics[p].get(key)
            cells.append("N/A" if val is None else fmt_val(val, spec))
        lines.append("| " + " | ".join(cells) + " |")

    # Collect present tiers in canonical order — skip tiers with zero students in all policies
    canonical = ["A", "B", "B1", "B2", "C"]
    seen = set()
    for p in POLICIES:
        seen.update(policy_metrics[p].get("per_tier", {}).keys())
    present = [
        t for t in canonical
        if t in seen
        and any(
            (policy_metrics[p].get("per_tier", {}).get(t, {}).get("count") or 0) > 0
            for p in POLICIES
        )
    ]

    if present:
        lines.append("|  |  |  |  |")
        lines.append("| **Per-Tier Breakdown** | | | |")
        for t in present:
            for sub_key, sub_label in [
                ("count", "Count"),
                ("mean_rank", "Mean Rank"),
                ("mean_npss_score", "Mean NPSS"),
                ("within_window_rate", "In-Window %"),
                ("overflow_count", "Overflow"),
            ]:
                cells = [f"Tier {t} — {sub_label}"]
                any_val = False
                for p in POLICIES:
                    td = policy_metrics[p].get("per_tier", {}).get(t, {})
                    val = td.get(sub_key)
                    if val is None:
                        cells.append("—")
                    else:
                        any_val = True
                        if sub_key == "within_window_rate":
                            cells.append(f"{val*100:.1f}%")
                        elif isinstance(val, float):
                            cells.append(f"{val:.3f}")
                        else:
                            cells.append(str(val))
                if any_val:
                    lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def build_advisor_metrics_table(policy_metrics: dict) -> str:
    pol_header = " | ".join(POLICY_LABELS[p] for p in POLICIES)
    lines = [
        f"| Metric | {pol_header} |",
        "|--------|" + "---------|" * len(POLICIES),
    ]
    specs = [
        ("Advisors Assigned", "advisors_assigned", "d"),
        ("Empty Labs", "empty_labs", "d"),
        ("Avg MSES (lower = better)", "avg_mses", ".4f"),
        ("Avg LUR", "avg_lur", ".4f"),
        ("Avg Entropy", "avg_entropy", ".4f"),
        ("Baseline Entropy", "baseline_entropy", ".4f"),
        ("Equity Retention %", "equity_retention", ".1f"),
        ("CPI Skewness", "cpi_skewness", ".4f"),
    ]
    for label, key, spec in specs:
        cells = [label]
        for p in POLICIES:
            adv = policy_metrics[p].get("advisor", {})
            val = adv.get(key)
            cells.append("N/A" if val is None else fmt_val(val, spec))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_year_section(year: str, results: dict) -> str:
    ref = results["cpi_fill"]
    meta = ref["meta"]
    n_s = len(ref["students"])
    n_f = len(ref["faculty"])
    mode = meta.get("mode", "percentile")
    N_A = meta.get("N_A", "?")
    N_B = meta.get("N_B", "?")
    cap = meta.get("common_max_load", "?")

    lines: list[str] = []
    lines.append(f"## {year} Cohort — {n_s} students, {n_f} faculty\n")
    lines.append(
        f"**Tiering mode:** {mode} &nbsp;|&nbsp; "
        f"**N_A:** {N_A} &nbsp;|&nbsp; "
        f"**N_B:** {N_B} &nbsp;|&nbsp; "
        f"**Capacity / advisor:** {cap}\n"
    )

    # Tiered-rounds notes
    tr = results["tiered_rounds"]
    if tr.get("stalled"):
        ua = ", ".join(tr["stall_unassigned"])
        lines.append(
            f"> ⚠️ **Tiered Rounds stall:** the following student(s) exhausted all "
            f"preferences without being assigned: {ua}\n"
        )
    if tr.get("tie_log"):
        lines.append("**Auto-resolved ties (tiered_rounds — lowest student number wins):**\n")
        for t in tr["tie_log"]:
            lines.append(
                f"- Round {t['round']}: {t['advisor']} — "
                f"tied {t['tied_students']} (CPI {t['tied_cpi']:.2f}) → "
                f"chose **{t['chosen']}**"
            )
        lines.append("")

    # Use ref students (tiers identical across all policies for same cohort)
    ref_students = ref["students"]
    orig_counts = ref["original_pref_counts"]
    assignments_by_policy = {p: results[p]["assignments"] for p in POLICIES}

    lines.append("### Allocation Comparison\n")
    if year == "2019":
        lines.append(
            "> Ranks 1–8 are the student's explicit choices. "
            "Ranks 9–25 (marked †) are backfill positions (alphabetical).\n"
        )
    lines.append(build_allocation_table(ref_students, assignments_by_policy, orig_counts))
    lines.append("")

    lines.append("### Tier Heatmaps\n")
    lines.append(
        "Each cell shows `count (% of capacity)`. "
        "Rows sorted by total load descending.\n"
    )
    for policy in POLICIES:
        r = results[policy]
        lines.append(f"#### {POLICY_LABELS[policy]}\n")
        lines.append(build_heatmap_table(r["students"], r["faculty"], r["assignments"]))
        lines.append("")

    policy_metrics = {p: results[p]["metrics"] for p in POLICIES}

    lines.append("### Student Satisfaction Metrics\n")
    lines.append(build_student_metrics_table(policy_metrics))
    lines.append("")

    lines.append("### Advisor Metrics\n")
    lines.append(build_advisor_metrics_table(policy_metrics))
    lines.append("")

    return "\n".join(lines)


def build_summary_table(all_results: dict) -> str:
    lines = [
        "| Year | Policy | NPSS | Mean PSI | Overflow | Avg MSES | Equity Ret % | Empty Labs |",
        "|------|--------|------|----------|----------|----------|--------------|------------|",
    ]
    for year in ("2019", "2020"):
        for policy in POLICIES:
            m = all_results[year][policy]["metrics"]
            adv = m.get("advisor", {})
            row = [
                year,
                POLICY_LABELS[policy],
                fmt_val(m.get("npss"), ".4f"),
                fmt_val(m.get("mean_psi"), ".4f"),
                str(m.get("overflow_count", 0)),
                fmt_val(adv.get("avg_mses"), ".4f"),
                fmt_val(adv.get("equity_retention"), ".1f"),
                str(adv.get("empty_labs", "?")),
            ]
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    all_results: dict[str, dict] = {}
    for year, year_dir in YEAR_DIRS.items():
        print(f"Running {year}...", flush=True)
        all_results[year] = run_year(year_dir)
        print(f"  {year} done.", flush=True)

    report: list[str] = [
        "# MS Thesis Allocation — Policy Comparison (2019 & 2020)",
        "",
        "Policies compared: **CPI-Fill**, **Least Loaded**, **Tiered Rounds**",
        "",
        "Each cell in the Allocation Comparison tables shows the assigned faculty ID with the",
        "student's preference rank in parentheses (1 = top choice).",
        "",
        "> **Tie-breaking (tiered_rounds):** when students tie on CPI for the same advisor in",
        "> the same round the one with the lowest student number is auto-selected.",
        "",
        "> **Preference backfilling:** 2019 students submitted only 8 preferences.",
        "> Remaining faculty are appended alphabetically so all three policies operate on a",
        "> complete ranking (standard protocol). Backfill assignments are marked **†**.",
        "",
    ]

    for year in ("2019", "2020"):
        report.append(build_year_section(year, all_results[year]))

    report += [
        "---",
        "",
        "## Cross-Cohort Summary\n",
        build_summary_table(all_results),
        "",
        "_Metric glossary — "
        "**NPSS**: CPI-weighted satisfaction (0–1, higher = better); "
        "**PSI**: equal-weighted rank score (higher = better); "
        "**Overflow**: students assigned outside their N-tier window; "
        "**MSES**: mean rank at which students listed their advisor (lower = better); "
        "**Equity Ret %**: advisor CPI-mix diversity vs. baseline (higher = better)._",
        "",
    ]

    out = ROOT / "test" / "allocation_comparison_2019_2020.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"\nReport written → {out}")


if __name__ == "__main__":
    main()
