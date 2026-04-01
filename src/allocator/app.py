"""
app.py — Main entry point for the MS Thesis Advisor Allocation tool.

======================================================================
OUTPUT_MODE  (set at the top of this file)
======================================================================
  "dash"  →  Launch an interactive Dash server (default).
              Supports step-by-step slider, Round-1 interactive picks,
              file upload, and live visualisation.

  "html"  →  Run the full allocation automatically (Round-1 picks by
              top CPI) and export a self-contained HTML file with an
              embedded Plotly slider.  No server required.

======================================================================
STARTUP_MODE  (set at the top of this file)
======================================================================
  "full"         →  Phase 0 → Round 1 → Main allocation  (default)
  "phase0_only"  →  Run Phase 0, write the report, then stop.
  "from_report"  →  Skip Phase 0; load phase0_report.csv + phase0_meta.csv
                    from PHASE0_REPORT_DIR and proceed directly to Round 1.

======================================================================
Dash mode keyboard shortcut
======================================================================
  Left / Right arrow keys step through the allocation while the slider
  is focused.

Usage (Dash)
------
    conda activate allocator
    python -m allocator.app

Usage (HTML export)
-------------------
    OUTPUT_MODE = "html"    # edit below
    python -m allocator.app
    # → writes  allocation_output.html  next to this file

Usage (CLI phase-0-only)
------------------------
    python -m allocator.allocation --phase0-only \\
        --students data/sample_students.csv \\
        --faculty  data/sample_faculty.csv  \\
        --out      reports/
"""

from __future__ import annotations

import os
import sys
import base64
import io
from pathlib import Path
from typing import Dict, List, Optional

# ======================================================================
# *** USER-CONFIGURABLE SETTINGS ***
# ======================================================================

OUTPUT_MODE        = "dash"          # "dash" | "html"
STARTUP_MODE       = "full"          # "full" | "phase0_only" | "from_report"
ALLOCATION_POLICY  = "least_loaded"  # "least_loaded" | "nonempty"

# Paths used when not uploading via the UI
DEFAULT_STUDENTS_PATH = str(Path(__file__).parent.parent.parent / "data" / "sample_students.csv")
DEFAULT_FACULTY_PATH  = str(Path(__file__).parent.parent.parent / "data" / "sample_faculty.csv")

# Used only when STARTUP_MODE = "from_report"
PHASE0_REPORT_DIR = str(Path(__file__).parent.parent.parent / "reports")

# Where Phase-0 reports and HTML export are written
OUTPUT_DIR = str(Path(__file__).parent.parent.parent / "reports")

# Dash server settings
DASH_HOST = "127.0.0.1"
DASH_PORT = 8050
DASH_DEBUG = True

# ======================================================================

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, ctx
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

from .allocation import (
    _least_loaded_choice,
    cpi_fill_phase1,
    cpi_fill_phase2,
    _nonempty_choice,
    build_r1_candidate_lists,
    cpi_fill_allocation,
    main_allocation,
    phase0,
    round1,
    run_full_allocation,
)
from .metrics import compute_metrics

def _protocol_choice(student, cap_fids, faculty_map, faculty_loads):
    """Dispatch to the active policy's choice function for dashboard highlighting."""
    if ALLOCATION_POLICY == "nonempty":
        return _nonempty_choice(student, cap_fids, faculty_map, faculty_loads)
    return _least_loaded_choice(student, cap_fids, faculty_map, faculty_loads)

from .data_loader import (
    load_faculty,
    load_phase0_report,
    load_students,
    save_phase0_report,
    validate_preferences,
)
from .state import AllocationSnapshot, Faculty, SnapshotList, Student
from .visualizer import (
    bipartite_graph,
    load_bar_chart,
    statistics_panel,
    step_log_table,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_upload(contents: str, filename: str):
    """Decode a Dash upload component's base64 content string to bytes."""
    _, content_string = contents.split(",", 1)
    return base64.b64decode(content_string)


def _copy_snaps(snaps: SnapshotList) -> SnapshotList:
    """Return a new SnapshotList containing the same snapshot objects.

    This is a *shallow* copy of the container only — snapshot objects are
    immutable dataclasses so sharing them is safe.  The key purpose is to
    give ``phase0_snapshots`` its own list so that subsequent ``round1()``
    appends (which extend ``snapshots`` in-place) do not accidentally
    contaminate the reset checkpoint.
    """
    new = SnapshotList()
    for s in snaps:
        new.append(s)
    return new


def _load_from_bytes(data: bytes, filename: str, loader_fn):
    """Save bytes to a temp file and call loader_fn(path)."""
    import tempfile
    suffix = Path(filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return loader_fn(tmp_path)
    finally:
        os.unlink(tmp_path)


def _new_fid_from_snap(snap: AllocationSnapshot) -> Optional[str]:
    """Return the faculty ID assigned in this snapshot step, if any."""
    if snap.preference_rank:
        sid = next(iter(snap.preference_rank.keys()), None)
        return snap.assignments.get(sid) if sid else None
    return None


# ---------------------------------------------------------------------------
# HTML export mode
# ---------------------------------------------------------------------------

def run_html_export(
    students: List[Student],
    faculty: List[Faculty],
    meta: dict,
    snapshots: SnapshotList,
    out_path: str,
) -> None:
    """
    Build a single self-contained HTML file with an embedded Plotly slider
    that steps through each AllocationSnapshot.
    """
    frames_bipartite = []
    frames_load      = []

    for snap in snapshots:
        new_fid = _new_fid_from_snap(snap)
        frames_bipartite.append(
            bipartite_graph(snap, students, faculty)
        )
        frames_load.append(
            load_bar_chart(snap, faculty, meta, new_fid)
        )

    final_snap = snapshots.last()
    fig_stats = statistics_panel(final_snap, students, faculty, meta)
    fig_log   = step_log_table(snapshots, final_snap.step)

    # Build slider steps over the bipartite figure
    fig = frames_bipartite[0]

    # Collect all traces from every frame; use updatemenus/sliders
    # For simplicity, embed as separate subplot div per step using Plotly's
    # animation frames approach.
    # We build a combined figure with frames and a step slider.

    combined = go.Figure()
    for trace in frames_bipartite[0].data:
        combined.add_trace(trace)

    frame_list = []
    for i, (fb, fl) in enumerate(zip(frames_bipartite, frames_load)):
        snap = snapshots[i]
        frame_list.append(go.Frame(
            data=list(fb.data),
            name=str(snap.step),
            layout=go.Layout(title_text=f"Step {snap.step} — {snap.phase}: {snap.event}"),
        ))

    combined.frames = frame_list

    steps = [
        dict(
            method="animate",
            args=[[str(snapshots[i].step)],
                  {"frame": {"duration": 0, "redraw": True},
                   "mode": "immediate"}],
            label=f"{snapshots[i].step}: {snapshots[i].phase}",
        )
        for i in range(len(snapshots))
    ]

    combined.update_layout(
        title=f"MS Thesis Allocation — {meta.get('cohort_size','?')} students, "
              f"{meta.get('faculty_count','?')} faculty",
        sliders=[dict(
            active=0,
            steps=steps,
            currentvalue=dict(prefix="Step: ", font=dict(size=14)),
            pad=dict(t=50),
        )],
        updatemenus=[dict(
            type="buttons",
            showactive=False,
            y=1.15,
            x=0,
            xanchor="left",
            buttons=[
                dict(label="▶ Play",
                     method="animate",
                     args=[None, {"frame": {"duration": 600, "redraw": True},
                                  "fromcurrent": True}]),
                dict(label="⏸ Pause",
                     method="animate",
                     args=[[None], {"frame": {"duration": 0, "redraw": False},
                                    "mode": "immediate"}]),
            ],
        )],
        height=frames_bipartite[0].layout.height,
    )

    # Write to HTML
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html_parts = [
        "<html><head><meta charset='utf-8'>",
        "<title>MS Thesis Advisor Allocation</title>",
        "</head><body>",
        "<h2 style='font-family:sans-serif'>MS Thesis Advisor Allocation</h2>",
        combined.to_html(full_html=False, include_plotlyjs="cdn"),
        "<hr>",
        "<h3 style='font-family:sans-serif'>Final Statistics</h3>",
        fig_stats.to_html(full_html=False, include_plotlyjs=False),
        "<h3 style='font-family:sans-serif'>Step Log</h3>",
        fig_log.to_html(full_html=False, include_plotlyjs=False),
        "</body></html>",
    ]

    out_path.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"HTML export written to: {out_path}")


# ---------------------------------------------------------------------------
# Dash app
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="MS Thesis Allocation",
    suppress_callback_exceptions=True,
)

# ---- app-level data store (populated at runtime) ----
_app_state: dict = {
    "students":              [],
    "faculty":               [],
    "meta":                  {},
    "snapshots":             None,   # SnapshotList (full, grows with each phase)
    "phase0_snapshots":      None,   # SnapshotList after Phase 0 (for reset)
    "r1_pending":            {},     # faculty_id -> [student_ids]
    "r1_picks":              {},     # faculty_id -> chosen student_id
    "r1_assignments":        {},     # assignments dict after Round 1
    "r1_faculty_loads":      {},     # faculty loads after Round 1
    "main_queue":            [],     # ordered list of Student for manual main alloc
    "main_queue_idx":        0,      # current position in main_queue
    "main_run":              0,      # incremented each time main allocation starts (for unique button IDs)
    "current_assignments":   {},     # live assignments during main alloc
    "current_faculty_loads": {},     # live faculty loads during main alloc
    "phase":                 "idle", # "idle"|"phase0_done"|"r1"|"r1_done"|"main_alloc"|"complete"
    "metrics":               {},     # satisfaction metrics from compute_metrics
}

# ---------------------------------------------------------------------------
# Main-allocation UI helpers
# ---------------------------------------------------------------------------

def _compute_eligible_advisors(student, faculty_map, faculty_loads, meta):
    """
    Return (advisors, extended, cap_label) for the given student.
    advisors: list of (fid, Faculty, rank_1based|None, load, at_capacity)
    extended: True if cap was widened because all within-cap advisors are full
    """
    N_A = meta.get("N_A", 3)
    N_B = meta.get("N_B", 5)
    all_fids = [f.id for f in sorted(faculty_map.values(), key=lambda f: f.name)]
    pref_index = {fid: i for i, fid in enumerate(student.preferences)}

    def _any_free(fids):
        return any(
            faculty_loads.get(f, 0) < faculty_map[f].max_load
            for f in fids if f in faculty_map
        )

    if student.tier == "A":
        cap = student.preferences[:N_A]
        cap_label = f"top {N_A} preferences (Tier A cap)"
        extended = False
        if not _any_free(cap):
            cap = student.preferences[:N_B]
            cap_label = f"top {N_B} preferences (cap extended from A→B)"
            extended = True
    elif student.tier in ("B", "B1", "B2"):
        cap = student.preferences[:N_B]
        cap_label = f"top {N_B} preferences (Tier {student.tier} cap)"
        extended = False
        if not _any_free(cap):
            cap = all_fids
            cap_label = f"all faculty (cap extended {student.tier}→global)"
            extended = True
    else:  # C — global cap, preferences first then remaining
        pref_set = set(student.preferences)
        cap = list(student.preferences) + [f for f in all_fids if f not in pref_set]
        cap_label = "all faculty (Tier C — global cap)"
        extended = False

    advisors = []
    for fid in cap:
        if fid not in faculty_map:
            continue
        fac = faculty_map[fid]
        load = faculty_loads.get(fid, 0)
        rank = pref_index.get(fid)
        advisors.append((fid, fac, rank + 1 if rank is not None else None, load, load >= fac.max_load))

    return advisors, extended, cap_label


def _render_student_picker(student, faculty_map, faculty_loads, meta, queue_idx, total_queue, run=0):
    """Render the advisor-selection UI for one student during main allocation."""
    advisors, extended, cap_label = _compute_eligible_advisors(
        student, faculty_map, faculty_loads, meta
    )
    tier_color = {"A": "success", "B": "warning", "B1": "warning", "B2": "info", "C": "danger"}

    # Compute the protocol's recommended pick (per active allocation policy)
    cap_fids = [fid for fid, _, _, _, _ in advisors]
    protocol_result = _protocol_choice(student, cap_fids, faculty_map, faculty_loads)
    protocol_fid = protocol_result[0] if protocol_result else None

    advisor_cols = []
    for fid, fac, rank, load, at_capacity in advisors:
        rank_label = f"#{rank} choice" if rank else "outside preferences"
        is_protocol = (fid == protocol_fid)

        if at_capacity:
            btn_color, outline = "secondary", True
            extra_style = {"opacity": "0.4"}
        elif is_protocol:
            btn_color, outline = "light", True
            # orange border via custom style; outline keeps background white
            extra_style = {"border": "2px solid #fd7e14", "borderRadius": "6px"}
        else:
            btn_color, outline = "primary", True
            extra_style = {}

        advisor_cols.append(dbc.Col(
            dbc.Button(
                [
                    html.Div(html.Strong(fac.name), className="mb-1"),
                    html.Div(f"{rank_label}  ·  {load}/{fac.max_load} students", className="small"),
                    html.Div(
                        "Full" if at_capacity else f"{fac.max_load - load} slot{'s' if fac.max_load - load != 1 else ''} free",
                        className=f"small mt-1 {'text-danger fw-bold' if at_capacity else 'text-success'}",
                    ),
                    *([html.Div(
                        "★ Highest preferred with vacancy" if ALLOCATION_POLICY == "nonempty"
                        else "★ Least-loaded · highest preferred",
                        className="small fw-bold mt-1", style={"color": "#fd7e14"},
                    )] if is_protocol else []),
                ],
                id={"type": "main-pick", "index": fid, "step": queue_idx, "run": run},
                color=btn_color,
                outline=outline,
                disabled=at_capacity,
                className="w-100 text-start",
                style={"opacity": "0.4" if at_capacity else "1.0", **extra_style},
            ),
            md=3, className="mb-3",
        ))

    all_at_cap = bool(advisors) and all(a[4] for a in advisors)

    return html.Div([
        dbc.Progress(
            value=int((queue_idx / max(total_queue, 1)) * 100),
            className="mb-3",
            label=f"{queue_idx} of {total_queue} assigned",
            striped=True,
        ),
        *([dbc.Alert(
            f"⚠ All advisors within standard cap are full — cap extended to {cap_label}.",
            color="warning", className="mb-2",
        )] if extended else []),
        *([dbc.Alert("No eligible advisors with remaining capacity.", color="danger", className="mb-2")] if all_at_cap else []),

        # Student info card
        dbc.Card(dbc.CardBody(dbc.Row(dbc.Col([
            html.H5(student.name, className="mb-1"),
            html.Div([
                dbc.Badge(f"Tier {student.tier}", color=tier_color.get(student.tier, "secondary"), className="me-2"),
                html.Span(f"CPI {student.cpi:.2f}  ·  {student.id}", className="text-muted"),
            ]),
            html.Small(f"Eligible: {cap_label}", className="text-muted mt-1 d-block"),
        ]))), className="mb-3 bg-light border-0"),

        html.H6("Select advisor:", className="mb-2 text-muted"),
        dbc.Row(advisor_cols),
    ])


# ---------------------------------------------------------------------------
# Metrics panel renderer
# ---------------------------------------------------------------------------

def _render_metrics_panel(metrics: dict) -> html.Div:
    """
    Render the satisfaction metrics as a Dash component panel.

    Includes:
    - Primary row: NPSS with colour band (green/yellow/red)
    - Secondary row: Mean PSI in muted style
    - Overflow badge if overflow_count > 0
    - Per-tier breakdown table (only tiers with count > 0)
    """
    if not metrics:
        return html.Div()

    npss           = metrics.get("npss", 0.0)
    mean_psi       = metrics.get("mean_psi", 0.0)
    overflow_count = metrics.get("overflow_count", 0)
    per_tier       = metrics.get("per_tier", {})

    # NPSS colour band
    if npss >= 0.90:
        npss_color = "success"
    elif npss >= 0.75:
        npss_color = "warning"
    else:
        npss_color = "danger"

    # Primary NPSS row
    primary_card = dbc.Card(dbc.CardBody([
        html.Div([
            html.Span(
                f"{npss:.4f}",
                style={"fontSize": "2rem", "fontWeight": "bold"},
                className=f"text-{npss_color}",
            ),
            html.Div("NPSS (primary)", className="fw-bold"),
            html.Small("CPI-weighted · tier-aware", className="text-muted"),
        ]),
    ]), className="mb-2 border-0 bg-light")

    # Secondary PSI row
    secondary_card = dbc.Card(dbc.CardBody([
        html.Div([
            html.Span(
                f"{mean_psi:.4f}",
                style={"fontSize": "1.4rem"},
                className="text-secondary",
            ),
            html.Div("Mean PSI (secondary)", className="text-muted"),
            html.Small("equal-weighted · global rank", className="text-muted"),
        ]),
    ]), className="mb-2 border-0 bg-light")

    # Overflow badge
    overflow_badge = []
    if overflow_count > 0:
        overflow_badge = [
            dbc.Badge(
                f"⚠ {overflow_count} overflow",
                color="danger",
                className="mb-2 me-2",
                style={"fontSize": "0.9rem"},
            )
        ]

    # Per-tier breakdown table
    tier_rows = []
    for tier in ("A", "B", "B1", "B2", "C"):
        td = per_tier.get(tier, {})
        count = td.get("count", 0)
        if count == 0:
            continue
        mean_rank = td.get("mean_rank")
        rank_str  = f"{mean_rank:.1f}" if mean_rank is not None else "—"
        rate      = td.get("within_window_rate", 0.0) * 100
        npss_sc   = td.get("mean_npss_score", 0.0)
        psi_sc    = td.get("mean_psi_score", 0.0)
        tier_rows.append(html.Tr([
            html.Td(dbc.Badge(
                tier,
                color={"A": "success", "B": "warning", "B1": "warning",
                       "B2": "info", "C": "danger"}.get(tier, "secondary"),
            )),
            html.Td(str(count), className="text-center"),
            html.Td(rank_str, className="text-center"),
            html.Td(f"{rate:.1f}%", className="text-center"),
            html.Td(f"{npss_sc:.3f}", className="text-center"),
            html.Td(f"{psi_sc:.3f}", className="text-center"),
        ]))

    tier_table = (
        dbc.Table([
            html.Thead(html.Tr([
                html.Th("Tier"),
                html.Th("Count", className="text-center"),
                html.Th("Mean Rank", className="text-center"),
                html.Th("Within-Window %", className="text-center"),
                html.Th("NPSS", className="text-center"),
                html.Th("PSI", className="text-center"),
            ])),
            html.Tbody(tier_rows),
        ], bordered=True, size="sm", className="mb-0")
        if tier_rows else html.P("No tier data available.", className="text-muted")
    )

    # ---- Advisor satisfaction section ----
    advisor = metrics.get("advisor", {})
    advisor_section = []
    if advisor:
        qmode     = advisor.get("quartile_mode", False)
        tier_note = "A=1 · B1=2 · B2=3 · C=4" if qmode else "A=1 · B=2 · C=3"
        mean_bt   = advisor.get("mean_best_tier", 0.0)
        worst_bt  = advisor.get("worst_best_tier", 0)
        frac_a    = advisor.get("fraction_with_A", 0.0)
        adv_a     = advisor.get("advisors_with_A", 0)
        total_adv = advisor.get("total_advisors", 0)
        adv_asgn  = advisor.get("advisors_assigned", 0)

        advisor_cards = dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Span(f"{mean_bt:.3f}",
                          style={"fontSize": "1.6rem", "fontWeight": "bold"},
                          className="text-primary"),
                html.Div("Mean best-tier", className="fw-bold"),
                html.Small(f"lower = better · {adv_asgn} advisors w/ students",
                           className="text-muted"),
            ]), className="mb-2 border-0 bg-light"), md=4),

            dbc.Col(dbc.Card(dbc.CardBody([
                html.Span(str(worst_bt),
                          style={"fontSize": "1.6rem", "fontWeight": "bold"},
                          className="text-warning"),
                html.Div("Worst best-tier", className="fw-bold"),
                html.Small("highest value = least satisfied advisor",
                           className="text-muted"),
            ]), className="mb-2 border-0 bg-light"), md=4),

            dbc.Col(dbc.Card(dbc.CardBody([
                html.Span(f"{frac_a:.1%}",
                          style={"fontSize": "1.6rem", "fontWeight": "bold"},
                          className="text-success"),
                html.Div("Advisors with ≥1 A-tier", className="fw-bold"),
                html.Small(f"{adv_a} / {total_adv} advisors",
                           className="text-muted"),
            ]), className="mb-2 border-0 bg-light"), md=4),
        ])

        advisor_section = [
            html.H6("Advisor Satisfaction", className="mt-3 mb-1 text-muted"),
            html.Small(f"Tier mapping: {tier_note}", className="text-muted d-block mb-2"),
            advisor_cards,
        ]

    return html.Div([
        html.H5("Satisfaction Metrics", className="mt-3 mb-2"),
        html.H6("Student Satisfaction", className="mb-1 text-muted"),
        dbc.Row([
            dbc.Col(primary_card, md=4),
            dbc.Col(secondary_card, md=4),
            dbc.Col(html.Div(overflow_badge), md=4, className="d-flex align-items-center"),
        ]),
        html.H6("Per-tier breakdown", className="mt-2 mb-1 text-muted"),
        tier_table,
        *advisor_section,
        dbc.Button("⬇ Download metrics (CSV)", id="btn-download-metrics",
                   color="outline-secondary", size="sm", className="mt-3"),
    ])


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _upload_card() -> dbc.Card:
    return dbc.Card([
        dbc.CardHeader("1 — Load data"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("Students file (CSV / Excel)"),
                    dcc.Upload(
                        id="upload-students",
                        children=html.Div(["Drag & drop or ", html.A("select file")]),
                        style={"borderWidth":"1px","borderStyle":"dashed",
                               "borderRadius":"5px","textAlign":"center","padding":"10px"},
                        multiple=False,
                    ),
                    html.Div(id="upload-students-status", className="text-muted small mt-1"),
                ], md=6),
                dbc.Col([
                    html.Label("Faculty file (CSV / Excel)"),
                    dcc.Upload(
                        id="upload-faculty",
                        children=html.Div(["Drag & drop or ", html.A("select file")]),
                        style={"borderWidth":"1px","borderStyle":"dashed",
                               "borderRadius":"5px","textAlign":"center","padding":"10px"},
                        multiple=False,
                    ),
                    html.Div(id="upload-faculty-status", className="text-muted small mt-1"),
                ], md=6),
            ]),
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    html.Label("— OR load a Phase-0 report —"),
                    dcc.Upload(
                        id="upload-p0-report",
                        children=html.Div(["phase0_report.csv"]),
                        style={"borderWidth":"1px","borderStyle":"dashed",
                               "borderRadius":"5px","textAlign":"center","padding":"8px"},
                        multiple=False,
                    ),
                ], md=6),
                dbc.Col([
                    html.Label(" "),  # spacer
                    dcc.Upload(
                        id="upload-p0-meta",
                        children=html.Div(["phase0_meta.csv"]),
                        style={"borderWidth":"1px","borderStyle":"dashed",
                               "borderRadius":"5px","textAlign":"center","padding":"8px"},
                        multiple=False,
                    ),
                ], md=6),
            ]),
        ]),
    ], className="mb-3")


def _control_card() -> dbc.Card:
    return dbc.Card([
        dbc.CardHeader("2 — Run"),
        dbc.CardBody([
            dbc.ButtonGroup([
                dbc.Button("Run Phase 0 only",   id="btn-phase0",      color="info",    className="me-2"),
                dbc.Button("Run full allocation", id="btn-full",        color="primary", className="me-2"),
                dbc.Button("Export HTML",         id="btn-html",        color="secondary", className="me-2"),
                dbc.Button("View Phase 0 data",   id="btn-view-phase0", color="light",   outline=True, className="me-2"),
                dbc.Button("↺ Reset to Round 1",  id="btn-reset-r1",   color="warning", outline=True),
            ]),
            html.Div(id="run-status", className="mt-2 text-muted small"),
        ]),
    ], className="mb-3")


def _r1_card() -> dbc.Card:
    return dbc.Card([
        dbc.CardHeader("3 — Round 1: faculty picks"),
        dbc.CardBody(id="r1-panel", children=[
            html.Span("Load data and run Phase 0 to begin.", className="text-muted"),
        ]),
    ], className="mb-3", id="r1-card")


def _main_alloc_card() -> dbc.Card:
    return dbc.Card([
        dbc.CardHeader("4 — Main Allocation"),
        dbc.CardBody(id="main-alloc-panel", children=[
            html.Span("Complete Round 1 first.", className="text-muted"),
        ]),
    ], className="mb-3")


def _landing_layout() -> dbc.Container:
    """Return a full-screen centered landing page for '/'."""
    return dbc.Container([
        dbc.Row(
            dbc.Col([
                html.H1("Welcome to the Allocator App",
                        className="text-primary text-center mb-2"),
                html.P("MS Thesis Advisor Allocation System",
                       className="text-muted text-center mb-4"),
                dbc.Card([
                    dbc.CardBody([
                        html.Label("Allocation Policy", className="fw-bold mb-1"),
                        dcc.Dropdown(
                            id="landing-policy-dropdown",
                            options=[
                                {"label": "Least-loaded · highest preferred",
                                 "value": "least_loaded"},
                                {"label": "Highest preferred with vacancy",
                                 "value": "nonempty"},
                                {"label": "CPI-Fill (two-phase)",
                                 "value": "cpi_fill"},
                            ],
                            value="least_loaded",
                            clearable=False,
                            className="mb-2",
                        ),
                        html.Div(id="landing-policy-desc",
                                 className="text-muted small mb-3"),
                        dbc.Button("Continue →",
                                   id="btn-landing-continue",
                                   color="primary",
                                   className="float-end"),
                    ]),
                ], className="border-0 shadow"),
            ], md=5),
            justify="center",
            align="center",
            style={"minHeight": "80vh"},
        ),
    ], fluid=True)


def _viz_card() -> dbc.Card:
    return dbc.Card([
        dbc.CardHeader("5 — Allocation replay"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col(
                    dcc.Slider(
                        id="step-slider",
                        min=0, max=0, step=1, value=0,
                        marks={},
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                    width=10,
                ),
                dbc.Col(
                    dbc.Button("▶ Play", id="btn-play", color="success", size="sm"),
                    width=2,
                ),
            ], className="mb-3"),
            dcc.Interval(id="play-interval", interval=700, n_intervals=0, disabled=True),
            dbc.Tabs([
                dbc.Tab(dcc.Graph(id="graph-bipartite"), label="Assignment Graph"),
                dbc.Tab(dcc.Graph(id="graph-load"),      label="Advisor Loads"),
                dbc.Tab(dcc.Graph(id="graph-stats"),     label="Statistics"),
                dbc.Tab(dcc.Graph(id="graph-log"),       label="Step Log"),
            ]),
        ]),
    ], className="mb-3")


app.layout = dbc.Container([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="store-policy", data="least_loaded"),

    # Landing page — shown at "/"
    html.Div(id="landing-page", children=_landing_layout()),

    # Main app page — shown at "/app"
    html.Div(id="main-page", style={"display": "none"}, children=[
        dbc.Row(dbc.Col(html.H2("MS Thesis Advisor Allocation",
                                className="my-3 text-primary"))),
        dbc.Row(dbc.Col(html.Div(id="active-policy-badge", className="mb-2"))),
        dbc.Row(dbc.Col(_upload_card())),
        dbc.Row(dbc.Col(_control_card())),
        dbc.Row(dbc.Col(_r1_card())),
        dbc.Row(dbc.Col(_main_alloc_card())),
        dbc.Row(dbc.Col(_viz_card())),
    ]),

    # Always-present hidden components (stores, downloads, modals, toast)
    dcc.Store(id="store-loaded",        data=False),
    dcc.Store(id="store-phase",         data="idle"),
    dcc.Store(id="store-r1-picks",      data={}),
    dcc.Store(id="store-playing",       data=False),
    dcc.Store(id="store-pending-pick",  data=None),
    dcc.Download(id="download-report"),
    dcc.Download(id="download-metrics"),

    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("⚠ Override protocol recommendation?")),
        dbc.ModalBody(id="modal-confirm-body"),
        dbc.ModalFooter([
            dbc.Button("Confirm override", id="btn-confirm-override",
                       color="danger",   className="me-2"),
            dbc.Button("Cancel",          id="btn-cancel-override",
                       color="secondary", outline=True),
        ]),
    ], id="modal-confirm-pick", is_open=False, centered=True, size="lg"),

    dbc.Toast(
        id="toast-picked",
        header="✓ Assigned",
        is_open=False,
        dismissable=True,
        duration=3000,
        style={"position": "fixed", "bottom": 24, "right": 24, "zIndex": 9999,
               "minWidth": "260px"},
        color="success",
    ),

    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Phase 0 Results")),
        dbc.ModalBody(id="modal-phase0-body"),
        dbc.ModalFooter(
            dbc.Button("Close", id="btn-close-phase0-modal", className="ms-auto", n_clicks=0)
        ),
    ], id="modal-phase0", size="xl", scrollable=True, is_open=False),
], fluid=True)


# ---------------------------------------------------------------------------
# Callbacks — landing page
# ---------------------------------------------------------------------------

@app.callback(
    Output("landing-policy-desc", "children"),
    Input("landing-policy-dropdown", "value"),
)
def cb_landing_policy_desc(value):
    if value == "nonempty":
        return ("Prioritises the highest-preferred advisor with no students yet assigned. "
                "Falls back to the highest-preferred advisor with remaining capacity "
                "if no empty labs exist.")
    if value == "cpi_fill":
        return ("Two-phase procedure: Phase 1 processes students in descending CPI order "
                "(N_tier cap) until the number of unassigned students equals the number "
                "of empty labs; Phase 2 assigns each remaining student to their "
                "highest-preferred empty lab (full preference list, no cap).")
    return ("Assigns to the least-loaded eligible advisor, "
            "with ties broken by preference rank.")


@app.callback(
    Output("url",          "pathname"),
    Output("store-policy", "data"),
    Input("btn-landing-continue", "n_clicks"),
    State("landing-policy-dropdown", "value"),
    prevent_initial_call=True,
)
def cb_landing_continue(n_clicks, policy):
    global ALLOCATION_POLICY
    chosen = policy or "least_loaded"
    ALLOCATION_POLICY = chosen
    return "/app", chosen


@app.callback(
    Output("landing-page", "style"),
    Output("main-page",    "style"),
    Input("url", "pathname"),
)
def cb_toggle_pages(pathname):
    if pathname == "/app":
        return {"display": "none"}, {"display": "block"}
    return {"display": "block"}, {"display": "none"}


@app.callback(
    Output("active-policy-badge", "children"),
    Input("store-policy", "data"),
)
def cb_policy_badge(policy):
    if policy == "nonempty":
        label, color = "Highest preferred with vacancy", "info"
    elif policy == "cpi_fill":
        label, color = "CPI-Fill (two-phase)", "warning"
    else:
        label, color = "Least-loaded · highest preferred", "secondary"
    return dbc.Badge(f"Policy: {label}", color=color, className="mb-2")


# ---------------------------------------------------------------------------
# Callbacks — data loading
# ---------------------------------------------------------------------------

@app.callback(
    Output("upload-students-status", "children"),
    Output("upload-faculty-status",  "children"),
    Output("store-loaded", "data"),
    Input("upload-students", "contents"),
    Input("upload-faculty",  "contents"),
    State("upload-students", "filename"),
    State("upload-faculty",  "filename"),
    prevent_initial_call=True,
)
def cb_load_files(s_contents, f_contents, s_fname, f_fname):
    _app_state["students"] = []
    _app_state["faculty"]  = []

    s_msg = f_msg = ""
    loaded = False

    if s_contents and s_fname:
        try:
            data = _parse_upload(s_contents, s_fname)
            _app_state["students"] = _load_from_bytes(data, s_fname, load_students)
            s_msg = f"✓ {len(_app_state['students'])} students loaded from {s_fname}"
        except Exception as e:
            s_msg = f"✗ Error: {e}"

    if f_contents and f_fname:
        try:
            data = _parse_upload(f_contents, f_fname)
            _app_state["faculty"] = _load_from_bytes(data, f_fname, load_faculty)
            f_msg = f"✓ {len(_app_state['faculty'])} faculty loaded from {f_fname}"
        except Exception as e:
            f_msg = f"✗ Error: {e}"

    if _app_state["students"] and _app_state["faculty"]:
        try:
            validate_preferences(_app_state["students"], _app_state["faculty"])
            loaded = True
        except ValueError as e:
            s_msg += f"  ⚠ {e}"

    return s_msg, f_msg, loaded


@app.callback(
    Output("upload-students-status", "children", allow_duplicate=True),
    Output("upload-faculty-status",  "children", allow_duplicate=True),
    Output("store-loaded", "data", allow_duplicate=True),
    Input("upload-p0-report", "contents"),
    Input("upload-p0-meta",   "contents"),
    State("upload-p0-report", "filename"),
    State("upload-p0-meta",   "filename"),
    State("upload-faculty",   "contents"),
    State("upload-faculty",   "filename"),
    prevent_initial_call=True,
)
def cb_load_report(rep_contents, meta_contents, rep_fname, meta_fname,
                   f_contents, f_fname):
    """Load students from a Phase-0 report + load faculty separately."""
    s_msg = f_msg = ""
    loaded = False

    if rep_contents and meta_contents:
        try:
            rep_data  = _parse_upload(rep_contents,  rep_fname)
            meta_data = _parse_upload(meta_contents, meta_fname)

            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tr:
                tr.write(rep_data); rp = tr.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tm:
                tm.write(meta_data); mp = tm.name

            students, meta = load_phase0_report(rp, mp)
            os.unlink(rp); os.unlink(mp)

            _app_state["students"] = students
            _app_state["meta"]     = meta
            _app_state["phase"]    = "phase0_done"
            s_msg = (f"✓ Phase-0 report loaded: {len(students)} students "
                     f"[N_A={meta['N_A']} N_B={meta['N_B']}]")
        except Exception as e:
            s_msg = f"✗ Error loading report: {e}"

    if f_contents and f_fname:
        try:
            data = _parse_upload(f_contents, f_fname)
            _app_state["faculty"] = _load_from_bytes(data, f_fname, load_faculty)
            f_msg = f"✓ {len(_app_state['faculty'])} faculty loaded"
        except Exception as e:
            f_msg = f"✗ Error: {e}"

    if _app_state["students"] and _app_state["faculty"]:
        loaded = True

    return s_msg, f_msg, loaded


# ---------------------------------------------------------------------------
# Callbacks — run buttons
# ---------------------------------------------------------------------------

@app.callback(
    Output("run-status", "children"),
    Output("store-phase", "data"),
    Output("step-slider", "max"),
    Output("step-slider", "marks"),
    Output("step-slider", "value"),
    Input("btn-phase0", "n_clicks"),
    Input("btn-full",   "n_clicks"),
    State("store-loaded", "data"),
    prevent_initial_call=True,
)
def cb_run(n_phase0, n_full, loaded):
    # Also accept preloaded data that was set before any upload callback fired
    if not loaded and not (_app_state["students"] and _app_state["faculty"]):
        return "⚠ Please load student and faculty files first.", "idle", 0, {}, 0

    triggered = ctx.triggered_id

    students = _app_state["students"]
    faculty  = _app_state["faculty"]

    if triggered == "btn-phase0":
        # Phase-0 only
        if _app_state["phase"] != "phase0_done":
            try:
                students, faculty, meta, snaps = phase0(
                    students, faculty, out_dir=OUTPUT_DIR
                )
                _app_state.update({
                    "students":         students,
                    "faculty":          faculty,
                    "meta":             meta,
                    "snapshots":        snaps,
                    "phase0_snapshots": _copy_snaps(snaps),   # separate object — never mutated by R1
                    "phase":            "phase0_done",
                    # reset any stale allocation state from a prior run
                    "r1_assignments":        {},
                    "r1_faculty_loads":      {},
                    "r1_picks":              {},
                    "current_assignments":   {},
                    "current_faculty_loads": {},
                    "main_queue":            [],
                    "main_queue_idx":        0,
                })
                if meta.get("mode") == "quartile":
                    msg = (f"Phase 0 complete — report saved to {OUTPUT_DIR}/. "
                           f"Tier A={sum(1 for s in students if s.tier=='A')} "
                           f"B1={sum(1 for s in students if s.tier=='B1')} "
                           f"B2={sum(1 for s in students if s.tier=='B2')} "
                           f"C={sum(1 for s in students if s.tier=='C')} "
                           f"| N_A={meta['N_A']} N_B={meta['N_B']}")
                else:
                    msg = (f"Phase 0 complete — report saved to {OUTPUT_DIR}/. "
                           f"Tier A={sum(1 for s in students if s.tier=='A')} "
                           f"B={sum(1 for s in students if s.tier=='B')} "
                           f"C={sum(1 for s in students if s.tier=='C')} "
                           f"| N_A={meta['N_A']} N_B={meta['N_B']}")
            except Exception as e:
                return f"✗ Phase 0 error: {e}", "idle", 0, {}, 0
        else:
            msg = "Phase-0 already computed (loaded from report)."
        snaps = _app_state["snapshots"]
        if not snaps:
            return msg, "phase0_done", 0, {}, 0
        marks = {i: str(snaps[i].step) for i in range(0, len(snaps), max(1, len(snaps)//10))}
        return msg, "phase0_done", len(snaps)-1, marks, len(snaps)-1

    if triggered == "btn-full":
        # Run Phase 0 if not already done
        if _app_state["phase"] not in ("phase0_done",):
            try:
                students, faculty, meta, snaps = phase0(students, faculty)
                _app_state.update({
                    "students":         students,
                    "faculty":          faculty,
                    "meta":             meta,
                    "snapshots":        snaps,
                    "phase0_snapshots": _copy_snaps(snaps),   # separate object — never mutated by R1
                    # reset any stale allocation state from a prior run
                    "r1_assignments":        {},
                    "r1_faculty_loads":      {},
                    "r1_picks":              {},
                    "current_assignments":   {},
                    "current_faculty_loads": {},
                    "main_queue":            [],
                    "main_queue_idx":        0,
                })
            except Exception as e:
                return f"✗ Phase 0 error: {e}", "idle", 0, {}, 0
        else:
            snaps = _app_state["snapshots"]
            meta  = _app_state["meta"]
            # snapshots may be None if phase0 was loaded from a report rather than run fresh
            if snaps is None:
                from .state import SnapshotList
                snaps = SnapshotList()
                _app_state["snapshots"] = snaps

        # CPI-Fill skips Round 1 entirely — run Phase 1 then pause for confirmation.
        if ALLOCATION_POLICY == "cpi_fill":
            assignments   = {s.id: None for s in students}
            faculty_loads = {f.id: 0    for f in faculty}
            try:
                assignments, faculty_loads, snaps, stats = cpi_fill_phase1(
                    students, faculty, assignments, faculty_loads, snaps,
                )
            except Exception as e:
                return f"✗ CPI-Fill Phase 1 error: {e}", "idle", 0, {}, 0
            _app_state["snapshots"]             = snaps
            _app_state["current_assignments"]   = assignments
            _app_state["current_faculty_loads"] = faculty_loads
            _app_state["phase"]                 = "cpi_phase1_done"
            n = len(snaps)
            marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}
            content = _cpi_phase1_report(stats)
            return content, "cpi_phase1_done", n - 1, marks, n - 1

        # For least_loaded / nonempty: populate Round-1 candidate lists;
        # pause for operator picks.
        r1_candidates = build_r1_candidate_lists(students, faculty)
        _app_state["r1_pending"] = r1_candidates
        _app_state["r1_picks"]   = {}
        _app_state["phase"]      = "r1"

        n = len(snaps)
        marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n//10))}
        msg = (f"Phase 0 done. Round 1: {len(r1_candidates)} faculties have "
               "1st-choice applicants — please make picks below, then click "
               "'Confirm Round-1 picks'.")
        return msg, "r1", n-1, marks, n-1

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# ---------------------------------------------------------------------------
# Callback — build Round-1 panel
# ---------------------------------------------------------------------------

@app.callback(
    Output("r1-panel", "children"),
    Input("store-phase", "data"),
    prevent_initial_call=False,
)
def cb_r1_panel(phase):
    if phase == "r1":
        student_map = {s.id: s for s in _app_state["students"]}
        faculty_map = {f.id: f for f in _app_state["faculty"]}
        candidates  = _app_state["r1_pending"]

        if not candidates:
            return html.Span("No faculties have 1st-choice applicants.", className="text-muted")

        rows = []
        for fid, sids in candidates.items():
            fac = faculty_map.get(fid)
            fac_label = f"{fac.name} ({fid})" if fac else fid
            options = []
            for sid in sids:
                s = student_map.get(sid)
                label = (f"{s.name} ({sid}) — CPI {s.cpi:.2f}, Tier {s.tier}" if s else sid)
                options.append({"label": label, "value": sid})
            rows.append(dbc.Row([
                dbc.Col(html.Strong(fac_label), md=3, className="d-flex align-items-center"),
                dbc.Col(
                    dcc.Dropdown(
                        id={"type": "r1-pick", "index": fid},
                        options=options,
                        value=sids[0],
                        clearable=False,
                    ),
                    md=9,
                ),
            ], className="mb-2"))
        rows.append(dbc.Row(dbc.Col(
            dbc.Button("Confirm Round-1 picks & continue",
                       id="btn-confirm-r1", color="success", className="mt-2"),
        )))
        return rows

    if phase == "r1_done":
        assignments = _app_state.get("r1_assignments", {})
        student_map = {s.id: s for s in _app_state["students"]}
        faculty_map = {f.id: f for f in _app_state["faculty"]}
        tier_color  = {"A": "success", "B": "warning", "C": "danger"}

        assigned = [(sid, fid) for sid, fid in assignments.items() if fid is not None]
        unassigned_count = sum(1 for fid in assignments.values() if fid is None)

        rows = []
        for sid, fid in sorted(assigned, key=lambda x: (faculty_map[x[1]].name if x[1] in faculty_map else x[1])):
            s = student_map.get(sid)
            f = faculty_map.get(fid)
            rows.append(html.Tr([
                html.Td(f.name if f else fid),
                html.Td(s.name if s else sid),
                html.Td(f"{s.cpi:.2f}" if s else "—"),
                html.Td(dbc.Badge(s.tier, color=tier_color.get(s.tier, "secondary")) if s else "—"),
            ]))

        r1_table = (
            dbc.Table([
                html.Thead(html.Tr([html.Th("Faculty"), html.Th("Student"), html.Th("CPI"), html.Th("Tier")])),
                html.Tbody(rows),
            ], bordered=True, size="sm", className="mb-3")
            if rows
            else html.P("No direct assignments in Round 1.", className="text-muted mb-3")
        )

        # All students assigned in Round 1 — ask for confirmation before finalising
        if unassigned_count == 0:
            return [
                dbc.Alert(
                    [html.Strong("All students assigned in Round 1. Round 2 skipped. "),
                     "Finalize?"],
                    color="info", className="mb-3",
                ),
                r1_table,
                dbc.Button("Finalize →", id="btn-r1-finalize", color="success"),
            ]

        proceed_label = (
            "Proceed to Main Allocation (auto-run) →"
            if ALLOCATION_POLICY == "cpi_fill"
            else "Proceed to Main Allocation (manual) →"
        )
        buttons = [
            dbc.Button(proceed_label, id="btn-proceed-main", color="success"),
        ]
        if ALLOCATION_POLICY != "cpi_fill":
            buttons.append(
                dbc.Button(
                    "Auto-run allocation →",
                    id="btn-autorun-main",
                    color="primary",
                    className="ms-2",
                )
            )

        return [
            html.P(
                [html.Strong(f"{len(assigned)} direct assignment(s)"), f" in Round 1. "
                 f"{unassigned_count} student(s) proceed to main allocation."],
                className="mb-3",
            ),
            r1_table,
            html.Div(buttons, className="d-flex"),
        ]

    if phase in ("main_alloc", "complete"):
        return html.Span("✓ Round 1 complete — main allocation in progress below.",
                         className="text-muted small")

    return html.Span("Load data and run allocation to see Round-1 picks.", className="text-muted")


# ---------------------------------------------------------------------------
# Callback — confirm Round-1 picks and run main allocation
# ---------------------------------------------------------------------------

@app.callback(
    Output("run-status",    "children", allow_duplicate=True),
    Output("store-phase",   "data",     allow_duplicate=True),
    Output("step-slider",   "max",      allow_duplicate=True),
    Output("step-slider",   "marks",    allow_duplicate=True),
    Output("step-slider",   "value",    allow_duplicate=True),
    Output("store-r1-picks","data"),
    Input("btn-confirm-r1", "n_clicks"),
    State({"type": "r1-pick", "index": dash.ALL}, "value"),
    State({"type": "r1-pick", "index": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def cb_confirm_r1(n_clicks, pick_values, pick_ids):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    r1_picks = {pid["index"]: pval for pid, pval in zip(pick_ids, pick_values)}
    _app_state["r1_picks"] = r1_picks

    students = _app_state["students"]
    faculty  = _app_state["faculty"]
    snaps    = _app_state["snapshots"]

    try:
        assignments, faculty_loads, snaps = round1(students, faculty, snaps, r1_picks)
        _app_state["r1_assignments"]   = dict(assignments)
        _app_state["r1_faculty_loads"] = dict(faculty_loads)
        _app_state["snapshots"]        = snaps
        _app_state["phase"]            = "r1_done"
    except Exception as e:
        return f"✗ Round 1 error: {e}", "r1", dash.no_update, dash.no_update, dash.no_update, r1_picks

    n = len(snaps)
    marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}
    assigned_count = sum(1 for v in assignments.values() if v is not None)
    unassigned_count = sum(1 for v in assignments.values() if v is None)
    msg = f"Round 1 complete — {assigned_count} assigned, {unassigned_count} to main allocation."
    return msg, "r1_done", n - 1, marks, n - 1, r1_picks


# ---------------------------------------------------------------------------
# Callback — reset to Round 1
# ---------------------------------------------------------------------------

@app.callback(
    Output("run-status",       "children",  allow_duplicate=True),
    Output("store-phase",      "data",      allow_duplicate=True),
    Output("step-slider",      "max",       allow_duplicate=True),
    Output("step-slider",      "marks",     allow_duplicate=True),
    Output("step-slider",      "value",     allow_duplicate=True),
    Output("main-alloc-panel", "children",  allow_duplicate=True),
    Input("btn-reset-r1", "n_clicks"),
    prevent_initial_call=True,
)
def cb_reset_r1(n_clicks):
    no_up6 = (dash.no_update,) * 6
    if not n_clicks:
        return no_up6

    allowed = ("r1", "r1_done", "main_alloc", "complete", "cpi_phase1_done")
    if _app_state["phase"] not in allowed:
        return ("⚠ Run full allocation first before resetting.",
                *([dash.no_update] * 5))

    # Restore the phase-0 checkpoint (fresh copy so subsequent runs don't
    # accumulate snapshots from prior runs).
    snaps = _copy_snaps(_app_state["phase0_snapshots"])

    _app_state["r1_picks"]              = {}
    _app_state["r1_assignments"]        = {}
    _app_state["r1_faculty_loads"]      = {}
    _app_state["current_assignments"]   = {}
    _app_state["current_faculty_loads"] = {}
    _app_state["main_queue"]            = []
    _app_state["main_queue_idx"]        = 0
    _app_state["snapshots"]             = snaps

    if snaps:
        n = len(snaps)
        marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}
        slider_max, slider_val = n - 1, n - 1
    else:
        marks, slider_max, slider_val = {}, 0, 0

    if ALLOCATION_POLICY == "cpi_fill":
        _app_state["phase"] = "phase0_done"
        msg = "Reset — Phase 0 complete. Click 'Run full allocation' to start Phase 1."
        panel = html.Span("Allocation reset. Ready to run Phase 1.", className="text-muted")
        return msg, "phase0_done", slider_max, marks, slider_val, panel

    students      = _app_state["students"]
    faculty       = _app_state["faculty"]
    r1_candidates = build_r1_candidate_lists(students, faculty)
    _app_state["r1_pending"] = r1_candidates
    _app_state["phase"]      = "r1"
    msg = (f"Reset — Round 1: {len(r1_candidates)} faculties have "
           "1st-choice applicants. Make picks below, then confirm.")
    return msg, "r1", slider_max, marks, slider_val, dash.no_update


# ---------------------------------------------------------------------------
# Callback — proceed to manual main allocation
# ---------------------------------------------------------------------------

@app.callback(
    Output("main-alloc-panel", "children"),
    Output("store-phase",      "data",     allow_duplicate=True),
    Output("step-slider",      "max",      allow_duplicate=True),
    Output("step-slider",      "marks",    allow_duplicate=True),
    Output("step-slider",      "value",    allow_duplicate=True),
    Input("btn-proceed-main",  "n_clicks"),
    prevent_initial_call=True,
)
def cb_proceed_main(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    students      = _app_state["students"]
    faculty       = _app_state["faculty"]
    meta          = _app_state["meta"]
    assignments   = dict(_app_state["r1_assignments"])
    faculty_loads = dict(_app_state["r1_faculty_loads"])
    faculty_map   = {f.id: f for f in faculty}

    # CPI-Fill: run Phase 1 then pause for confirmation before Phase 2.
    if ALLOCATION_POLICY == "cpi_fill":
        snaps = _app_state["snapshots"]
        try:
            assignments, faculty_loads, snaps, stats = cpi_fill_phase1(
                students, faculty, assignments, faculty_loads, snaps,
            )
        except Exception as e:
            return (
                html.Span(f"✗ CPI-Fill Phase 1 error: {e}", className="text-danger"),
                "r1_done",
                dash.no_update, dash.no_update, dash.no_update,
            )
        _app_state["snapshots"]             = snaps
        _app_state["current_assignments"]   = assignments
        _app_state["current_faculty_loads"] = faculty_loads
        _app_state["phase"]                 = "cpi_phase1_done"
        n = len(snaps)
        marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}
        content = _cpi_phase1_report(stats)
        return content, "cpi_phase1_done", n - 1, marks, n - 1

    # Manual allocation for least_loaded / nonempty
    # Build queue in tier priority order, each tier by CPI desc, unassigned only
    tier_order = ("A", "B1", "B2", "C") if meta.get("mode") == "quartile" else ("A", "B", "C")
    queue = []
    for tier in tier_order:
        tier_students = sorted(
            [s for s in students if s.tier == tier and assignments.get(s.id) is None],
            key=lambda s: (-s.cpi, s.id),
        )
        queue.extend(tier_students)

    _app_state["main_queue"]            = queue
    _app_state["main_queue_idx"]        = 0
    _app_state["main_run"]              = _app_state.get("main_run", 0) + 1
    _app_state["current_assignments"]   = assignments
    _app_state["current_faculty_loads"] = faculty_loads
    _app_state["phase"]                 = "main_alloc"

    if not queue:
        return (
            html.Span("All students already assigned in Round 1.", className="text-success"),
            "complete",
            dash.no_update, dash.no_update, dash.no_update,
        )

    run     = _app_state["main_run"]
    content = _render_student_picker(queue[0], faculty_map, faculty_loads, meta, 0, len(queue), run=run)
    return content, "main_alloc", dash.no_update, dash.no_update, dash.no_update


# ---------------------------------------------------------------------------
# Callback — proceed to CPI-Fill Phase 2 (after user confirmation)
# ---------------------------------------------------------------------------

@app.callback(
    Output("btn-cpi-proceed-phase2", "disabled"),
    Input("btn-cpi-proceed-phase2",  "n_clicks"),
    prevent_initial_call=True,
)
def cb_disable_cpi_proceed_btn(n_clicks):
    return bool(n_clicks)


@app.callback(
    Output("main-alloc-panel", "children",  allow_duplicate=True),
    Output("store-phase",      "data",      allow_duplicate=True),
    Output("step-slider",      "max",       allow_duplicate=True),
    Output("step-slider",      "marks",     allow_duplicate=True),
    Output("step-slider",      "value",     allow_duplicate=True),
    Input("btn-cpi-proceed-phase2", "n_clicks"),
    prevent_initial_call=True,
)
def cb_cpi_proceed_phase2(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    students      = _app_state["students"]
    faculty       = _app_state["faculty"]
    assignments   = dict(_app_state["current_assignments"])
    faculty_loads = dict(_app_state["current_faculty_loads"])
    snaps         = _app_state["snapshots"]

    try:
        assignments, snaps, phase2_skipped = cpi_fill_phase2(
            students, faculty, assignments, faculty_loads, snaps,
        )
    except Exception as e:
        return (
            html.Span(f"✗ CPI-Fill Phase 2 error: {e}", className="text-danger"),
            "cpi_phase1_done",
            dash.no_update, dash.no_update, dash.no_update,
        )

    _app_state["snapshots"]             = snaps
    _app_state["current_assignments"]   = assignments
    _app_state["current_faculty_loads"] = faculty_loads
    _app_state["phase"]                 = "complete"
    metrics = compute_metrics(
        students, assignments, len(faculty),
        faculty_ids=[f.id for f in faculty],
    )
    _app_state["metrics"] = metrics
    n = len(snaps)
    marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}
    content = _finalize_prompt(assignments, faculty_loads, faculty,
                               phase2_skipped=phase2_skipped)
    return content, "complete", n - 1, marks, n - 1


# ---------------------------------------------------------------------------
# Callback — auto-run main allocation (least_loaded / nonempty)
# ---------------------------------------------------------------------------

@app.callback(
    Output("main-alloc-panel", "children",  allow_duplicate=True),
    Output("store-phase",      "data",      allow_duplicate=True),
    Output("step-slider",      "max",       allow_duplicate=True),
    Output("step-slider",      "marks",     allow_duplicate=True),
    Output("step-slider",      "value",     allow_duplicate=True),
    Input("btn-autorun-main",  "n_clicks"),
    prevent_initial_call=True,
)
def cb_autorun_main(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    students      = _app_state["students"]
    faculty       = _app_state["faculty"]
    meta          = _app_state["meta"]
    assignments   = dict(_app_state["r1_assignments"])
    faculty_loads = dict(_app_state["r1_faculty_loads"])
    snaps         = _app_state["snapshots"]
    N_A           = meta["N_A"]
    N_B           = meta["N_B"]

    try:
        assignments, snaps = main_allocation(
            students, faculty, assignments, faculty_loads, snaps, N_A, N_B,
            policy=ALLOCATION_POLICY,
        )
    except Exception as e:
        return (
            html.Span(f"✗ Auto-run error: {e}", className="text-danger"),
            "r1_done",
            dash.no_update, dash.no_update, dash.no_update,
        )

    _app_state["snapshots"]             = snaps
    _app_state["current_assignments"]   = assignments
    _app_state["current_faculty_loads"] = faculty_loads
    _app_state["phase"]                 = "complete"
    metrics = compute_metrics(students, assignments, F=len(faculty))
    _app_state["metrics"] = metrics

    n = len(snaps)
    marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}
    content = _finalize_prompt(assignments, faculty_loads, faculty)
    return content, "complete", n - 1, marks, n - 1


# ---------------------------------------------------------------------------
# Helper — build the full allocation completion panel
# ---------------------------------------------------------------------------

def _build_completion_panel(
    assignments: dict,
    faculty_loads: dict,
    students: list,
    faculty: list,
    metrics: dict,
    label_text: str,
) -> "html.Div":
    """
    Return an html.Div with the full post-allocation view:
    summary table (with pref rank), advisor popularity table, metrics panel.
    Used by both the Round-1-only and Round-2 finalization callbacks.
    """
    faculty_map = {f.id: f for f in faculty}
    student_map = {s.id: s for s in students}

    tier_color   = {"A": "success", "B": "warning", "B1": "warning", "B2": "info", "C": "danger"}
    summary_rows = []
    for sid, fac_id in sorted(
        assignments.items(),
        key=lambda x: (
            student_map.get(x[0], Student(x[0], "", 0, [])).tier or "Z",
            -(student_map[x[0]].cpi if x[0] in student_map else 0),
        ),
    ):
        s = student_map.get(sid)
        f = faculty_map.get(fac_id) if fac_id else None
        try:
            rank = s.preferences.index(fac_id) + 1 if (s and fac_id) else None
        except ValueError:
            rank = None
        summary_rows.append(html.Tr([
            html.Td(s.name if s else sid),
            html.Td(f"{s.cpi:.2f}" if s else "—"),
            html.Td(dbc.Badge(s.tier, color=tier_color.get(s.tier, "secondary")) if s else "—"),
            html.Td(f.name if f else html.Span("Unassigned", className="text-danger")),
            html.Td(str(rank) if rank else "—", className="text-center"),
        ]))

    pop: dict = {1: {}, 2: {}, 3: {}}
    for s in students:
        for rank_idx, pfid in enumerate(s.preferences[:3], start=1):
            entry = pop[rank_idx].setdefault(pfid, {"total": 0})
            entry["total"] += 1
            entry[s.tier] = entry.get(s.tier, 0) + 1
    all_pop_fids = sorted(
        {pfid for r in pop.values() for pfid in r},
        key=lambda pfid: -max(pop[r].get(pfid, {}).get("total", 0) for r in (1, 2, 3)),
    )

    def _cell(pfid, rank_idx):
        entry = pop[rank_idx].get(pfid)
        if not entry or entry["total"] == 0:
            return html.Td("—", className="text-muted text-center")
        tier_parts = [f"{t}:{entry[t]}" for t in ("A", "B1", "B2", "B", "C") if entry.get(t)]
        return html.Td([
            html.Span(str(entry["total"]), className="fw-bold"),
            html.Br(),
            html.Span("  ".join(tier_parts), className="text-muted",
                      style={"fontSize": "0.78em"}),
        ], className="text-center")

    pop_rows = [
        html.Tr([
            html.Td(faculty_map[pfid].name if pfid in faculty_map else pfid),
            _cell(pfid, 1), _cell(pfid, 2), _cell(pfid, 3),
        ])
        for pfid in all_pop_fids
    ]
    pop_table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("Advisor"),
            html.Th("Choice #1", className="text-center"),
            html.Th("Choice #2", className="text-center"),
            html.Th("Choice #3", className="text-center"),
        ])),
        html.Tbody(pop_rows),
    ], bordered=True, hover=True, striped=True, size="sm")

    metrics_panel = _render_metrics_panel(metrics)
    assigned_count   = sum(1 for v in assignments.values() if v is not None)
    unassigned_count = sum(1 for v in assignments.values() if v is None)
    empty_labs       = sum(1 for f in faculty if faculty_loads.get(f.id, 0) == 0)

    return html.Div([
        dbc.Alert(
            [html.Strong(f"✓ {label_text}. "),
             f"{assigned_count} assigned, {unassigned_count} unassigned, "
             f"{empty_labs} empty lab{'s' if empty_labs != 1 else ''}."],
            color="success", className="mb-3",
        ),
        dbc.Button("⬇ Save report (CSV)", id="btn-save-report",
                   color="outline-secondary", size="sm", className="mb-3"),
        dbc.Table([
            html.Thead(html.Tr([
                html.Th("Student"), html.Th("CPI"),
                html.Th("Tier"), html.Th("Advisor"),
                html.Th("Pref Rank", className="text-center"),
            ])),
            html.Tbody(summary_rows),
        ], bordered=True, hover=True, striped=True, size="sm"),
        html.Hr(),
        html.H5("Advisor popularity", className="mt-2 mb-0"),
        html.P("Total students per advisor per choice (tier breakdown: A · B · C).",
               className="text-muted small"),
        pop_table,
        html.Hr(),
        metrics_panel,
    ])


def _cpi_phase1_report(stats: dict) -> "html.Div":
    """
    Return the Phase 1 completion panel shown after CPI-Fill Phase 1 stops.
    Displays assigned / unassigned / empty-labs counts and a proceed button.
    """
    assigned   = stats["total_students"] - stats["unassigned_count"]
    unassigned = stats["unassigned_count"]
    empty_labs = stats["empty_labs_count"]
    return html.Div([
        dbc.Alert(
            [html.Strong("Phase 1 complete. "),
             f"{assigned} assigned, {unassigned} unassigned, "
             f"{empty_labs} empty lab{'s' if empty_labs != 1 else ''}."],
            color="info", className="mb-3",
        ),
        dbc.Button("Proceed to Phase 2 →", id="btn-cpi-proceed-phase2",
                   color="primary"),
    ])


def _finalize_prompt(
    assignments: dict,
    faculty_loads: dict,
    faculty: list,
    phase2_skipped: bool = False,
) -> "html.Div":
    """
    Return the 'Allocation complete — Finalize?' confirmation widget shown
    after Round 2 (manual, auto-run, or CPI-Fill) completes.
    """
    assigned_count   = sum(1 for v in assignments.values() if v is not None)
    unassigned_count = sum(1 for v in assignments.values() if v is None)
    empty_labs       = sum(1 for f in faculty if faculty_loads.get(f.id, 0) == 0)
    skip_note        = " Round 2 being skipped." if phase2_skipped else ""
    return html.Div([
        dbc.Alert(
            [html.Strong("✓ Allocation complete. "),
             f"{assigned_count} assigned, {unassigned_count} unassigned, "
             f"{empty_labs} empty lab{'s' if empty_labs != 1 else ''}.{skip_note} Finalize?"],
            color="success", className="mb-3",
        ),
        dbc.Button("Finalize →", id="btn-finalize-main", color="success"),
    ])


# ---------------------------------------------------------------------------
# Callback — finalise a Round-1-only allocation (all students assigned in R1)
# ---------------------------------------------------------------------------

@app.callback(
    Output("main-alloc-panel", "children",  allow_duplicate=True),
    Output("store-phase",      "data",      allow_duplicate=True),
    Output("step-slider",      "max",       allow_duplicate=True),
    Output("step-slider",      "marks",     allow_duplicate=True),
    Output("step-slider",      "value",     allow_duplicate=True),
    Input("btn-r1-finalize",   "n_clicks"),
    prevent_initial_call=True,
)
def cb_r1_finalize(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    students      = _app_state["students"]
    faculty       = _app_state["faculty"]
    assignments   = dict(_app_state["r1_assignments"])
    faculty_loads = dict(_app_state["r1_faculty_loads"])
    snaps         = _app_state["snapshots"]

    # Append Final snapshot
    step = (snaps.last().step + 1) if snaps and snaps.last() else 1
    snaps.append(AllocationSnapshot(
        step=step,
        phase="Final",
        event=(f"Allocation complete (Round 1 only) | "
               f"assigned={sum(1 for v in assignments.values() if v is not None)} "
               f"| unassigned=0"),
        assignments=dict(assignments),
        faculty_loads=dict(faculty_loads),
        unassigned=set(),
    ))

    _app_state["snapshots"]             = snaps
    _app_state["current_assignments"]   = assignments
    _app_state["current_faculty_loads"] = faculty_loads
    _app_state["phase"]                 = "complete"

    metrics = compute_metrics(students, assignments, F=len(faculty))
    _app_state["metrics"] = metrics

    content = _build_completion_panel(
        assignments, faculty_loads, students, faculty, metrics,
        "Allocation complete (Round 1 only)",
    )
    n = len(snaps)
    marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}
    return content, "complete", n - 1, marks, n - 1


# ---------------------------------------------------------------------------
# Callback — finalise a Round-2 allocation (manual, auto-run, or CPI-Fill)
# ---------------------------------------------------------------------------

@app.callback(
    Output("main-alloc-panel", "children", allow_duplicate=True),
    Input("btn-finalize-main", "n_clicks"),
    prevent_initial_call=True,
)
def cb_finalize_main(n_clicks):
    if not n_clicks:
        return dash.no_update
    assignments   = _app_state["current_assignments"]
    faculty_loads = _app_state["current_faculty_loads"]
    students      = _app_state["students"]
    faculty       = _app_state["faculty"]
    metrics       = _app_state.get("metrics") or compute_metrics(
        students, assignments, F=len(faculty)
    )
    return _build_completion_panel(
        assignments, faculty_loads, students, faculty, metrics,
        "Allocation complete",
    )


# ---------------------------------------------------------------------------
# Helper — execute one manual pick (shared by direct pick + override confirm)
# ---------------------------------------------------------------------------

def _do_pick(fid: str) -> tuple:
    """
    Record the assignment of the current queue student to faculty ``fid``,
    append a snapshot, advance the queue pointer, and return the 7-tuple
    (panel_content, phase, slider_max, slider_marks, slider_value,
     toast_children, toast_is_open) expected by both pick callbacks.
    """
    queue         = _app_state["main_queue"]
    idx           = _app_state["main_queue_idx"]
    student       = queue[idx]
    students      = _app_state["students"]
    faculty       = _app_state["faculty"]
    meta          = _app_state["meta"]
    faculty_map   = {f.id: f for f in faculty}
    assignments   = _app_state["current_assignments"]
    faculty_loads = _app_state["current_faculty_loads"]
    current_run   = _app_state.get("main_run", 0)

    # Record assignment
    assignments[student.id] = fid
    faculty_loads[fid]      = faculty_loads.get(fid, 0) + 1

    # Append snapshot
    snaps = _app_state["snapshots"]
    step  = (snaps.last().step + 1) if snaps and snaps.last() else 1
    try:
        rank = student.preferences.index(fid) + 1
    except ValueError:
        rank = None
    fac         = faculty_map.get(fid)
    phase_label = f"Class{student.tier}"
    unassigned  = {s.id for s in students if assignments.get(s.id) is None}
    snaps.append(AllocationSnapshot(
        step=step,
        phase=phase_label,
        event=(
            f"{phase_label} | {student.name} ({student.id}, Tier {student.tier}, "
            f"CPI {student.cpi:.2f}) → {fac.name if fac else fid} ({fid}) "
            f"| pref rank {rank} | load now {faculty_loads[fid]}"
        ),
        assignments=dict(assignments),
        faculty_loads=dict(faculty_loads),
        unassigned=set(unassigned),
        preference_rank={student.id: rank} if rank else None,
    ))

    new_idx = idx + 1
    _app_state["main_queue_idx"] = new_idx

    # ---- All done ----
    if new_idx >= len(queue):
        still_unassigned = [s.id for s in students if assignments.get(s.id) is None]
        snaps.append(AllocationSnapshot(
            step=step + 1,
            phase="Final",
            event=(f"Allocation complete | assigned={len(assignments)-len(still_unassigned)} "
                   f"| unassigned={len(still_unassigned)}"),
            assignments=dict(assignments),
            faculty_loads=dict(faculty_loads),
            unassigned=set(still_unassigned),
        ))
        _app_state["phase"] = "complete"

        # Compute and store metrics
        metrics = compute_metrics(
            students, assignments, len(faculty),
            faculty_ids=[f.id for f in faculty],
        )
        _app_state["metrics"] = metrics

        n = len(snaps)
        marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}

        assigned_count = len(assignments) - len(still_unassigned)
        empty_labs     = sum(1 for f in faculty if faculty_loads.get(f.id, 0) == 0)
        metrics_panel  = _render_metrics_panel(metrics)

        content = html.Div([
            dbc.Alert(
                [html.Strong("✓ Main allocation complete. "),
                 f"{assigned_count} assigned, "
                 f"{len(still_unassigned)} unassigned, "
                 f"{empty_labs} empty lab{'s' if empty_labs != 1 else ''}."],
                color="success", className="mb-3",
            ),
            dbc.Button("⬇ Save report (CSV)", id="btn-save-report",
                       color="outline-secondary", size="sm", className="mb-3"),
            dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Student"), html.Th("CPI"),
                    html.Th("Tier"),    html.Th("Advisor"),
                ])),
                html.Tbody(summary_rows),
            ], bordered=True, hover=True, striped=True, size="sm"),
            html.Hr(),
            html.H5("Advisor popularity", className="mt-2 mb-0"),
            html.P("Total students per advisor per choice (tier breakdown: A · B · C).",
                   className="text-muted small"),
            pop_table,
            html.Hr(),
            metrics_panel,
        ])
        toast_msg = [html.Strong(student.name), f" → {fac.name if fac else fid}"]
        return content, "complete", n - 1, marks, n - 1, toast_msg, True

    # ---- Next student ----
    picked_fac   = faculty_map.get(fid)
    toast_msg    = [html.Strong(student.name), f" → {picked_fac.name if picked_fac else fid}"]
    next_student = queue[new_idx]
    content      = _render_student_picker(
        next_student, faculty_map, faculty_loads, meta,
        new_idx, len(queue), run=current_run,
    )
    n     = len(snaps)
    marks = {i: str(snaps[i].step) for i in range(0, n, max(1, n // 10))}
    return content, "main_alloc", n - 1, marks, n - 1, toast_msg, True


# ---------------------------------------------------------------------------
# Callback — manual main allocation pick
# ---------------------------------------------------------------------------

@app.callback(
    Output("main-alloc-panel",    "children",  allow_duplicate=True),
    Output("store-phase",         "data",      allow_duplicate=True),
    Output("step-slider",         "max",       allow_duplicate=True),
    Output("step-slider",         "marks",     allow_duplicate=True),
    Output("step-slider",         "value",     allow_duplicate=True),
    Output("toast-picked",        "children",  allow_duplicate=True),
    Output("toast-picked",        "is_open",   allow_duplicate=True),
    Output("modal-confirm-pick",  "is_open",   allow_duplicate=True),
    Output("modal-confirm-body",  "children",  allow_duplicate=True),
    Output("store-pending-pick",  "data",      allow_duplicate=True),
    Input({"type": "main-pick", "index": dash.ALL, "step": dash.ALL, "run": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def cb_main_alloc_pick(n_clicks_list):
    _no_update = (dash.no_update,) * 10
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return _no_update

    triggered_value = ctx.triggered[0].get("value") if ctx.triggered else None
    if not triggered_value:
        return _no_update

    if _app_state["phase"] != "main_alloc":
        return _no_update

    fid         = triggered["index"]
    queue       = _app_state["main_queue"]
    idx         = _app_state["main_queue_idx"]
    current_run = _app_state.get("main_run", 0)
    if triggered.get("step") != idx or triggered.get("run") != current_run:
        return _no_update
    if idx >= len(queue):
        return _no_update

    student       = queue[idx]
    faculty       = _app_state["faculty"]
    meta          = _app_state["meta"]
    faculty_map   = {f.id: f for f in faculty}
    faculty_loads = _app_state["current_faculty_loads"]

    # Determine protocol pick (per active allocation policy)
    advisors, _, _ = _compute_eligible_advisors(student, faculty_map, faculty_loads, meta)
    cap_fids       = [f for f, _, _, _, at_cap in advisors if not at_cap]
    proto_result   = _protocol_choice(student, cap_fids, faculty_map, faculty_loads)
    protocol_fid   = proto_result[0] if proto_result else None

    # ---- Protocol pick or no recommendation: execute immediately ----
    if fid == protocol_fid or protocol_fid is None:
        result = _do_pick(fid)
        return (*result, False, dash.no_update, dash.no_update)

    # ---- Override: show confirmation modal ----
    chosen_fac   = faculty_map.get(fid)
    protocol_fac = faculty_map.get(protocol_fid)
    chosen_load  = faculty_loads.get(fid, 0)
    proto_load   = faculty_loads.get(protocol_fid, 0)

    try:
        chosen_rank = student.preferences.index(fid) + 1
    except ValueError:
        chosen_rank = None
    try:
        proto_rank = student.preferences.index(protocol_fid) + 1
    except ValueError:
        proto_rank = None

    def _rank_label(r):
        return f"Choice #{r}" if r else "outside preferences"

    modal_body = html.Div([
        dbc.Alert(
            [html.Strong("You are selecting a different advisor than the protocol recommends."),
             " Please confirm your override."],
            color="warning", className="mb-3",
        ),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div("★ Protocol recommendation", className="text-warning fw-bold mb-1"),
                html.H6(protocol_fac.name if protocol_fac else protocol_fid),
                html.Div(_rank_label(proto_rank),  className="text-muted small"),
                html.Div(f"Load: {proto_load}/{protocol_fac.max_load if protocol_fac else '?'}",
                         className="text-muted small"),
            ]), color="warning", outline=True), md=6, className="mb-2"),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.Div("Your selection", className="text-danger fw-bold mb-1"),
                html.H6(chosen_fac.name if chosen_fac else fid),
                html.Div(_rank_label(chosen_rank), className="text-muted small"),
                html.Div(f"Load: {chosen_load}/{chosen_fac.max_load if chosen_fac else '?'}",
                         className="text-muted small"),
            ]), color="danger", outline=True), md=6, className="mb-2"),
        ]),
    ])
    pending = {"fid": fid, "idx": idx, "run": current_run}
    return (
        dash.no_update, dash.no_update, dash.no_update, dash.no_update,
        dash.no_update, dash.no_update, dash.no_update,
        True, modal_body, pending,
    )


# ---------------------------------------------------------------------------
# Callback — override confirmation modal
# ---------------------------------------------------------------------------

@app.callback(
    Output("main-alloc-panel",   "children",  allow_duplicate=True),
    Output("store-phase",        "data",      allow_duplicate=True),
    Output("step-slider",        "max",       allow_duplicate=True),
    Output("step-slider",        "marks",     allow_duplicate=True),
    Output("step-slider",        "value",     allow_duplicate=True),
    Output("toast-picked",       "children",  allow_duplicate=True),
    Output("toast-picked",       "is_open",   allow_duplicate=True),
    Output("modal-confirm-pick", "is_open",   allow_duplicate=True),
    Input("btn-confirm-override", "n_clicks"),
    Input("btn-cancel-override",  "n_clicks"),
    State("store-pending-pick",   "data"),
    prevent_initial_call=True,
)
def cb_confirm_override(n_confirm, n_cancel, pending):
    _no_update = (dash.no_update,) * 8
    if not ctx.triggered_id:
        return _no_update

    # Cancel — just close the modal
    if ctx.triggered_id == "btn-cancel-override":
        return (*([dash.no_update] * 7), False)

    # Confirm — execute the pending pick
    if not pending or _app_state["phase"] != "main_alloc":
        return _no_update

    # Validate that the pending pick still matches the current queue position
    current_run = _app_state.get("main_run", 0)
    if pending.get("idx") != _app_state["main_queue_idx"] or pending.get("run") != current_run:
        return _no_update

    result = _do_pick(pending["fid"])
    return (*result, False)   # close modal after executing


# ---------------------------------------------------------------------------
# Callback — play button
# ---------------------------------------------------------------------------

@app.callback(
    Output("play-interval", "disabled"),
    Output("store-playing",  "data"),
    Input("btn-play", "n_clicks"),
    State("store-playing", "data"),
    prevent_initial_call=True,
)
def cb_toggle_play(n, playing):
    new_state = not playing
    return not new_state, new_state   # interval disabled = not playing


@app.callback(
    Output("step-slider", "value", allow_duplicate=True),
    Input("play-interval", "n_intervals"),
    State("step-slider", "value"),
    State("step-slider", "max"),
    State("store-playing", "data"),
    prevent_initial_call=True,
)
def cb_advance_slider(_, current, max_val, playing):
    if not playing:
        return dash.no_update
    next_val = current + 1
    if next_val > max_val:
        return max_val
    return next_val


# ---------------------------------------------------------------------------
# Callbacks — visualisation panels (all linked to step slider)
# ---------------------------------------------------------------------------

@app.callback(
    Output("graph-bipartite", "figure"),
    Output("graph-load",      "figure"),
    Output("graph-stats",     "figure"),
    Output("graph-log",       "figure"),
    Input("step-slider", "value"),
    prevent_initial_call=False,
)
def cb_update_graphs(step_idx):
    snaps    = _app_state.get("snapshots")
    students = _app_state.get("students", [])
    faculty  = _app_state.get("faculty",  [])
    meta     = _app_state.get("meta",     {})

    empty = go.Figure().update_layout(
        title="No data yet — load files and run allocation",
        height=300,
    )

    if not snaps or not students or not faculty:
        return empty, empty, empty, empty

    step_idx = max(0, min(step_idx or 0, len(snaps)-1))
    snap = snaps[step_idx]
    new_fid = _new_fid_from_snap(snap)

    fig_bp    = bipartite_graph(snap, students, faculty)
    fig_load  = load_bar_chart(snap, faculty, meta, new_fid)
    fig_stats = statistics_panel(snap, students, faculty, meta)
    fig_log   = step_log_table(snaps, snap.step)

    return fig_bp, fig_load, fig_stats, fig_log


# ---------------------------------------------------------------------------
# Callback — HTML export button
# ---------------------------------------------------------------------------

@app.callback(
    Output("run-status", "children", allow_duplicate=True),
    Input("btn-html", "n_clicks"),
    prevent_initial_call=True,
)
def cb_export_html(n):
    snaps    = _app_state.get("snapshots")
    students = _app_state.get("students", [])
    faculty  = _app_state.get("faculty",  [])
    meta     = _app_state.get("meta",     {})

    if not snaps or not students or not faculty:
        return "⚠ Run allocation first before exporting."

    out_path = Path(OUTPUT_DIR) / "allocation_output.html"
    try:
        run_html_export(students, faculty, meta, snaps, str(out_path))
        return f"✓ HTML exported to {out_path}"
    except Exception as e:
        return f"✗ Export error: {e}"


# ---------------------------------------------------------------------------
# Callback — Phase-0 data modal
# ---------------------------------------------------------------------------

@app.callback(
    Output("modal-phase0",      "is_open"),
    Output("modal-phase0-body", "children"),
    Input("btn-view-phase0",          "n_clicks"),
    Input("btn-close-phase0-modal",   "n_clicks"),
    State("modal-phase0", "is_open"),
    prevent_initial_call=True,
)
def cb_phase0_modal(open_clicks, close_clicks, is_open):
    triggered = ctx.triggered_id
    if triggered == "btn-close-phase0-modal":
        return False, dash.no_update

    meta     = _app_state.get("meta", {})
    students = _app_state.get("students", [])

    if not meta or not students:
        return True, html.Span("No Phase-0 data yet — run Phase 0 first.", className="text-muted")

    # Meta summary table (mode-aware labels)
    if meta.get("mode") == "quartile":
        meta_rows = [
            ("Cohort size",             meta.get("cohort_size", "—")),
            ("Faculty count",           meta.get("faculty_count", "—")),
            ("Mode",                    meta.get("mode", "—")),
            (f"p{meta.get('p_low_pct', '?')} (C / B2 cutoff)", meta.get("p_low", "—")),
            ("p50 (B2 / B1 cutoff)",    meta.get("p_mid", "—")),
            (f"p{meta.get('p_high_pct', '?')} (B1 / A cutoff)", meta.get("p_high", "—")),
            ("Grace ±",                 meta.get("grace", "—")),
            ("N_A",                     meta.get("N_A", "—")),
            ("N_B (B1 & B2)",           meta.get("N_B", "—")),
            ("max_load",                meta.get("common_max_load", "—")),
        ]
    else:
        meta_rows = [
            ("Cohort size",    meta.get("cohort_size", "—")),
            ("Faculty count",  meta.get("faculty_count", "—")),
            ("Mode",           meta.get("mode", "—")),
            (f"p{meta.get('p_low_pct', '?')} (B cutoff)", meta.get("p_low", "—")),
            (f"p{meta.get('p_high_pct', '?')} (A cutoff)", meta.get("p_high", "—")),
            ("Grace ±",        meta.get("grace", "—")),
            ("N_A",            meta.get("N_A", "—")),
            ("N_B",            meta.get("N_B", "—")),
            ("max_load",       meta.get("common_max_load", "—")),
        ]
    meta_table = dbc.Table([
        html.Thead(html.Tr([html.Th("Parameter"), html.Th("Value")])),
        html.Tbody([html.Tr([html.Td(k), html.Td(str(v))]) for k, v in meta_rows]),
    ], bordered=True, size="sm", className="mb-4")

    # Per-student tier table
    tier_rows = [
        html.Tr([
            html.Td(s.id),
            html.Td(s.name),
            html.Td(f"{s.cpi:.2f}"),
            html.Td(dbc.Badge(
                s.tier,
                color={"A": "success", "B": "warning", "B1": "warning", "B2": "info", "C": "danger"}.get(s.tier, "secondary"),
            )),
            html.Td(str(s.n_tier) if s.n_tier is not None else "—"),
        ])
        for s in sorted(students, key=lambda x: -x.cpi)
    ]
    student_table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("ID"), html.Th("Name"), html.Th("CPI"),
            html.Th("Tier"), html.Th("N (pref protection)"),
        ])),
        html.Tbody(tier_rows),
    ], bordered=True, hover=True, striped=True, size="sm")

    body = [
        html.H6("Cohort Parameters", className="fw-bold"),
        meta_table,
        html.H6("Student Tier Assignments", className="fw-bold"),
        student_table,
    ]
    return True, body


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------

@app.callback(
    Output("download-report", "data"),
    Input("btn-save-report", "n_clicks"),
    prevent_initial_call=True,
)
def cb_save_report(n_clicks):
    assignments = _app_state.get("current_assignments") or {}
    students    = _app_state.get("students", [])
    faculty_map = {f.id: f for f in _app_state.get("faculty", [])}
    student_map = {s.id: s for s in students}

    lines = ["student_id,student_name,cpi,tier,advisor_id,advisor_name"]
    for sid, fid in sorted(assignments.items()):
        s = student_map.get(sid)
        f = faculty_map.get(fid) if fid else None
        lines.append(",".join([
            sid,
            (s.name if s else ""),
            (f"{s.cpi:.2f}" if s else ""),
            (s.tier if s else ""),
            fid or "",
            (f.name if f else ""),
        ]))
    csv_text = "\n".join(lines)
    return dcc.send_string(csv_text, filename="allocation_report.csv")


@app.callback(
    Output("download-metrics", "data"),
    Input("btn-download-metrics", "n_clicks"),
    prevent_initial_call=True,
)
def cb_download_metrics(n_clicks):
    metrics     = _app_state.get("metrics") or {}
    students    = _app_state.get("students", [])
    student_map = {s.id: s for s in students}
    per_student = metrics.get("per_student", {})

    lines = ["student_id,name,tier,n_tier,assigned_rank,within_window,npss_score,cpi_weight,psi_score"]
    for sid, sd in sorted(per_student.items()):
        s      = student_map.get(sid)
        name   = s.name if s else ""
        n_tier = sd.get("n_tier")
        rank   = sd.get("assigned_rank")
        prefs_len  = len(s.preferences) if s else 0
        n_eff      = n_tier if n_tier is not None else prefs_len
        within_win = 1 if (rank is not None and n_eff and rank <= n_eff) else 0
        lines.append(",".join([
            sid,
            name,
            sd.get("tier", ""),
            str(n_tier) if n_tier is not None else "",
            str(rank)   if rank   is not None else "",
            str(within_win),
            f"{sd.get('npss_score', 0.0):.6f}",
            f"{sd.get('cpi_weight', 0.0):.6f}",
            f"{sd.get('psi_score',  0.0):.6f}",
        ]))
    csv_text = "\n".join(lines)
    return dcc.send_string(csv_text, filename="metrics_report.csv")


def _run_html_mode():
    """
    Non-interactive HTML export:
    Load default files → Phase 0 → Round 1 (auto) → Main → export.
    """
    print("HTML mode: loading data from default paths …")
    students = load_students(DEFAULT_STUDENTS_PATH)
    faculty  = load_faculty(DEFAULT_FACULTY_PATH)
    validate_preferences(students, faculty)

    if STARTUP_MODE == "from_report":
        from pathlib import Path as _P
        students, meta = load_phase0_report(
            _P(PHASE0_REPORT_DIR) / "phase0_report.csv",
            _P(PHASE0_REPORT_DIR) / "phase0_meta.csv",
        )
        print(f"  Phase-0 report loaded from {PHASE0_REPORT_DIR}")
        # refill max_load for faculty
        from .allocation import phase0 as _p0
        _, faculty, _, _ = _p0(students, faculty)
    else:
        pass  # Phase 0 handled inside run_full_allocation

    assignments, snaps, meta, metrics = run_full_allocation(
        students, faculty,
        out_dir=OUTPUT_DIR if STARTUP_MODE == "full" else None,
        policy=ALLOCATION_POLICY,
    )
    _app_state["metrics"] = metrics

    out_path = Path(OUTPUT_DIR) / "allocation_output.html"
    run_html_export(students, faculty, meta, snaps, str(out_path))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MS Thesis Advisor Allocation — Dash UI")
    parser.add_argument(
        "--policy",
        default=None,
        choices=["least_loaded", "nonempty", "cpi_fill"],
        help=(
            "Override the allocation policy set in ALLOCATION_POLICY.\n"
            "  least_loaded : least-loaded eligible faculty, tie-broken by preference rank.\n"
            "  nonempty     : prefer the highest-preferred empty lab; fall back to\n"
            "                 highest-preferred faculty with remaining capacity.\n"
            "  cpi_fill     : two-phase procedure — Phase 1 in CPI order with N_tier\n"
            "                 cap until stopping condition fires; Phase 2 assigns each\n"
            "                 remaining student to their highest-preferred empty lab."
        ),
    )
    args = parser.parse_args()

    # Apply CLI policy override so allocation and dashboard highlighting stay in sync
    if args.policy is not None:
        ALLOCATION_POLICY = args.policy

    if OUTPUT_MODE == "html":
        _run_html_mode()
    else:
        app.run(host=DASH_HOST, port=DASH_PORT, debug=DASH_DEBUG)
