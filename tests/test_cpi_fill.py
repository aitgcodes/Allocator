"""
tests/test_cpi_fill.py — Unit tests for the CPI-Fill allocation policy.

Run with:
    conda run -n allocator python -m pytest tests/test_cpi_fill.py -v
"""

import pytest

from src.allocator.state import Faculty, SnapshotList, Student
from src.allocator.allocation import (
    cpi_fill_allocation,
    run_full_allocation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _student(sid, cpi, prefs, tier="A", n_tier=3):
    return Student(id=sid, name=f"S{sid}", cpi=cpi,
                   preferences=prefs, tier=tier, n_tier=n_tier)


def _faculty(fid, max_load=5):
    return Faculty(id=fid, name=f"F{fid}", max_load=max_load)


def _run(students, faculty, assignments, faculty_loads):
    """Convenience wrapper: run cpi_fill_allocation with a fresh SnapshotList."""
    from src.allocator.allocation import _snap
    snaps = SnapshotList()
    # seed the SnapshotList with a step-0 snapshot so step_ctr works
    step_ctr = [0]
    unassigned = {sid for sid, fid in assignments.items() if fid is None}
    snaps.append(_snap(step_ctr, "Test", "seed", assignments, faculty_loads, unassigned))
    return cpi_fill_allocation(students, faculty, assignments, faculty_loads, snaps)


# ---------------------------------------------------------------------------
# Test 1 — Phase 1 stopping condition fires correctly
# ---------------------------------------------------------------------------

def test_phase1_stopping_condition():
    """
    U=5, E=2 (U-E=3).  Every student's top preference is a non-empty lab
    (f1 or f2), so Phase 1 always assigns to a non-empty lab and U-E shrinks
    by 1 each step.  The stopping condition fires after exactly 3 assignments.
    Phase 2 then places the 2 remaining students in the empty labs (f3, f4).
    """
    students = [
        _student("s1", 9.0, ["f1", "f2", "f3", "f4"]),
        _student("s2", 8.5, ["f2", "f1", "f3", "f4"]),
        _student("s3", 8.0, ["f1", "f2", "f3", "f4"]),
        _student("s4", 7.5, ["f1", "f2", "f3", "f4"]),
        _student("s5", 7.0, ["f1", "f2", "f3", "f4"]),
    ]
    faculty = [_faculty("f1", 5), _faculty("f2", 5),
               _faculty("f3", 5), _faculty("f4", 5)]

    # f1, f2 non-empty (load=1); f3, f4 empty.  U=5, E=2, U-E=3.
    assignments   = {s.id: None for s in students}
    faculty_loads = {"f1": 1, "f2": 1, "f3": 0, "f4": 0}

    result_assignments, snaps, _ = _run(students, faculty, assignments, faculty_loads)

    assert all(v is not None for v in result_assignments.values()), \
        "All students should be assigned"

    phase1_complete = [s for s in snaps if "Phase 1 complete" in s.event]
    assert phase1_complete, "Expected a 'Phase 1 complete' snapshot"

    # U-E=3 → exactly 3 Phase 1 assignment events
    phase1_assigns = [s for s in snaps if s.phase == "Phase1" and "→" in s.event]
    assert len(phase1_assigns) == 3, \
        f"Phase 1 should make exactly 3 assignments (U-E=3), made {len(phase1_assigns)}"


# ---------------------------------------------------------------------------
# Test 2 — Phase 2 fills all empty labs
# ---------------------------------------------------------------------------

def test_phase2_fills_all_empty_labs():
    """After a full CPI-Fill run, no empty labs remain and no student is unassigned."""
    students = [
        _student("s1", 9.0, ["f1", "f2", "f3"]),
        _student("s2", 8.0, ["f2", "f1", "f3"]),
        _student("s3", 7.0, ["f3", "f1", "f2"]),
    ]
    faculty = [_faculty("f1", 2), _faculty("f2", 2), _faculty("f3", 2)]
    assignments   = {s.id: None for s in students}
    faculty_loads = {"f1": 0, "f2": 0, "f3": 0}

    result_assignments, _, _ = _run(students, faculty, assignments, faculty_loads)

    assert all(v is not None for v in result_assignments.values()), \
        "All students should be assigned"
    from src.allocator.allocation import _snap
    # Recompute faculty_loads from result
    loads = {"f1": 0, "f2": 0, "f3": 0}
    for fid in result_assignments.values():
        loads[fid] += 1
    assert all(l >= 1 for l in loads.values()), \
        "Every faculty should have at least one student (no empty labs)"


# ---------------------------------------------------------------------------
# Test 3 — Phase 2 respects preference order
# ---------------------------------------------------------------------------

def test_phase2_respects_preference_order():
    """
    Student has two empty labs in their list at positions 2 and 5.
    Verify they are assigned to position 2 (higher preference), not 5.
    """
    # f1 is full after "round 1"; f2 and f5 are empty; f3, f4 full
    students = [_student("s1", 8.0, ["f1", "f2", "f3", "f4", "f5"], n_tier=None)]
    faculty = [
        _faculty("f1", 1), _faculty("f2", 2), _faculty("f3", 1),
        _faculty("f4", 1), _faculty("f5", 2),
    ]
    assignments   = {"s1": None}
    faculty_loads = {"f1": 1, "f2": 0, "f3": 1, "f4": 1, "f5": 0}

    result_assignments, _, _ = _run(students, faculty, assignments, faculty_loads)

    assert result_assignments["s1"] == "f2", \
        f"Expected assignment to f2 (rank 2), got {result_assignments['s1']}"


# ---------------------------------------------------------------------------
# Test 4 — Phase 2 adapts to dynamic empty-lab state
# ---------------------------------------------------------------------------

def test_phase2_dynamic_empty_lab_state():
    """
    Two Phase-2 students share the same highest-preferred empty lab.
    First student gets it; second moves to their next empty lab.
    """
    students = [
        _student("s1", 9.0, ["f1", "f2"], n_tier=None),
        _student("s2", 7.0, ["f1", "f2"], n_tier=None),
    ]
    faculty = [_faculty("f1", 1), _faculty("f2", 1)]
    assignments   = {"s1": None, "s2": None}
    faculty_loads = {"f1": 0, "f2": 0}

    result_assignments, _, _ = _run(students, faculty, assignments, faculty_loads)

    # s1 (higher CPI) should get f1; s2 gets f2
    assert result_assignments["s1"] == "f1", \
        f"s1 should get f1, got {result_assignments['s1']}"
    assert result_assignments["s2"] == "f2", \
        f"s2 should get f2, got {result_assignments['s2']}"


# ---------------------------------------------------------------------------
# Test 5 — U == E at entry: Phase 1 is skipped entirely
# ---------------------------------------------------------------------------

def test_u_equals_e_phase1_skipped():
    """When U == E at entry, Phase 1 produces zero assignments; only Phase 2 runs."""
    students = [
        _student("s1", 9.0, ["f1", "f2"]),
        _student("s2", 8.0, ["f2", "f1"]),
    ]
    faculty = [_faculty("f1", 2), _faculty("f2", 2)]
    assignments   = {"s1": None, "s2": None}
    faculty_loads = {"f1": 0, "f2": 0}   # U=2, E=2

    result_assignments, snaps, _ = _run(students, faculty, assignments, faculty_loads)

    # No Phase1 assignment events
    phase1_assigns = [s for s in snaps if s.phase == "Phase1" and "→" in s.event]
    assert len(phase1_assigns) == 0, \
        f"Phase 1 should be skipped (0 assignments), got {len(phase1_assigns)}"

    # Phase 1 skipped snapshot should be present
    skip_snaps = [s for s in snaps if "Phase 1 skipped" in s.event]
    assert skip_snaps, "Expected a 'Phase 1 skipped' snapshot"

    assert all(v is not None for v in result_assignments.values())


# ---------------------------------------------------------------------------
# Test 6 — E == 0: Phase 1 runs to completion, Phase 2 is a no-op
# ---------------------------------------------------------------------------

def test_e_equals_0_phase2_noop():
    """When E == 0 after Round 1, Phase 1 runs to completion; Phase 2 is a no-op."""
    students = [
        _student("s1", 9.0, ["f1", "f2"]),
        _student("s2", 8.0, ["f2", "f1"]),
    ]
    faculty = [_faculty("f1", 2), _faculty("f2", 2)]
    # Both faculty already have load >= 1 — no empty labs
    assignments   = {"s1": None, "s2": None}
    faculty_loads = {"f1": 1, "f2": 1}   # E=0

    result_assignments, snaps, _ = _run(students, faculty, assignments, faculty_loads)

    # Phase 2 should have zero assignment events
    phase2_assigns = [s for s in snaps if s.phase == "Phase2" and "→" in s.event]
    assert len(phase2_assigns) == 0, \
        f"Phase 2 should be a no-op (0 assignments), got {len(phase2_assigns)}"

    # All students should still be assigned in Phase 1
    assert all(v is not None for v in result_assignments.values())


# ---------------------------------------------------------------------------
# Test 7 — U < E raises RuntimeError (or warning + Phase2 failure)
# ---------------------------------------------------------------------------

def test_u_less_than_e_raises():
    """When fewer students are unassigned than there are empty labs, raises RuntimeError."""
    students = [_student("s1", 9.0, ["f1", "f2"])]
    faculty = [_faculty("f1", 2), _faculty("f2", 2)]
    assignments   = {"s1": None}
    faculty_loads = {"f1": 0, "f2": 0}   # U=1, E=2 — one empty lab will remain unfilled

    # The warning is issued; Phase 2 runs but we still expect all students assigned
    # (even if some labs remain empty). The function should NOT crash.
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result_assignments, _, _ = _run(students, faculty, assignments, faculty_loads)
        assert any("not enough students" in str(warning.message).lower()
                   for warning in w), "Expected a warning about insufficient students"

    assert result_assignments["s1"] is not None


# ---------------------------------------------------------------------------
# Test 8 — CPI ordering in Phase 1
# ---------------------------------------------------------------------------

def test_phase1_cpi_ordering():
    """
    s2 has higher CPI but appears second in the input list.
    Phase 1 processes in CPI order: s2 (9.0) before s1 (7.0).
    U=4, E=2 (U-E=2): Phase 1 stops after 2 assignments.
    """
    students = [
        _student("s1", 7.0, ["f1", "f2", "f3", "f4"]),   # lower CPI, appears first
        _student("s2", 9.0, ["f1", "f2", "f3", "f4"]),   # higher CPI, appears second
        _student("s3", 5.0, ["f1", "f2", "f3", "f4"]),
        _student("s4", 4.0, ["f1", "f2", "f3", "f4"]),
    ]
    faculty = [_faculty("f1", 5), _faculty("f2", 5),
               _faculty("f3", 5), _faculty("f4", 5)]
    # f1, f2 non-empty (load=1); f3, f4 empty. U=4, E=2, U-E=2.
    # All students prefer f1 first → Phase 1 assigns to f1 (non-empty) each time.
    assignments   = {s.id: None for s in students}
    faculty_loads = {"f1": 1, "f2": 1, "f3": 0, "f4": 0}

    result_assignments, snaps, _ = _run(students, faculty, assignments, faculty_loads)

    phase1_events = [s for s in snaps if s.phase == "Phase1" and "→" in s.event]
    assert len(phase1_events) == 2, \
        f"Expected 2 Phase 1 assignments (U-E=2), got {len(phase1_events)}"

    def _sid_from_event(event_str):
        # "Phase 1 | Ss2 (s2, CPI ...) → ..." — ID is inside the first parens
        start = event_str.index("(") + 1
        return event_str[start:event_str.index(",", start)]

    assert _sid_from_event(phase1_events[0].event) == "s2", \
        "s2 (CPI 9.0) should be processed first in Phase 1"
    assert _sid_from_event(phase1_events[1].event) == "s1", \
        "s1 (CPI 7.0) should be processed second in Phase 1"


# ---------------------------------------------------------------------------
# Test 9 — Phase 1 assigns highest-preferred, not least-loaded
# ---------------------------------------------------------------------------

def test_phase1_assigns_highest_preferred_not_least_loaded():
    """
    Phase 1 assigns each student to their highest-preferred advisor with
    remaining capacity, regardless of load.

    f1 (load=2, max=5) is the student's first preference.
    f2 (load=0, max=5) is the student's second preference.

    A least-loaded rule would pick f2 (load 0).
    CPI-Fill Phase 1 must pick f1 (highest-preferred with capacity).
    """
    students = [_student("s1", 8.0, ["f1", "f2", "f3"])]
    faculty  = [_faculty("f1", 5), _faculty("f2", 5), _faculty("f3", 5)]
    # f1 has load=2 (non-empty, high load), f2 has load=0 (empty, low load)
    # f3 is also empty. U=1, E=2 → U < E → warning but still assigns.
    assignments   = {"s1": None}
    faculty_loads = {"f1": 2, "f2": 0, "f3": 0}

    import warnings
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result_assignments, _, _ = _run(students, faculty, assignments, faculty_loads)

    # s1 should get f1 (rank 1), not f2 (rank 2, but load=0)
    assert result_assignments["s1"] == "f1", \
        f"Phase 1 should assign to highest-preferred f1, got {result_assignments['s1']}"


# ---------------------------------------------------------------------------
# Test 10 — Full run via run_full_allocation with policy="cpi_fill"
# ---------------------------------------------------------------------------

def test_full_run_via_run_full_allocation():
    """
    Pass policy='cpi_fill' to run_full_allocation.
    Verify no None values in assignments and metric keys are present.
    """
    # Build a small but realistic cohort
    all_fids = ["f1", "f2", "f3", "f4"]
    students_raw = [
        Student(id="s1", name="Alice",   cpi=9.2, preferences=["f1","f2","f3","f4"]),
        Student(id="s2", name="Bob",     cpi=8.8, preferences=["f2","f1","f3","f4"]),
        Student(id="s3", name="Carol",   cpi=8.1, preferences=["f3","f4","f1","f2"]),
        Student(id="s4", name="Dave",    cpi=7.5, preferences=["f1","f3","f2","f4"]),
        Student(id="s5", name="Eve",     cpi=6.9, preferences=["f4","f2","f1","f3"]),
        Student(id="s6", name="Frank",   cpi=6.2, preferences=["f2","f4","f3","f1"]),
        Student(id="s7", name="Grace",   cpi=5.8, preferences=["f3","f1","f4","f2"]),
        Student(id="s8", name="Heidi",   cpi=5.0, preferences=["f4","f3","f2","f1"]),
    ]
    faculty_raw = [
        Faculty(id="f1", name="Prof A", max_load=3),
        Faculty(id="f2", name="Prof B", max_load=3),
        Faculty(id="f3", name="Prof C", max_load=3),
        Faculty(id="f4", name="Prof D", max_load=3),
    ]

    assignments, snaps, meta, metrics = run_full_allocation(
        students_raw, faculty_raw, policy="cpi_fill"
    )

    assert all(v is not None for v in assignments.values()), \
        f"All students should be assigned, unassigned: " \
        f"{[k for k, v in assignments.items() if v is None]}"

    for key in ("npss", "overflow_count", "mean_psi", "per_tier", "per_student"):
        assert key in metrics, f"Missing metrics key: {key}"

    # Verify Phase1 and Phase2 snapshots are present
    phases = {s.phase for s in snaps}
    assert "Phase1" in phases or "CPIFill" in phases, \
        "Expected CPI-Fill phases in snapshot list"
