from dataclasses import dataclass
from typing import List, Dict
from collections import defaultdict

import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.express as px
import pandas as pd

from allocation import Student, Advisor, class_wise_allocation

app = dash.Dash(__name__)


# Helper to build default advisors & students
def default_advisors():
    return [f"A{i+1}" for i in range(5)]


def default_students():
    return [f"S{i+1}" for i in range(10)]


app.layout = html.Div(
    [
        html.H1("Advisor Allocation Visual Tool"),
        html.Div(
            [
                html.H2("Global Parameters"),
                html.Label("Max load per advisor"),
                dcc.Input(id="max-load", type="number", min=1, max=10, step=1, value=3),
                html.Br(),
                html.Label("Class A cap N_A"),
                dcc.Input(id="N-A", type="number", min=1, max=10, step=1, value=2),
                html.Br(),
                html.Label("Class B cap N_B"),
                dcc.Input(id="N-B", type="number", min=1, max=10, step=1, value=2),
            ],
            style={"margin-bottom": "20px"},
        ),
        html.Div(
            [
                html.H2("Advisors"),
                html.Label("Number of advisors"),
                dcc.Input(
                    id="num-advisors", type="number", min=1, max=50, step=1, value=5
                ),
                html.Button("Generate advisors", id="gen-advisors", n_clicks=0),
                dash_table.DataTable(
                    id="advisors-table",
                    columns=[
                        {"name": "Advisor ID", "id": "id", "editable": True},
                        {
                            "name": "Max load",
                            "id": "max_load",
                            "type": "numeric",
                            "editable": True,
                        },
                    ],
                    data=[{"id": aid, "max_load": 3} for aid in default_advisors()],
                    editable=True,
                ),
            ],
            style={"margin-bottom": "20px"},
        ),
        html.Div(
            [
                html.H2("Students"),
                html.Label("Number of students"),
                dcc.Input(
                    id="num-students", type="number", min=1, max=100, step=1, value=10
                ),
                html.Button("Generate students", id="gen-students", n_clicks=0),
                dash_table.DataTable(
                    id="students-table",
                    columns=[
                        {"name": "Student ID", "id": "id", "editable": True},
                        {
                            "name": "CPI",
                            "id": "cpi",
                            "type": "numeric",
                            "editable": True,
                        },
                        {
                            "name": "Class tier",
                            "id": "class_tier",
                            "presentation": "dropdown",
                        },
                        {
                            "name": "Preferences (comma-separated advisor IDs)",
                            "id": "prefs",
                            "editable": True,
                        },
                    ],
                    data=[
                        {
                            "id": sid,
                            "cpi": 8.0,
                            "class_tier": "A",
                            "prefs": ",".join(default_advisors()[:3]),
                        }
                        for sid in default_students()
                    ],
                    editable=True,
                    dropdown={
                        "class_tier": {
                            "options": [
                                {"label": "A", "value": "A"},
                                {"label": "B", "value": "B"},
                                {"label": "C", "value": "C"},
                            ]
                        }
                    },
                    style_table={"overflowX": "auto"},
                ),
            ],
            style={"margin-bottom": "20px"},
        ),
        html.Button(
            "Run allocation",
            id="run-allocation",
            n_clicks=0,
            style={"margin-bottom": "20px"},
        ),
        html.H2("Results"),
        html.Div(id="assignments-table-container"),
        html.Div(
            [
                html.H3("Advisor Loads"),
                dcc.Graph(id="advisor-loads-graph"),
            ]
        ),
    ]
)

# Callbacks


@app.callback(
    Output("advisors-table", "data"),
    Input("gen-advisors", "n_clicks"),
    State("num-advisors", "value"),
    State("max-load", "value"),
    prevent_initial_call=True,
)
def generate_advisors(n_clicks, num_advisors, max_load):
    if num_advisors is None:
        return dash.no_update
    return [{"id": f"A{i+1}", "max_load": max_load} for i in range(num_advisors)]


@app.callback(
    Output("students-table", "data"),
    Input("gen-students", "n_clicks"),
    State("num-students", "value"),
    State("advisors-table", "data"),
    prevent_initial_call=True,
)
def generate_students(n_clicks, num_students, advisors_data):
    if num_students is None or not advisors_data:
        return dash.no_update
    advisor_ids = [row["id"] for row in advisors_data]
    default_prefs = ",".join(advisor_ids[:3])
    data = []
    for i in range(num_students):
        tier = (
            "A"
            if i < num_students // 3
            else ("B" if i < 2 * num_students // 3 else "C")
        )
        data.append(
            {
                "id": f"S{i+1}",
                "cpi": 8.0,
                "class_tier": tier,
                "prefs": default_prefs,
            }
        )
    return data


@app.callback(
    Output("assignments-table-container", "children"),
    Output("advisor-loads-graph", "figure"),
    Input("run-allocation", "n_clicks"),
    State("advisors-table", "data"),
    State("students-table", "data"),
    State("N-A", "value"),
    State("N-B", "value"),
    prevent_initial_call=True,
)
def run_allocation_cb(n_clicks, advisors_data, students_data, N_A, N_B):
    if not advisors_data or not students_data:
        return dash.no_update, dash.no_update

    # Build advisors dict
    advisors = {
        row["id"]: Advisor(id=row["id"], max_load=int(row["max_load"]))
        for row in advisors_data
    }

    # Build students list
    students = []
    for row in students_data:
        sid = row["id"]
        cpi = float(row.get("cpi", 0.0))
        tier = row.get("class_tier", "A")
        pref_str = row.get("prefs", "")
        prefs = [p.strip() for p in pref_str.split(",") if p.strip() in advisors]
        students.append(Student(id=sid, cpi=cpi, class_tier=tier, preferences=prefs))

    result = class_wise_allocation(students, advisors, N_A=int(N_A), N_B=int(N_B))

    # Build assignments table
    df_assign = pd.DataFrame(
        [
            {
                "student": s.id,
                "CPI": s.cpi,
                "class": s.class_tier,
                "assigned_advisor": result.assignments.get(s.id, None),
            }
            for s in students
        ]
    ).sort_values(["class", "CPI"], ascending=[True, False])

    assignments_table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in df_assign.columns],
        data=df_assign.to_dict("records"),
        style_table={"overflowX": "auto"},
    )

    # Advisor loads figure
    df_loads = pd.DataFrame(
        [{"advisor": aid, "load": load} for aid, load in result.advisor_loads.items()]
    )
    fig = px.bar(df_loads, x="advisor", y="load", title="Advisor Loads")

    return assignments_table, fig


if __name__ == "__main__":
    app.run_server(debug=True)
