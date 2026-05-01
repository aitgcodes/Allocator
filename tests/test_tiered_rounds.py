"""
tests/test_tiered_rounds.py — Unit tests for the CPI-tiered preference rounds engine.

Tests:
1. Unique CPI happy path across multiple rounds.
2. Advisor reaches capacity and is skipped in later rounds.
3. Same-round competition with a unique highest-CPI student.
4. Top-CPI tie creates a correct pending tie (right fields).
5. Resume after manual tie decision and allocation continues correctly.
6. Multi-round forwarding of non-selected students.
7. Defensive handling for malformed/incomplete preferences.
8. Regression: existing least_loaded, nonempty, cpi_fill outputs unchanged.
"""
from __future__ import annotations

import pytest

from src.allocator.allocation import (
    cpi_fill_allocation,
    main_allocation,
    phase0,
    round1,
    tiered_rounds_apply_picks,
    tiered_rounds_continue_unconstrained,
    tiered_rounds_resume,
    tiered_rounds_start,
    tiered_rounds_start_interactive,
)
from src.allocator.state import Faculty, SnapshotList, Student


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _student(sid: str, name: str, cpi: float, prefs: list) -> Student:
    return Student(id=sid, name=name, cpi=cpi, preferences=prefs)


def _faculty(fid: str, name: str, max_load: int) -> Faculty:
    return Faculty(id=fid, name=name, max_load=max_load)


def _phase0_snaps(students, faculty) -> SnapshotList:
    """Run phase0 and return the snapshot list for use in tiered_rounds_start."""
    updated_s, updated_f, meta, snaps = phase0(students, faculty)
    return updated_s, updated_f, snaps


# ---------------------------------------------------------------------------
# Test 1 — Unique CPI happy path across multiple rounds
# ---------------------------------------------------------------------------

def test_unique_cpi_happy_path():
    """
    3 students, 3 advisors.  Each student lists all advisors in the same order.
    S1 (CPI 9) → F1 in round 1; S2 (CPI 8) → F1 in round 2… wait, F1 is
    saturated after round 1.  Actually S2's 1st pref is also F1 (saturated),
    so in round 2 S2 offers F2 (2nd pref) → assigned.  S3 similarly.
    """
    students = [
        _student("S1", "Alice",   9.0, ["F1", "F2", "F3"]),
        _student("S2", "Bob",     8.0, ["F1", "F2", "F3"]),
        _student("S3", "Charlie", 7.0, ["F1", "F2", "F3"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
        _faculty("F3", "Prof C", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start(s_up, f_up, snaps)

    assert tr.status == "complete", f"Expected complete, got {tr.status}"
    assert tr.assignments["S1"] == "F1"
    assert tr.assignments["S2"] == "F2"
    assert tr.assignments["S3"] == "F3"
    assert all(v is not None for v in tr.assignments.values())


# ---------------------------------------------------------------------------
# Test 2 — Advisor reaches capacity and is skipped in later rounds
# ---------------------------------------------------------------------------

def test_advisor_skipped_after_full():
    """
    F1 has max_load=1.  S1 and S2 both prefer F1 first (S1 wins — higher CPI).
    In round 2, F1 is saturated → S2 skips to F2.
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   8.0, ["F1", "F2"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start(s_up, f_up, snaps)

    assert tr.status == "complete"
    assert tr.assignments["S1"] == "F1"
    assert tr.assignments["S2"] == "F2"

    # F1 should appear in saturated_advisors after round 1
    assert "F1" in tr.saturated_advisors


# ---------------------------------------------------------------------------
# Test 3 — Same-round competition with a unique highest-CPI student
# ---------------------------------------------------------------------------

def test_unique_winner_in_competitive_round():
    """
    F1 has capacity 2.  S1 (9.0) and S2 (8.0) both list F1 as first preference.
    Round 1: S1 wins F1 (unique highest CPI).
    Round 2: S2 offers their 2nd preference F2 (protocol uses round index into
    preference list, not the same preference again).  S2 is the only candidate
    for F2 → assigned.
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   8.0, ["F1", "F2"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 2),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start(s_up, f_up, snaps)

    assert tr.status == "complete"
    assert tr.assignments["S1"] == "F1"
    # S2 moves to their 2nd preference (F2) in round 2
    assert tr.assignments["S2"] == "F2"


# ---------------------------------------------------------------------------
# Test 4 — Top-CPI tie creates a correct pending PendingTie
# ---------------------------------------------------------------------------

def test_tie_creates_pending_decision():
    """
    S1 and S2 share CPI 9.0 and both prefer F1 first.
    Engine should pause with status="awaiting_tie".
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   9.0, ["F1", "F2"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start(s_up, f_up, snaps)

    assert tr.status == "awaiting_tie", f"Expected awaiting_tie, got {tr.status}"
    tie = tr.pending_tie
    assert tie is not None
    assert tie.advisor_id == "F1"
    assert tie.round_no == 1
    assert tie.tied_cpi == 9.0
    assert set(tie.tied_ids) == {"S1", "S2"}
    assert set(tie.candidate_ids) == {"S1", "S2"}
    assert "S1" in tie.candidate_names
    assert tie.candidate_cpis["S1"] == 9.0
    assert "CPI tie" in tie.reason


# ---------------------------------------------------------------------------
# Test 5 — Resume after manual tie decision, allocation continues correctly
# ---------------------------------------------------------------------------

def test_resume_after_tie():
    """
    Same setup as test 4.  After choosing S1 to break the tie,
    S2 should be assigned in round 2 (only candidate for F2).
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   9.0, ["F1", "F2"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start(s_up, f_up, snaps)

    assert tr.status == "awaiting_tie"

    tr2 = tiered_rounds_resume(tr, "S1")

    assert tr2.status == "complete"
    assert tr2.assignments["S1"] == "F1"
    assert tr2.assignments["S2"] == "F2"

    # Trace should record the manual decision
    round1_trace = next(e for e in tr2.trace_log if e["round_no"] == 1)
    assert len(round1_trace["manual_decisions"]) == 1
    assert round1_trace["manual_decisions"][0]["chosen_student_id"] == "S1"


# ---------------------------------------------------------------------------
# Test 6 — Multi-round forwarding of non-selected students
# ---------------------------------------------------------------------------

def test_multi_round_forwarding():
    """
    F1 capacity=1.  S1(9), S2(8), S3(7) all prefer F1 → F2 → F3.
    Round 1: F1 picks S1.  Round 2: F2 picks S2 (sole candidate).
    Round 3: F3 picks S3.  All assigned.
    """
    students = [
        _student("S1", "Alice",   9.0, ["F1", "F2", "F3"]),
        _student("S2", "Bob",     8.0, ["F1", "F2", "F3"]),
        _student("S3", "Charlie", 7.0, ["F1", "F2", "F3"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
        _faculty("F3", "Prof C", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start(s_up, f_up, snaps)

    assert tr.status == "complete"
    assert tr.assignments["S1"] == "F1"
    assert tr.assignments["S2"] == "F2"
    assert tr.assignments["S3"] == "F3"

    # Three rounds should have been executed
    assert len(tr.trace_log) == 3

    # Round 1: only S1 assigned (to F1)
    r1 = tr.trace_log[0]
    assert r1["round_no"] == 1
    assert len(r1["assigned_this_round"]) == 1
    assert "S1" in r1["assigned_this_round"]

    # F1 is saturated in the global state after round 1
    assert "F1" in tr.saturated_advisors

    # Round 2: S2 and S3 both target F2 (their 2nd preference) — F1 is saturated
    # but not targeted in round 2, so it does not appear in skipped_advisor_ids.
    r2 = tr.trace_log[1]
    assert r2["round_no"] == 2
    assert "F2" in r2["candidate_pools"]


# ---------------------------------------------------------------------------
# Test 7 — Defensive handling for malformed/incomplete preferences
# ---------------------------------------------------------------------------

def test_malformed_empty_preference_list():
    """A student with an empty preference list should raise ValueError."""
    students = [
        _student("S1", "Alice", 9.0, []),      # malformed
        _student("S2", "Bob",   8.0, ["F1"]),
    ]
    faculty = [_faculty("F1", "Prof A", 2)]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    with pytest.raises(ValueError, match="empty preference list"):
        tiered_rounds_start(s_up, f_up, snaps)


def test_malformed_unknown_faculty_in_prefs():
    """A student referencing an unknown faculty ID should raise ValueError."""
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F_UNKNOWN"]),
    ]
    faculty = [_faculty("F1", "Prof A", 1)]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    with pytest.raises(ValueError, match="unknown faculty IDs"):
        tiered_rounds_start(s_up, f_up, snaps)


def test_malformed_insufficient_capacity():
    """Total faculty capacity < students should raise ValueError."""
    students = [
        _student("S1", "Alice", 9.0, ["F1"]),
        _student("S2", "Bob",   8.0, ["F1"]),
    ]
    faculty = [_faculty("F1", "Prof A", 1)]   # capacity=1 < 2 students
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    with pytest.raises(ValueError, match="Total faculty capacity"):
        tiered_rounds_start(s_up, f_up, snaps)


def test_invalid_resume_chosen_not_in_tied():
    """Choosing a student not in the tied set should raise ValueError."""
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   9.0, ["F1", "F2"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start(s_up, f_up, snaps)
    assert tr.status == "awaiting_tie"

    with pytest.raises(ValueError, match="not in the tied set"):
        tiered_rounds_resume(tr, "S_DOES_NOT_EXIST")


# ---------------------------------------------------------------------------
# Test 8 — Regression: existing protocols unchanged
# ---------------------------------------------------------------------------

def test_regression_least_loaded():
    """least_loaded policy still produces the same output after the new code."""
    students = [
        _student("S1", "Alice",   9.0, ["F1", "F2"]),
        _student("S2", "Bob",     8.0, ["F1", "F2"]),
        _student("S3", "Charlie", 7.0, ["F2", "F1"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 2),
        _faculty("F2", "Prof B", 2),
    ]
    s_up, f_up, meta, snaps = phase0(students, faculty)
    N_A, N_B = meta["N_A"], meta["N_B"]
    assignments, fl, snaps = round1(s_up, f_up, snaps)
    assignments, snaps = main_allocation(
        s_up, f_up, assignments, fl, snaps, N_A, N_B, policy="least_loaded"
    )
    assert all(v is not None for v in assignments.values())


def test_regression_nonempty():
    """nonempty policy still produces a full allocation."""
    students = [
        _student("S1", "Alice",   9.0, ["F1", "F2"]),
        _student("S2", "Bob",     8.0, ["F2", "F1"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, meta, snaps = phase0(students, faculty)
    N_A, N_B = meta["N_A"], meta["N_B"]
    assignments, fl, snaps = round1(s_up, f_up, snaps)
    assignments, snaps = main_allocation(
        s_up, f_up, assignments, fl, snaps, N_A, N_B, policy="nonempty"
    )
    assert all(v is not None for v in assignments.values())


def test_regression_cpi_fill():
    """cpi_fill policy still completes without errors."""
    students = [
        _student("S1", "Alice",   9.0, ["F1", "F2"]),
        _student("S2", "Bob",     8.0, ["F1", "F2"]),
        _student("S3", "Charlie", 7.0, ["F2", "F1"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 2),
        _faculty("F2", "Prof B", 2),
    ]
    s_up, f_up, meta, snaps = phase0(students, faculty)
    assignments = {s.id: None for s in s_up}
    fl = {f.id: 0 for f in f_up}
    assignments, snaps, _ = cpi_fill_allocation(s_up, f_up, assignments, fl, snaps)
    assert all(v is not None for v in assignments.values())


# ---------------------------------------------------------------------------
# Tests for interactive (manual) engine path
# ---------------------------------------------------------------------------

def test_interactive_basic_manual_progression():
    """
    3 students, 3 advisors, all distinct first preferences.
    Round 1 should have 3 advisor groups each with 1 candidate.
    Confirming the default picks (highest CPI = only candidate) completes allocation.
    """
    students = [
        _student("S1", "Alice",   9.0, ["F1", "F2", "F3"]),
        _student("S2", "Bob",     8.0, ["F2", "F1", "F3"]),
        _student("S3", "Charlie", 7.0, ["F3", "F1", "F2"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
        _faculty("F3", "Prof C", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start_interactive(s_up, f_up, snaps)

    assert tr.status == "awaiting_round_picks"
    assert tr.round_no == 1
    assert set(tr.pending_round_groups.keys()) == {"F1", "F2", "F3"}
    # Each advisor has exactly one candidate
    assert all(len(v) == 1 for v in tr.pending_round_groups.values())

    # Confirm picks: take the only candidate for each advisor
    picks = {fid: sids[0] for fid, sids in tr.pending_round_groups.items()}
    tr = tiered_rounds_apply_picks(tr, picks)

    assert tr.status == "complete"
    assert all(v is not None for v in tr.assignments.values())
    assert len(tr.trace_log) == 1
    assert len(tr.trace_log[0]["manual_decisions"]) == 3


def test_interactive_multi_round_progression():
    """
    S1 and S2 both prefer F1 first; S1 wins (higher CPI).
    Round 2 S2 moves to F2.  Two manual rounds to complete.
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   8.0, ["F1", "F2"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start_interactive(s_up, f_up, snaps)

    assert tr.status == "awaiting_round_picks"
    assert tr.round_no == 1
    # Both target F1; S1 is top candidate
    assert "F1" in tr.pending_round_groups
    assert tr.pending_round_groups["F1"][0] == "S1"

    picks = {fid: sids[0] for fid, sids in tr.pending_round_groups.items()}
    tr = tiered_rounds_apply_picks(tr, picks)

    # S2 still unassigned → round 2
    assert tr.status == "awaiting_round_picks"
    assert tr.round_no == 2
    assert "F2" in tr.pending_round_groups

    picks2 = {fid: sids[0] for fid, sids in tr.pending_round_groups.items()}
    tr = tiered_rounds_apply_picks(tr, picks2)

    assert tr.status == "complete"
    assert tr.assignments["S1"] == "F1"
    assert tr.assignments["S2"] == "F2"


def test_interactive_missing_pick_raises():
    """
    Omitting a required advisor from picks raises a clear ValueError.
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   8.0, ["F2", "F1"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start_interactive(s_up, f_up, snaps)

    assert tr.status == "awaiting_round_picks"
    # Provide only one of the two required picks
    partial_picks = {"F1": tr.pending_round_groups["F1"][0]}
    with pytest.raises(ValueError, match="missing"):
        tiered_rounds_apply_picks(tr, partial_picks)


def test_interactive_null_round_auto_advance():
    """
    Round 1: S1 → F1, F1 becomes saturated.
    Round 2: S2's only preference is F1 (saturated) → null round auto-advances.
    Round 3: S2's next preference is F2 → assigned.
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   8.0, ["F1", "F2"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    # Use stop_at_round=None; S2 preference list length forces round 2 to be null
    tr = tiered_rounds_start_interactive(s_up, f_up, snaps)

    assert tr.status == "awaiting_round_picks"
    assert tr.round_no == 1
    # Assign S1 to F1 (saturates it)
    picks = {"F1": "S1"}
    tr = tiered_rounds_apply_picks(tr, picks)

    # Round 2 would be null (S2 targets saturated F1); should auto-advance to round 2→F2
    # The engine skips the null round internally and returns awaiting_round_picks for F2
    assert tr.status == "awaiting_round_picks"
    assert "F1" not in tr.pending_round_groups  # saturated, skipped
    assert "F2" in tr.pending_round_groups

    picks2 = {"F2": "S2"}
    tr = tiered_rounds_apply_picks(tr, picks2)
    assert tr.status == "complete"
    assert tr.assignments["S2"] == "F2"


def test_interactive_stop_at_round_switch_to_backfill():
    """
    stop_at_round=2: after round 1 the engine should return switch_to_backfill
    without proceeding to round 2.
    tiered_rounds_continue_unconstrained then resumes without a cap.
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   8.0, ["F2", "F1"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start_interactive(s_up, f_up, snaps, stop_at_round=2)

    assert tr.status == "awaiting_round_picks"
    assert tr.round_no == 1

    picks = {fid: sids[0] for fid, sids in tr.pending_round_groups.items()}
    tr = tiered_rounds_apply_picks(tr, picks, stop_at_round=2)

    # Both students assigned in round 1 (distinct first prefs) → complete, not switch
    # Adjust: make only one assigned so round 2 would be needed
    # Re-run with a scenario where one student is unassigned after round 1
    students2 = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   8.0, ["F1", "F2"]),
    ]
    s_up2, f_up2, snaps2 = _phase0_snaps(students2, faculty)
    tr2 = tiered_rounds_start_interactive(s_up2, f_up2, snaps2, stop_at_round=2)

    assert tr2.status == "awaiting_round_picks"
    picks2 = {"F1": "S1"}  # only F1 has candidates; S2 will be unassigned
    tr2 = tiered_rounds_apply_picks(tr2, picks2, stop_at_round=2)

    assert tr2.status == "switch_to_backfill"

    # Continuing unconstrained should present round 2 for S2
    tr2 = tiered_rounds_continue_unconstrained(tr2)
    assert tr2.status == "awaiting_round_picks"
    assert tr2.round_no == 2


def test_interactive_rank_uses_round_number():
    """
    Preference rank stored in snapshots equals round_no, not list.index().
    """
    students = [
        _student("S1", "Alice", 9.0, ["F1", "F2"]),
        _student("S2", "Bob",   8.0, ["F2", "F1"]),
    ]
    faculty = [
        _faculty("F1", "Prof A", 1),
        _faculty("F2", "Prof B", 1),
    ]
    s_up, f_up, snaps = _phase0_snaps(students, faculty)
    tr = tiered_rounds_start_interactive(s_up, f_up, snaps)

    picks = {fid: sids[0] for fid, sids in tr.pending_round_groups.items()}
    tr = tiered_rounds_apply_picks(tr, picks)

    assert tr.status == "complete"
    # Both students assigned at round 1; each snapshot for a pick should record rank=1
    pick_snaps = [s for s in tr.snapshots if s.preference_rank]
    assert all(rank == 1 for s in pick_snaps for rank in s.preference_rank.values())
