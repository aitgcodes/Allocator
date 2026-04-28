#!/usr/bin/env python3
"""
Generate multi-policy allocation comparison report for 2019 and 2020 cohorts.
Policies: cpi_fill, least_loaded, tiered_rounds
Outputs:
  test/allocation_comparison_2019_2020.md
  test/allocation_comparison_2019_2020.pdf
  test/figures/heatmap_<year>_<policy>.png  (one per policy per year)
"""

import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from allocator.allocation import (
    phase0,
    run_full_allocation,
    tiered_rounds_resume,
    tiered_rounds_start,
)
from allocator.data_loader import load_faculty, preprocess_students
from allocator.metrics import compute_metrics
from allocator.state import Student

POLICIES = ["cpi_fill", "least_loaded", "tiered_rounds"]
POLICY_LABELS = {
    "cpi_fill":      "CPI-Fill",
    "least_loaded":  "Least Loaded",
    "tiered_rounds": "Tiered Rounds",
}
YEAR_DIRS = {
    "2019": ROOT / "test" / "2019",
    "2020": ROOT / "test" / "2020",
}
FIGURES_DIR = ROOT / "test" / "figures"
OUT_MD  = ROOT / "test" / "allocation_comparison_2019_2020.md"
OUT_PDF = ROOT / "test" / "allocation_comparison_2019_2020.pdf"

# LaTeX unicode header (written to a temp location at runtime)
_UNICODE_TEX = textwrap.dedent(r"""
    \usepackage{newunicodechar}
    \newunicodechar{→}{\ensuremath{\rightarrow}}
    \newunicodechar{←}{\ensuremath{\leftarrow}}
    \newunicodechar{≤}{\ensuremath{\leq}}
    \newunicodechar{≥}{\ensuremath{\geq}}
    \newunicodechar{γ}{\ensuremath{\gamma}}
    \newunicodechar{×}{\ensuremath{\times}}
    \newunicodechar{−}{\ensuremath{-}}
    \newunicodechar{±}{\ensuremath{\pm}}
    \newunicodechar{†}{\ensuremath{\dagger}}
""").strip()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_year_students(
    students_path: Path,
    faculty: list,
) -> tuple[list[Student], dict[str, int]]:
    """
    Load students from a raw-form-style anonymized CSV using the same
    preprocess_students() pipeline as the UI "Clean & Load" path.

    Returns (students, orig_pref_counts) where orig_pref_counts[sid] is the
    number of *unique* non-empty preference entries in the raw file (before
    deduplication / backfill) — used to mark backfill assignments with †.
    """
    # --- count unique explicit preferences per student from the raw CSV ---
    raw = pd.read_csv(students_path, dtype=str)
    raw.columns = [c.strip().lower() for c in raw.columns]
    raw_pref_cols = [c for c in raw.columns if c.strip().lower().startswith("preference")]
    roll_col = next((c for c in raw.columns if "roll" in c), None)

    orig_counts: dict[str, int] = {}
    for _, row in raw.iterrows():
        sid = str(row[roll_col]).strip() if roll_col else ""
        seen: set[str] = set()
        for p in raw_pref_cols:
            val = str(row[p]).strip() if pd.notna(row[p]) else ""
            if val:
                seen.add(val)
        orig_counts[sid] = len(seen)

    # --- preprocess: normalise columns, deduplicate, map names→IDs, backfill ---
    cleaned_df, _, _ = preprocess_students(students_path, faculty)

    pref_cols = sorted(
        [c for c in cleaned_df.columns if c.startswith("pref_")],
        key=lambda c: int(c.split("_")[1]),
    )
    fac_ids = {f.id for f in faculty}

    students: list[Student] = []
    for _, row in cleaned_df.iterrows():
        sid  = str(row["student_id"]).strip()
        cpi  = float(row["cpi"])
        prefs = [
            str(row[p]).strip()
            for p in pref_cols
            if str(row[p]).strip() in fac_ids
        ]
        students.append(Student(id=sid, name=sid, cpi=cpi, preferences=prefs))

    return students, orig_counts


# ---------------------------------------------------------------------------
# Policy runners
# ---------------------------------------------------------------------------

def run_standard_policy(
    students_path: Path, faculty_path: Path, policy: str
) -> dict:
    faculty = load_faculty(faculty_path)
    students, orig = load_year_students(students_path, faculty)
    assignments, _, meta, metrics = run_full_allocation(students, faculty, policy=policy)
    return dict(assignments=assignments, students=students, faculty=faculty,
                meta=meta, metrics=metrics, original_pref_counts=orig)


def run_tiered_rounds(students_path: Path, faculty_path: Path) -> dict:
    faculty = load_faculty(faculty_path)
    students, orig = load_year_students(students_path, faculty)
    students_ph0, faculty_ph0, meta, snapshots = phase0(students, faculty)
    state = tiered_rounds_start(students_ph0, faculty_ph0, snapshots)
    tie_log: list[dict] = []
    while state.status not in ("complete", "stalled"):
        if state.status == "awaiting_tie":
            pt = state.pending_tie
            chosen = sorted(pt.tied_ids,
                            key=lambda s: int(re.sub(r"\D", "", s) or "0"))[0]
            tie_log.append(dict(round=pt.round_no, advisor=pt.advisor_id,
                                tied_students=pt.tied_ids, chosen=chosen,
                                tied_cpi=pt.tied_cpi))
            state = tiered_rounds_resume(state, chosen)
    stalled = state.status == "stalled"
    metrics = compute_metrics(
        state.students, state.assignments,
        F=len(faculty_ph0),
        faculty_ids=[f.id for f in faculty_ph0],
        faculty=faculty_ph0,
    )
    return dict(assignments=state.assignments, students=state.students,
                faculty=faculty_ph0, meta=meta, metrics=metrics,
                original_pref_counts=orig, tie_log=tie_log,
                stalled=stalled,
                stall_unassigned=list(state.stall_unassigned) if stalled else [])


def run_year(year_dir: Path) -> dict:
    sp, fp = year_dir / "anonymized_preferences.csv", year_dir / "faculty.csv"
    results = {}
    for policy in ("cpi_fill", "least_loaded"):
        print(f"    {policy}...", flush=True)
        results[policy] = run_standard_policy(sp, fp, policy)
    print("    tiered_rounds...", flush=True)
    results["tiered_rounds"] = run_tiered_rounds(sp, fp)
    return results


# ---------------------------------------------------------------------------
# Heatmap image generation (Plotly + Kaleido)
# ---------------------------------------------------------------------------

_TIER_COLOURS = {
    "A":  "#2196F3",
    "B":  "#FF9800",
    "B1": "#FF9800",
    "B2": "#FFB300",
    "C":  "#E53935",
}

def generate_heatmap_image(
    students: list[Student],
    faculty: list,
    assignments: dict,
    policy: str,
    year: str,
    out_dir: Path,
) -> Path:
    """Generate a tier-heatmap PNG and return its path."""
    quartile_mode = any(s.tier in ("B1", "B2") for s in students if s.tier)
    tier_labels   = ["A", "B1", "B2", "C"] if quartile_mode else ["A", "B", "C"]

    fmap = {f.id: f for f in faculty}
    smap = {s.id: s for s in students}

    counts: dict[str, dict[str, int]] = {}
    for sid, fid in assignments.items():
        if fid is None:
            continue
        s = smap.get(sid)
        if s is None or s.tier is None:
            continue
        t = s.tier if s.tier in tier_labels else tier_labels[-1]
        counts.setdefault(fid, {t2: 0 for t2 in tier_labels})[t] += 1

    if not counts:
        return None

    active  = sorted(counts.items(), key=lambda x: -sum(x[1].values()))
    y_ids   = [fid for fid, _ in active]

    z, text = [], []
    for fid, tc in active:
        cap   = fmap[fid].max_load if fid in fmap else 1
        row_z, row_t = [], []
        for t in tier_labels:
            cnt = tc.get(t, 0)
            pct = cnt * 100 / cap if cap > 0 else 0
            row_z.append(pct)
            row_t.append(f"{cnt} ({pct:.0f}%)" if cnt else "")
        z.append(row_z)
        text.append(row_t)

    # Build a custom colour scale that maps each tier column distinctly
    # (we use a single "Blues" scale on the z-values for the colour gradient)
    fig = go.Figure(go.Heatmap(
        z=z,
        x=tier_labels,
        y=y_ids,
        text=text,
        texttemplate="%{text}",
        textfont={"size": 11, "color": "black"},
        colorscale="Blues",
        zmin=0,
        zmax=100,
        showscale=True,
        colorbar=dict(title="% of cap", thickness=12, len=0.8),
    ))

    fig.update_layout(
        title=dict(
            text=f"{POLICY_LABELS[policy]}  ·  {year}",
            font=dict(size=13),
        ),
        xaxis=dict(title="CPI Tier", side="bottom"),
        yaxis=dict(title="Advisor", autorange="reversed"),
        height=max(320, len(active) * 28 + 100),
        width=520,
        margin=dict(l=70, r=70, t=50, b=50),
        plot_bgcolor="white",
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / f"heatmap_{year}_{policy}.png"
    fig.write_image(str(img_path), scale=2)
    return img_path


# ---------------------------------------------------------------------------
# Preference rank helpers
# ---------------------------------------------------------------------------

def pref_rank(student: Student, faculty_id: str) -> int | None:
    try:
        return student.preferences.index(faculty_id) + 1
    except ValueError:
        return None


def rank_cell(student: Student, fid: str | None, orig_count: int) -> str:
    if fid is None:
        return "— *(unassigned)*"
    rank = pref_rank(student, fid)
    if rank is None:
        return f"{fid} (?)"
    marker = "†" if rank > orig_count else ""
    return f"{fid} ({rank}){marker}"


# ---------------------------------------------------------------------------
# Load balance helper
# ---------------------------------------------------------------------------

def compute_load_balance(advisor_metrics: dict) -> int:
    per_fac = advisor_metrics.get("per_faculty", {})
    empty   = advisor_metrics.get("empty_labs", 0)
    loads   = [d["student_count"] for d in per_fac.values()] if per_fac else []
    if not loads:
        return 0
    return max(loads) - (0 if empty > 0 else min(loads))


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def build_allocation_table(
    students: list[Student],
    assignments_by_policy: dict,
    orig_counts: dict[str, int],
) -> str:
    smap       = {s.id: s for s in students}
    sorted_ids = sorted(smap, key=lambda sid: -smap[sid].cpi)
    pol_cols   = " | ".join(POLICY_LABELS[p] for p in POLICIES)
    lines = [
        f"| Student | CPI | Tier | {pol_cols} |",
        "|---------|-----|------|" + "----------------|" * len(POLICIES),
    ]
    for sid in sorted_ids:
        s    = smap[sid]
        orig = orig_counts.get(sid, len(s.preferences))
        cells = [sid, f"{s.cpi:.2f}", s.tier or "?"]
        for policy in POLICIES:
            cells.append(rank_cell(s, assignments_by_policy[policy].get(sid), orig))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_student_metrics_table(policy_metrics: dict) -> str:
    pol_hdr = " | ".join(POLICY_LABELS[p] for p in POLICIES)
    lines = [
        f"| Metric | {pol_hdr} |",
        "|--------|" + "---------|" * len(POLICIES),
    ]
    for label, key, spec in [
        ("NPSS",           "npss",           ".4f"),
        ("Mean PSI",       "mean_psi",        ".4f"),
        ("Overflow Count", "overflow_count",  "d"),
    ]:
        cells = [label]
        for p in POLICIES:
            v = policy_metrics[p].get(key)
            cells.append("N/A" if v is None else (format(v, spec) if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")

    # Per-tier (skip tiers with zero students everywhere)
    canonical = ["A", "B", "B1", "B2", "C"]
    seen      = set()
    for p in POLICIES:
        seen.update(policy_metrics[p].get("per_tier", {}).keys())
    present = [
        t for t in canonical if t in seen
        and any((policy_metrics[p].get("per_tier", {}).get(t, {}).get("count") or 0) > 0
                for p in POLICIES)
    ]
    if present:
        lines += ["|  |  |  |  |", "| **Per-Tier Breakdown** | | | |"]
        for t in present:
            for sk, sl in [
                ("count",              "Count"),
                ("mean_rank",          "Mean Rank"),
                ("mean_npss_score",    "Mean NPSS"),
                ("within_window_rate", "In-Window %"),
                ("overflow_count",     "Overflow"),
            ]:
                cells = [f"Tier {t} — {sl}"]
                any_val = False
                for p in POLICIES:
                    td  = policy_metrics[p].get("per_tier", {}).get(t, {})
                    val = td.get(sk)
                    if val is None:
                        cells.append("—")
                    else:
                        any_val = True
                        if sk == "within_window_rate":
                            cells.append(f"{val*100:.1f}%")
                        elif isinstance(val, float):
                            cells.append(f"{val:.3f}")
                        else:
                            cells.append(str(val))
                if any_val:
                    lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _adv_cell(policy_metrics: dict, policy: str, key: str, spec: str = ".4f") -> str:
    v = policy_metrics[policy].get("advisor", {}).get(key)
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return format(v, spec)
    return str(v)


def build_advisor_satisfaction_table(policy_metrics: dict) -> str:
    pol_hdr = " | ".join(POLICY_LABELS[p] for p in POLICIES)
    lines = [
        f"| Metric | {pol_hdr} |",
        "|--------|" + "---------|" * len(POLICIES),
    ]
    for label, key, spec in [
        ("Avg MSES (lower = better)", "avg_mses", ".4f"),
        ("Avg LUR",                   "avg_lur",  ".4f"),
    ]:
        cells = [label] + [_adv_cell(policy_metrics, p, key, spec) for p in POLICIES]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_load_distribution_table(policy_metrics: dict) -> str:
    pol_hdr = " | ".join(POLICY_LABELS[p] for p in POLICIES)
    lines = [
        f"| Metric | {pol_hdr} |",
        "|--------|" + "---------|" * len(POLICIES),
    ]
    for label, key, spec in [
        ("Advisors Assigned", "advisors_assigned", "d"),
        ("Empty Labs",        "empty_labs",        "d"),
    ]:
        cells = [label] + [_adv_cell(policy_metrics, p, key, spec) for p in POLICIES]
        lines.append("| " + " | ".join(cells) + " |")
    # Load balance (derived)
    cells = ["Load Balance"]
    for p in POLICIES:
        cells.append(str(compute_load_balance(policy_metrics[p].get("advisor", {}))))
    lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_tier_mixing_table(policy_metrics: dict) -> str:
    pol_hdr = " | ".join(POLICY_LABELS[p] for p in POLICIES)
    lines = [
        f"| Metric | {pol_hdr} |",
        "|--------|" + "---------|" * len(POLICIES),
    ]
    for label, key, spec in [
        ("Avg H_norm",          "avg_entropy",      ".4f"),
        ("H_baseline (ceiling)","baseline_entropy",  ".4f"),
        ("Equity Retention %",  "equity_retention",  ".1f"),
        ("CPI Skewness (diag)", "cpi_skewness",      ".4f"),
    ]:
        cells = [label] + [_adv_cell(policy_metrics, p, key, spec) for p in POLICIES]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Year section builder
# ---------------------------------------------------------------------------

def build_year_section(year: str, results: dict, figures_dir: Path) -> str:
    ref   = results["cpi_fill"]
    meta  = ref["meta"]
    n_s   = len(ref["students"])
    n_f   = len(ref["faculty"])
    mode  = meta.get("mode", "percentile")
    N_A   = meta.get("N_A", "?")
    N_B   = meta.get("N_B", "?")
    cap   = meta.get("common_max_load", "?")

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
            f"> ⚠️ **Tiered Rounds stall:** student(s) {ua} exhausted all "
            f"preferences without being assigned.\n"
        )
    if tr.get("tie_log"):
        lines.append(
            "**Auto-resolved ties (tiered_rounds — lowest student number wins):**\n"
        )
        for t in tr["tie_log"]:
            lines.append(
                f"- Round {t['round']}: {t['advisor']} — "
                f"tied {t['tied_students']} (CPI {t['tied_cpi']:.2f}) → "
                f"chose **{t['chosen']}**"
            )
        lines.append("")

    ref_students = ref["students"]
    orig_counts  = ref["original_pref_counts"]
    asgn_by_pol  = {p: results[p]["assignments"] for p in POLICIES}
    pol_metrics  = {p: results[p]["metrics"]     for p in POLICIES}

    # --- Allocation comparison table ---
    lines.append("### Allocation Comparison\n")
    if year == "2019":
        lines.append(
            "> Ranks 1–8 are explicit choices; ranks 9–25 (marked †) are backfill.\n"
        )
    lines.append(build_allocation_table(ref_students, asgn_by_pol, orig_counts))
    lines.append("")

    # --- Tier heatmaps (images) ---
    lines.append("### Tier Heatmaps\n")
    lines.append(
        "Each cell shows the count of students from that CPI tier assigned to the "
        "advisor, coloured by percentage of the advisor's capacity. "
        "Advisors sorted by total load descending.\n"
    )
    for policy in POLICIES:
        r       = results[policy]
        img_path = generate_heatmap_image(
            r["students"], r["faculty"], r["assignments"],
            policy, year, figures_dir,
        )
        rel = img_path.relative_to(OUT_MD.parent)
        lines.append(f"#### {POLICY_LABELS[policy]}\n")
        lines.append(f"![{POLICY_LABELS[policy]} heatmap — {year}]({rel})\n")

    # --- Student metrics ---
    lines.append("### Student Satisfaction Metrics\n")
    lines.append(build_student_metrics_table(pol_metrics))
    lines.append("")

    # --- Advisor satisfaction ---
    lines.append("### Advisor Satisfaction\n")
    lines.append(build_advisor_satisfaction_table(pol_metrics))
    lines.append("")

    # --- Load distribution ---
    lines.append("### Advisor Equity — Load Distribution\n")
    lines.append(build_load_distribution_table(pol_metrics))
    lines.append("")

    # --- Tier mixing ---
    lines.append("### Advisor Equity — Tier Mixing\n")
    lines.append(
        "> H_norm: normalized per-advisor Shannon entropy (0 = single tier, "
        "1 = uniform across all tiers). "
        "H_baseline = Σ H_max(actual\\_load) / F, where H_max(n) = log(min(n,K)) / log(K). "
        "ERR = H̄_norm / H_baseline × 100 %, always in [0, 100 %].\n"
    )
    lines.append(build_tier_mixing_table(pol_metrics))
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cross-cohort summary
# ---------------------------------------------------------------------------

def build_summary_table(all_results: dict) -> str:
    lines = [
        "| Year | Policy | NPSS | Mean PSI | Overflow | Avg MSES | "
        "Empty Labs | Load Balance | ERR % | Equity Ceiling |",
        "|------|--------|------|----------|----------|----------|"
        "------------|--------------|-------|----------------|",
    ]
    for year in ("2019", "2020"):
        for policy in POLICIES:
            m   = all_results[year][policy]["metrics"]
            adv = m.get("advisor", {})
            lb  = compute_load_balance(adv)
            row = [
                year, POLICY_LABELS[policy],
                f"{m.get('npss', 0):.4f}",
                f"{m.get('mean_psi', 0):.4f}",
                str(m.get("overflow_count", 0)),
                f"{adv.get('avg_mses', 0):.4f}" if adv.get("avg_mses") is not None else "N/A",
                str(adv.get("empty_labs", "?")),
                str(lb),
                f"{adv.get('equity_retention', 0):.1f}",
                f"{adv.get('baseline_entropy', 0):.4f}",
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
        "Preference ranks appear in parentheses beside each assigned advisor ID "
        "(1 = student's top choice).",
        "",
        "> **Tie-breaking (tiered_rounds):** equal-CPI students competing for the same "
        "advisor in the same round are resolved by lowest student number.",
        "",
        "> **Preference backfilling (2019):** students submitted only 8 preferences. "
        "Remaining faculty are appended alphabetically to complete the ranking "
        "(standard protocol). Backfill assignments are marked **†**.",
        "",
    ]

    for year in ("2019", "2020"):
        report.append(build_year_section(year, all_results[year], FIGURES_DIR))

    report += [
        "---",
        "",
        "## Cross-Cohort Summary\n",
        build_summary_table(all_results),
        "",
        "_Metric glossary — "
        "**NPSS**: CPI-weighted satisfaction (higher = better); "
        "**PSI**: equal-weighted rank score (higher = better); "
        "**Overflow**: outside N-tier window; "
        "**MSES**: mean rank students placed their advisor (lower = better); "
        "**ERR**: Equity Retention Rate — fraction of max possible tier mixing achieved "
        "(higher = better, always ≤ 100 %)._",
        "",
    ]

    OUT_MD.write_text("\n".join(report), encoding="utf-8")
    print(f"\nMarkdown report → {OUT_MD}")

    # --- Generate PDF ---
    tex_header = ROOT / "test" / "_unicode_symbols.tex"
    tex_header.write_text(_UNICODE_TEX, encoding="utf-8")
    result = subprocess.run(
        [
            "pandoc", str(OUT_MD), "-o", str(OUT_PDF),
            "--pdf-engine=xelatex",
            "-V", "geometry:margin=2.5cm",
            "-V", "fontsize=11pt",
            "-V", "mainfont=Georgia",
            "-V", "monofont=Menlo",
            "-H", str(tex_header),
            "--toc", "--toc-depth=3",
        ],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"PDF report       → {OUT_PDF}")
    else:
        print("PDF generation failed:")
        print(result.stderr)
    tex_header.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
