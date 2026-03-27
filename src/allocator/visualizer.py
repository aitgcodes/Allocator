"""
visualizer.py — Plotly figure builders for all four dashboard panels.

All functions accept a single AllocationSnapshot (or supporting data)
and return a plotly.graph_objects.Figure.

Panel A : bipartite_graph(snap, students, faculty)
Panel B : load_bar_chart(snap, faculty, meta)
Panel C : step_log_table(snapshots, current_step)
Panel D : statistics_panel(snap, students, meta)
"""

from __future__ import annotations

from typing import Dict, List, Optional

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from .state import AllocationSnapshot, Faculty, Student

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

TIER_COLOUR = {"A": "#2196F3", "B": "#FF9800", "C": "#E53935"}  # blue, orange, red
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

    # --- per-tier breakdown ---
    tier_stats = []
    for tier in ("A", "B", "C"):
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
