"""
visualizer.py — Plotly figure builders for all dashboard panels.

All functions accept a single AllocationSnapshot (or supporting data)
and return a plotly.graph_objects.Figure.

Panel A : bipartite_graph(snap, students, faculty)
Panel B : load_bar_chart(snap, faculty, meta)
Panel C : step_log_table(snapshots, current_step)
Panel D : statistics_panel(snap, students, meta)
Panel E : advisor_cpi_histogram(snap, students, faculty)
Panel F : advisor_tier_heatmap(snap, students, faculty)
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from plotly.subplots import make_subplots

from .state import AllocationSnapshot, Faculty, Student

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

TIER_COLOUR = {
    "A":  "#2196F3",   # blue
    "B":  "#FF9800",   # orange   (percentile mode)
    "B1": "#FF9800",   # orange   (quartile mode — top half of B)
    "B2": "#FFB300",   # amber    (quartile mode — bottom half of B)
    "C":  "#E53935",   # red
}
LOAD_COLOURS = {
    "low":  "#43A047",   # green   (load ≤ 50 % of max)
    "mid":  "#FDD835",   # yellow  (50–85 %)
    "high": "#E53935",   # red     (>85 %)
}
HIGHLIGHT_COLOUR = "#9C27B0"   # purple — newly assigned edge / bar


def _load_colour(load: int, max_load: int) -> str:
    if max_load == 0:
        return LOAD_COLOURS["low"]
    ratio = load / max_load
    if ratio <= 0.50:
        return LOAD_COLOURS["low"]
    if ratio <= 0.85:
        return LOAD_COLOURS["mid"]
    return LOAD_COLOURS["high"]


# ---------------------------------------------------------------------------
# Panel A — Bipartite graph
# ---------------------------------------------------------------------------

def bipartite_graph(
    snap: AllocationSnapshot,
    students: List[Student],
    faculty: List[Faculty],
) -> go.Figure:
    """
    Draw students (left column) and faculty (right column) as nodes.
    An edge connects each assigned student to their advisor.
    The edge created in this exact snapshot step is highlighted.
    """
    student_map = {s.id: s for s in students}
    faculty_map = {f.id: f for f in faculty}

    # vertical positions
    s_y = {s.id: i for i, s in enumerate(
        sorted(students, key=lambda x: (-x.cpi, x.id)))}
    f_y = {f.id: i * (len(students) / max(len(faculty), 1))
           for i, f in enumerate(faculty)}

    # nodes — students
    s_x = [0.0] * len(students)
    s_yv = [s_y[s.id] for s in sorted(students, key=lambda x: (-x.cpi, x.id))]
    s_text = [
        f"{s.name}<br>CPI {s.cpi:.2f}<br>Tier {s.tier or '?'}"
        for s in sorted(students, key=lambda x: (-x.cpi, x.id))
    ]
    s_colours = [TIER_COLOUR.get(s.tier or "C", "#999") for s in
                 sorted(students, key=lambda x: (-x.cpi, x.id))]
    s_ids_ordered = [s.id for s in sorted(students, key=lambda x: (-x.cpi, x.id))]

    # nodes — faculty
    f_x = [1.0] * len(faculty)
    f_yv = [f_y[f.id] for f in faculty]
    f_text = [
        f"{f.name}<br>Load {snap.faculty_loads.get(f.id,0)}/{f.max_load}"
        for f in faculty
    ]
    f_colours = [
        _load_colour(snap.faculty_loads.get(f.id, 0), f.max_load)
        for f in faculty
    ]

    # newly assigned student in this step
    new_assign: Optional[str] = None
    if snap.preference_rank:
        new_assign = next(iter(snap.preference_rank.keys()), None)

    # edges
    edge_x, edge_y, edge_colours, edge_widths = [], [], [], []
    for sid, fid in snap.assignments.items():
        if fid is None:
            continue
        sx = 0.0
        sy = s_y.get(sid, 0)
        fx = 1.0
        fy = f_y.get(fid, 0)
        edge_x += [sx, fx, None]
        edge_y += [sy, fy, None]
        is_new = (sid == new_assign)
        edge_colours.append(HIGHLIGHT_COLOUR if is_new else "#BDBDBD")
        edge_widths.append(3 if is_new else 1)

    fig = go.Figure()

    # draw edges (one trace per edge to allow individual colours)
    for i in range(len(edge_colours)):
        base = i * 3
        fig.add_trace(go.Scatter(
            x=edge_x[base:base+3],
            y=edge_y[base:base+3],
            mode="lines",
            line=dict(color=edge_colours[i], width=edge_widths[i]),
            showlegend=False,
            hoverinfo="skip",
        ))

    # student nodes
    fig.add_trace(go.Scatter(
        x=s_x, y=s_yv,
        mode="markers+text",
        marker=dict(size=14, color=s_colours, line=dict(width=1, color="#333")),
        text=[s.split("<br>")[0] for s in s_text],
        textposition="middle left",
        hovertext=s_text,
        hoverinfo="text",
        name="Students",
        showlegend=False,
    ))

    # faculty nodes
    fig.add_trace(go.Scatter(
        x=f_x, y=f_yv,
        mode="markers+text",
        marker=dict(size=18, color=f_colours, symbol="square",
                    line=dict(width=1, color="#333")),
        text=[t.split("<br>")[0] for t in f_text],
        textposition="middle right",
        hovertext=f_text,
        hoverinfo="text",
        name="Faculty",
        showlegend=False,
    ))

    # tier legend
    for tier, col in TIER_COLOUR.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=10, color=col),
            name=f"Tier {tier}",
        ))

    fig.update_layout(
        title=f"Step {snap.step} — {snap.phase}",
        xaxis=dict(range=[-0.4, 1.4], showgrid=False,
                   zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=160, r=160, t=50, b=10),
        plot_bgcolor="#FAFAFA",
        paper_bgcolor="#FFFFFF",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        height=max(400, len(students) * 28 + 80),
    )
    return fig


# ---------------------------------------------------------------------------
# Panel B — Advisor load bar chart
# ---------------------------------------------------------------------------

def load_bar_chart(
    snap: AllocationSnapshot,
    faculty: List[Faculty],
    meta: dict,
    new_fid: Optional[str] = None,
) -> go.Figure:
    """
    Horizontal bar chart of advisor loads.
    Dashed vertical line at common_max_load.
    Bars are coloured green/yellow/red by utilisation.
    The faculty assigned in the current step is highlighted purple.
    """
    fac_names  = [f.name for f in faculty]
    fac_ids    = [f.id   for f in faculty]
    loads      = [snap.faculty_loads.get(fid, 0) for fid in fac_ids]
    max_loads  = [f.max_load for f in faculty]

    bar_colours = []
    for fid, load, ml in zip(fac_ids, loads, max_loads):
        if fid == new_fid:
            bar_colours.append(HIGHLIGHT_COLOUR)
        else:
            bar_colours.append(_load_colour(load, ml))

    fig = go.Figure(go.Bar(
        y=fac_names,
        x=loads,
        orientation="h",
        marker_color=bar_colours,
        text=[f"{l}/{ml}" for l, ml in zip(loads, max_loads)],
        textposition="outside",
        hovertemplate="%{y}: %{x} students<extra></extra>",
    ))

    common_max = meta.get("common_max_load", max(max_loads, default=1))
    fig.add_vline(
        x=common_max,
        line_dash="dash",
        line_color="#E53935",
        annotation_text=f"max_load={common_max}",
        annotation_position="top right",
    )

    fig.update_layout(
        title="Advisor Load",
        xaxis_title="Students assigned",
        yaxis=dict(autorange="reversed"),
        margin=dict(l=10, r=60, t=50, b=40),
        plot_bgcolor="#FAFAFA",
        paper_bgcolor="#FFFFFF",
        height=max(300, len(faculty) * 32 + 80),
    )
    return fig


# ---------------------------------------------------------------------------
# Panel C — Step log table
# ---------------------------------------------------------------------------

def step_log_table(
    snapshots,           # SnapshotList
    current_step: int,
) -> go.Figure:
    """
    Show all events up to and including current_step as a scrollable table.
    """
    rows = [
        {
            "Step": snap.step,
            "Phase": snap.phase,
            "Event": snap.event,
        }
        for snap in snapshots
        if snap.step <= current_step
    ]

    if not rows:
        rows = [{"Step": 0, "Phase": "—", "Event": "No events yet"}]

    df = pd.DataFrame(rows)

    # highlight current row
    fill_colours = [
        [HIGHLIGHT_COLOUR if r == current_step else "#FFFFFF"
         for r in df["Step"]]
    ] * len(df.columns)

    fig = go.Figure(go.Table(
        header=dict(
            values=["<b>Step</b>", "<b>Phase</b>", "<b>Event</b>"],
            fill_color="#37474F",
            font=dict(color="white", size=12),
            align="left",
        ),
        cells=dict(
            values=[df["Step"], df["Phase"], df["Event"]],
            fill_color=fill_colours,
            font=dict(size=11),
            align="left",
            height=24,
        ),
    ))

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=300,
    )
    return fig


# ---------------------------------------------------------------------------
# Panel D — Statistics panel
# ---------------------------------------------------------------------------

def statistics_panel(
    snap: AllocationSnapshot,
    students: List[Student],
    faculty: List[Faculty],
    meta: dict,
) -> go.Figure:
    """
    Summary statistics as a formatted table:
    - Per-class assignment counts and % within N_tier
    - % assigned within 1st choice
    - Faculty load distribution (min / max / mean)
    """
    student_map = {s.id: s for s in students}

    # --- per-student stats ---
    rows = []
    assigned_within_pref1 = 0
    assigned_within_ntier = 0
    total_assigned = 0

    for sid, fid in snap.assignments.items():
        s = student_map[sid]
        if fid is None:
            rows.append({"tier": s.tier, "assigned": False,
                         "within_1st": False, "within_ntier": False})
            continue
        total_assigned += 1
        rank = s.preferences.index(fid) + 1 if fid in s.preferences else None
        within_1st   = rank == 1
        within_ntier = (
            rank is not None and (s.n_tier is None or rank <= s.n_tier)
        )
        if within_1st:
            assigned_within_pref1 += 1
        if within_ntier:
            assigned_within_ntier += 1
        rows.append({"tier": s.tier, "assigned": True,
                     "within_1st": within_1st, "within_ntier": within_ntier})

    n = len(students)
    overall_pct_1st   = 100 * assigned_within_pref1  / n if n else 0
    overall_pct_ntier = 100 * assigned_within_ntier  / n if n else 0

    # --- per-tier breakdown (order handles both percentile and quartile mode) ---
    tier_stats = []
    present_tiers = [t for t in ("A", "B1", "B2", "B", "C")
                     if any(s.tier == t for s in students)]
    for tier in present_tiers:
        tier_rows  = [r for r in rows if r["tier"] == tier]
        n_tier_val = len(tier_rows)
        n_asgn     = sum(1 for r in tier_rows if r["assigned"])
        n_1st      = sum(1 for r in tier_rows if r["within_1st"])
        n_nt       = sum(1 for r in tier_rows if r["within_ntier"])
        tier_stats.append({
            "Class": f"Class {tier}",
            "Students": n_tier_val,
            "Assigned": n_asgn,
            "Within 1st choice (%)": f"{100*n_1st/n_tier_val:.1f}" if n_tier_val else "—",
            "Within N_tier (%)":     f"{100*n_nt/n_tier_val:.1f}"  if n_tier_val else "—",
        })

    # overall row
    tier_stats.append({
        "Class": "Overall",
        "Students": n,
        "Assigned": total_assigned,
        "Within 1st choice (%)": f"{overall_pct_1st:.1f}",
        "Within N_tier (%)":     f"{overall_pct_ntier:.1f}",
    })

    # --- faculty load distribution ---
    active_loads = [snap.faculty_loads.get(f.id, 0) for f in faculty]
    load_min  = min(active_loads) if active_loads else 0
    load_max  = max(active_loads) if active_loads else 0
    load_mean = sum(active_loads) / len(active_loads) if active_loads else 0

    df_tier = pd.DataFrame(tier_stats)

    fig = go.Figure()

    fig.add_trace(go.Table(
        header=dict(
            values=[f"<b>{c}</b>" for c in df_tier.columns],
            fill_color="#37474F",
            font=dict(color="white", size=12),
            align="center",
        ),
        cells=dict(
            values=[df_tier[c] for c in df_tier.columns],
            fill_color=[
                ["#E3F2FD" if r < len(tier_stats)-1 else "#FFF9C4"
                 for r in range(len(tier_stats))]
            ] * len(df_tier.columns),
            font=dict(size=12),
            align="center",
            height=26,
        ),
    ))

    fig.add_annotation(
        text=(
            f"Faculty load — "
            f"min: {load_min} | max: {load_max} | "
            f"mean: {load_mean:.1f} | "
            f"formula max_load: {meta.get('common_max_load','—')}"
        ),
        xref="paper", yref="paper",
        x=0.5, y=-0.05,
        showarrow=False,
        font=dict(size=12),
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=40),
        height=260,
    )
    return fig


# ---------------------------------------------------------------------------
# Panel E — Advisor-averaged CPI histogram
# ---------------------------------------------------------------------------

def advisor_cpi_histogram(
    snap: AllocationSnapshot,
    students: List[Student],
    faculty: List[Faculty],
) -> go.Figure:
    student_cpi: Dict[str, float] = {s.id: s.cpi for s in students}

    faculty_cpis: Dict[str, List[float]] = {f.id: [] for f in faculty}
    for sid, fid in snap.assignments.items():
        if fid is not None and fid in faculty_cpis:
            faculty_cpis[fid].append(student_cpi.get(sid, 0.0))

    avg_cpis = [
        sum(cpis) / len(cpis) if cpis else 0.0
        for cpis in faculty_cpis.values()
    ]

    fig = go.Figure(go.Histogram(
        x=avg_cpis,
        nbinsx=10,
        xbins=dict(start=0, end=10, size=1),
        marker_color=HIGHLIGHT_COLOUR,
        marker_line=dict(color="white", width=1),
    ))
    fig.update_layout(
        xaxis=dict(title="Advisor-Averaged CPI", range=[0, 10]),
        yaxis=dict(title="Number of Advisors"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=40, r=20, t=30, b=40),
        height=300,
    )
    return fig


# ---------------------------------------------------------------------------
# Panel F — Advisor Tier Distribution Heatmap
# ---------------------------------------------------------------------------

def advisor_tier_heatmap(
    snap: AllocationSnapshot,
    students: List[Student],
    faculty: List[Faculty],
    meta: dict,
) -> go.Figure:
    """
    Diagnostic advisor-equity view.

    Rows = advisors with ≥1 assigned student, sorted by load descending.
    Columns = CPI tier labels (percentile: A/B/C; quartile: A/B1/B2/C).
    Cell value = count(advisor, tier) × 100 / max_load.
    Row sum = advisor's total load as % of capacity.

    Use together with Advisor CPI Entropy.
    """
    student_map:  Dict[str, Student] = {s.id: s for s in students}
    faculty_name: Dict[str, str]     = {f.id: f.name for f in faculty}

    max_load: int = int(
        meta.get("common_max_load")
        or math.floor(len(students) / max(len(faculty), 1)) + 1
    )

    # Detect tier mode
    quartile_mode = any(
        s.tier in ("B1", "B2") for s in students if s.tier is not None
    )
    tier_labels = ["A", "B1", "B2", "C"] if quartile_mode else ["A", "B", "C"]

    # Build advisor → tier counts from current snapshot assignments
    adv_counts: Dict[str, Dict[str, int]] = {}
    for sid, fid in snap.assignments.items():
        if fid is None:
            continue
        s = student_map.get(sid)
        if s is None:
            continue
        tier = s.tier if s.tier in tier_labels else tier_labels[-1]
        if fid not in adv_counts:
            adv_counts[fid] = {t: 0 for t in tier_labels}
        adv_counts[fid][tier] += 1

    if not adv_counts:
        fig = go.Figure()
        fig.update_layout(
            title="Advisor Tier Distribution — no assignments yet",
            height=300,
            margin=dict(l=160, r=20, t=50, b=60),
        )
        return fig

    # Sort by total load descending (most loaded advisors at the top)
    sorted_fids = sorted(
        adv_counts.keys(),
        key=lambda fid: sum(adv_counts[fid].values()),
        reverse=True,
    )

    # Build heatmap matrices
    z:          List[List[float]] = []
    customdata: List[List[list]]  = []
    y_labels:   List[str]         = []

    for fid in sorted_fids:
        counts = adv_counts[fid]
        total  = sum(counts.values())
        name        = faculty_name.get(fid, fid)
        row_sum_pct = round(total * 100.0 / max_load)
        y_labels.append(f"{name} ({row_sum_pct}%)")

        row_z  = []
        row_cd = []
        for tier in tier_labels:
            count    = counts.get(tier, 0)
            cell_pct = count * 100.0 / max_load
            row_z.append(cell_pct)
            row_cd.append([count, total])

        z.append(row_z)
        customdata.append(row_cd)

    n_advisors = len(sorted_fids)
    height     = max(340, 28 * n_advisors + 120)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=tier_labels,
        y=y_labels,
        customdata=customdata,
        colorscale="Blues",
        zmin=0,
        zmax=100,
        hovertemplate=(
            f"<b>%{{y}}</b><br>"
            f"Tier: %{{x}}<br>"
            f"Students in tier: %{{customdata[0]}}<br>"
            f"Cell value: %{{z:.0f}}% of capacity ({max_load})<br>"
            f"Advisor load: %{{customdata[1]}}/{max_load}"
            "<extra></extra>"
        ),
        colorbar=dict(title="% of capacity", ticksuffix="%"),
    ))

    fig.update_layout(
        title=dict(
            text=f"Advisor Tier Distribution — Step {snap.step}",
            font=dict(size=13),
        ),
        xaxis=dict(title="CPI Tier"),
        yaxis=dict(title="Advisor", autorange="reversed"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=160, r=20, t=50, b=80),
        height=height,
    )

    fig.add_annotation(
        text=(
            f"Cell = students in tier × 100 / capacity ({max_load}). "
            "Row sum = % of capacity filled. "
            "Rows sorted by load descending."
        ),
        xref="paper", yref="paper",
        x=0.5, y=-0.08,
        showarrow=False,
        font=dict(size=12, color="#666"),
        align="center",
    )

    return fig


# ---------------------------------------------------------------------------
# Panel G — Per-tier mean preference rank comparison chart
# ---------------------------------------------------------------------------

# Policy display colours (consistent across single and comparison views)
_POLICY_COLOURS = {
    "least_loaded": "#2196F3",   # blue
    "cpi_fill":     "#FF9800",   # orange
}
_FALLBACK_COLOURS = ["#9C27B0", "#E53935", "#00BCD4"]


def per_tier_rank_chart(
    runs: List[dict],
    tier_labels: List[str],
) -> go.Figure:
    """
    Grouped bar chart comparing mean assigned preference rank per tier.

    Parameters
    ----------
    runs : list of {"label": str, "metrics": dict}
        One entry per policy run to display. Metrics must contain "per_tier".
    tier_labels : list of str
        Ordered tier labels to include, e.g. ["A","B","C"] or ["A","B1","B2","C"].

    Lower rank = better (assigned closer to 1st choice).
    """
    fig = go.Figure()

    for i, run in enumerate(runs):
        label   = run["label"]
        metrics = run["metrics"]
        colour  = _POLICY_COLOURS.get(label, _FALLBACK_COLOURS[i % len(_FALLBACK_COLOURS)])

        per_tier = metrics.get("per_tier", {})
        y_vals   = []
        x_vals   = []
        text_vals = []

        for tier in tier_labels:
            td = per_tier.get(tier, {})
            if td.get("count", 0) == 0:
                continue
            mean_rank = td.get("mean_rank")
            if mean_rank is None:
                continue
            win_pct = td.get("within_window_rate", 0.0) * 100
            x_vals.append(f"Tier {tier}")
            y_vals.append(round(mean_rank, 2))
            text_vals.append(f"{win_pct:.0f}% in window")

        fig.add_trace(go.Bar(
            name=label,
            x=x_vals,
            y=y_vals,
            text=text_vals,
            textposition="outside",
            textfont=dict(size=9),
            marker_color=colour,
            hovertemplate=(
                f"<b>{label}</b><br>"
                "Tier: %{x}<br>"
                "Mean rank: %{y:.2f}<br>"
                "%{text}"
                "<extra></extra>"
            ),
        ))

    # Subtitle annotation listing NPSS / PSI per run
    subtitle_parts = []
    for run in runs:
        m = run["metrics"]
        subtitle_parts.append(
            f"{run['label']}: NPSS={m.get('npss', 0):.3f}  PSI={m.get('mean_psi', 0):.3f}"
        )
    subtitle = "    |    ".join(subtitle_parts)

    fig.update_layout(
        title=dict(text="Per-Tier Mean Preference Rank", font=dict(size=13)),
        barmode="group",
        xaxis=dict(title=""),
        yaxis=dict(
            title="Mean assigned preference rank  (lower = better)",
            rangemode="tozero",
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=60, r=20, t=70, b=90),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    fig.add_annotation(
        text=subtitle,
        xref="paper", yref="paper",
        x=0.5, y=-0.15,
        showarrow=False,
        font=dict(size=12, color="#444"),
        align="center",
    )

    fig.add_annotation(
        text="Bar label: % of tier assigned within protected preference window (N_tier)",
        xref="paper", yref="paper",
        x=0.5, y=-0.22,
        showarrow=False,
        font=dict(size=11, color="#888"),
        align="center",
    )

    return fig
