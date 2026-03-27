"""
allocator — MS Thesis Advisor Allocation package.

Submodules
----------
state        : Student, Faculty, AllocationSnapshot, SnapshotList
data_loader  : load_students, load_faculty, save/load_phase0_report
allocation   : phase0, round1, main_allocation, run_full_allocation
visualizer   : bipartite_graph, load_bar_chart, step_log_table, statistics_panel
app          : Dash application entry-point
"""

from .state import Student, Faculty, AllocationSnapshot, SnapshotList
from .allocation import phase0, round1, main_allocation, run_full_allocation
from .data_loader import (
    load_students, load_faculty,
    save_phase0_report, load_phase0_report,
    validate_preferences,
)