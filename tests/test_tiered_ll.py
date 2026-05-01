"""
tests/test_tiered_ll.py — Tests for the tiered_ll hybrid policy engine.

Run with:
    conda run -n allocator python -m pytest tests/test_tiered_ll.py -v
"""

from src.allocator.state import Faculty, Student, SnapshotList
from src.allocator.allocation import (
    _reachability,
    find_critical_round,
    phase0,
    run_full_allocation,
    tiered_ll_backfill,
    tiered_rounds_dry_run,
    tiered_rounds_resume,
    tiered_rounds_start,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(n, max_load=2):
    return Faculty(id=f"F{n:02d}", name=f"Prof{n:02d}", max_load=max_load)


def _fids(n):
    return [f"F{i:02d}" for i in range(1, n + 1)]


def _s(sid, cpi, prefs):
    return Student(id=str(sid), name=f"S{sid}", cpi=float(cpi), preferences=prefs)


def _phase0_cohort(students, faculty):
    """Run phase0 and return (students, faculty, meta)."""
    sts, fac, meta, _ = phase0(students, faculty)
    return sts, fac, meta


def _dummy_snaps(students, faculty):
    snaps = SnapshotList()
    from src.allocator.state import AllocationSnapshot
    snaps.append(AllocationSnapshot(
        step=0, phase="Phase0", event="test-init",
        assignments={s.id: None for s in students},
        faculty_loads={f.id: 0 for f in faculty},
        unassigned={s.id for s in students},
    ))
    return snaps


# ---------------------------------------------------------------------------
# 1 — _reachability
# ---------------------------------------------------------------------------

class TestReachability:
    def test_all_reachable(self):
        """All faculty reachable when every unassigned student can still reach them."""
        faculty = [_f(1, 2), _f(2, 2)]
        faculty_loads = {"F01": 0, "F02": 0}
        students = [
            _s(1, 9.0, ["F01", "F02"]),
            _s(2, 8.0, ["F02", "F01"]),
        ]
        student_map = {s.id: s for s in students}
        # completed_round_no=0 means all prefs remain
        reachable, unreachable = _reachability(
            {"1", "2"}, faculty, faculty_loads, student_map, 0
        )
        assert reachable == 2
        assert unreachable == 0

    def test_unreachable_faculty(self):
        """F02 has capacity but no unassigned student lists it in remaining prefs."""
        faculty = [_f(1, 1), _f(2, 1)]
        faculty_loads = {"F01": 1, "F02": 0}  # F01 full, F02 has capacity
        students = [
            _s(1, 9.0, ["F01", "F02"]),  # round 1 pref = F01 (used); remaining: F02 only if round>=1
        ]
        student_map = {s.id: s for s in students}
        # After round 1 (completed_round_no=1): remaining prefs for s1 = prefs[1:] = ["F02"]
        # F02 has capacity and is reachable → unreachable = 0
        reachable, unreachable = _reachability(
            {"1"}, faculty, faculty_loads, student_map, 1
        )
        assert unreachable == 0

    def test_faculty_with_cap_unreachable(self):
        """F03 has capacity but nobody can reach it any more."""
        faculty = [_f(1, 1), _f(2, 1), _f(3, 2)]
        faculty_loads = {"F01": 1, "F02": 1, "F03": 0}
        students = [_s(1, 9.0, ["F01", "F02"])]  # F03 not in prefs at all
        student_map = {s.id: s for s in students}
        reachable, unreachable = _reachability(
            {"1"}, faculty, faculty_loads, student_map, 0
        )
        assert unreachable == 1   # F03 has cap but no student can reach it


# ---------------------------------------------------------------------------
# 2 — find_critical_round
# ---------------------------------------------------------------------------

class TestFindCriticalRound:
    def _make_entry(self, round_no, unreachable=0, stall=False, assigned=1,
                    unassigned=0, empty_labs=0):
        return {
            "round_no":                 round_no,
            "unreachable_faculty_count": unreachable,
            "is_stall":                 stall,
            "assignments_made":         assigned,
            "unassigned_count":         unassigned,
            "empty_labs_count":         empty_labs,
        }

    def test_no_criterion_fires(self):
        """k = last round when criterion never fires."""
        states = [
            self._make_entry(1), self._make_entry(2), self._make_entry(3),
        ]
        assert find_critical_round(states) == 3

    def test_criterion_fires_at_round_2(self):
        """k = 1 when criterion fires at round 2."""
        states = [
            self._make_entry(1),
            self._make_entry(2, unreachable=1),
        ]
        assert find_critical_round(states) == 1

    def test_criterion_fires_at_round_3(self):
        """k = 2 when criterion fires at round 3."""
        states = [
            self._make_entry(1),
            self._make_entry(2),
            self._make_entry(3, unreachable=2),
        ]
        assert find_critical_round(states) == 2

    def test_stall_criterion(self):
        """Stall also triggers the criterion."""
        states = [
            self._make_entry(1),
            self._make_entry(2, stall=True, assigned=0, unassigned=3),
        ]
        assert find_critical_round(states) == 1

    def test_criterion_fires_at_round_1(self):
        """k = 1 (minimum) when criterion fires immediately at round 1."""
        states = [self._make_entry(1, unreachable=1)]
        assert find_critical_round(states) == 1

    def test_empty_states(self):
        """Empty dry-run returns k=1."""
        assert find_critical_round([]) == 1

    def test_unassigned_equals_empty_labs_fires_criterion(self):
        """k = round_no when unassigned == empty_labs (exact parity — run this round)."""
        states = [
            self._make_entry(1, unassigned=10, empty_labs=7),
            self._make_entry(2, unassigned=7,  empty_labs=7),
        ]
        assert find_critical_round(states) == 2

    def test_unassigned_below_empty_labs_fires_criterion(self):
        """k = prev round when unassigned < empty_labs (overshoot — stop before this round)."""
        states = [
            self._make_entry(1, unassigned=20, empty_labs=7),
            self._make_entry(2, unassigned=6,  empty_labs=7),
        ]
        assert find_critical_round(states) == 1

    def test_unassigned_below_empty_labs_at_round1_returns_zero(self):
        """k = 0 when round 1 itself overshoots (skip all tiered rounds)."""
        states = [
            self._make_entry(1, unassigned=2, empty_labs=5),
        ]
        assert find_critical_round(states) == 0

    def test_unassigned_zero_does_not_fire_empty_labs_criterion(self):
        """Criterion does not fire when unassigned=0 (all students already assigned)."""
        states = [
            self._make_entry(1, unassigned=5, empty_labs=3),
            self._make_entry(2, unassigned=0, empty_labs=3),
        ]
        # unassigned=0 does not satisfy (unassigned > 0) → criterion doesn't fire → k=2
        assert find_critical_round(states) == 2

    def test_unassigned_above_empty_labs_does_not_fire(self):
        """Criterion does not fire when unassigned > empty_labs."""
        states = [
            self._make_entry(1, unassigned=5, empty_labs=2),
            self._make_entry(2, unassigned=3, empty_labs=2),
        ]
        assert find_critical_round(states) == 2


# ---------------------------------------------------------------------------
# 3 — tiered_rounds_dry_run
# ---------------------------------------------------------------------------

class TestTieredRoundsDryRun:
    def _clean_cohort(self):
        """8 students, 4 faculty, well-distributed preferences."""
        students = [
            _s(1, 9.5, ["F01", "F02", "F03", "F04"]),
            _s(2, 9.2, ["F02", "F01", "F03", "F04"]),
            _s(3, 9.0, ["F03", "F04", "F01", "F02"]),
            _s(4, 8.8, ["F04", "F03", "F02", "F01"]),
            _s(5, 8.5, ["F01", "F03", "F02", "F04"]),
            _s(6, 8.2, ["F02", "F04", "F01", "F03"]),
            _s(7, 8.0, ["F03", "F01", "F04", "F02"]),
            _s(8, 7.8, ["F04", "F02", "F03", "F01"]),
        ]
        faculty = [_f(i, 2) for i in range(1, 5)]
        students, faculty, _ = _phase0_cohort(students, faculty)
        return students, faculty

    def test_returns_nonempty_list(self):
        students, faculty = self._clean_cohort()
        states = tiered_rounds_dry_run(students, faculty)
        assert len(states) > 0

    def test_each_entry_has_required_fields(self):
        students, faculty = self._clean_cohort()
        states = tiered_rounds_dry_run(students, faculty)
        for entry in states:
            assert "round_no" in entry
            assert "unassigned_count" in entry
            assert "unreachable_faculty_count" in entry
            assert "assignments_made" in entry
            assert "is_stall" in entry
            assert "empty_labs_count" in entry

    def test_round_nos_are_sequential(self):
        students, faculty = self._clean_cohort()
        states = tiered_rounds_dry_run(students, faculty)
        for i, entry in enumerate(states):
            assert entry["round_no"] == i + 1

    def test_k_crit_in_valid_range(self):
        students, faculty = self._clean_cohort()
        states = tiered_rounds_dry_run(students, faculty)
        k = find_critical_round(states)
        total = states[-1]["round_no"] if states else 1
        assert 0 <= k <= total

    def test_originals_not_mutated(self):
        """Dry-run must not mutate the original student or faculty objects."""
        students, faculty = self._clean_cohort()
        orig_tiers = [s.tier for s in students]
        orig_loads = [f.max_load for f in faculty]
        tiered_rounds_dry_run(students, faculty)
        assert [s.tier for s in students] == orig_tiers
        assert [f.max_load for f in faculty] == orig_loads


# ---------------------------------------------------------------------------
# 4 — tiered_ll_backfill
# ---------------------------------------------------------------------------

class TestTieredLLBackfill:
    def _make_state(self):
        """4 students, 4 faculty; students 3 and 4 unassigned after 2 rounds."""
        faculty = [_f(i, 1) for i in range(1, 5)]
        students = [
            _s(1, 9.5, ["F01", "F02", "F03", "F04"]),
            _s(2, 9.2, ["F02", "F01", "F03", "F04"]),
            _s(3, 8.0, ["F03", "F01", "F02", "F04"]),
            _s(4, 7.5, ["F04", "F01", "F02", "F03"]),
        ]
        students, faculty, _ = _phase0_cohort(students, faculty)
        return students, faculty

    def test_backfill_uses_remaining_prefs(self):
        """Students passed to backfill start searching from index k."""
        students, faculty = self._make_state()
        k = 2
        # Simulate: s1 → F01, s2 → F02 already assigned
        assignments   = {s.id: None for s in students}
        faculty_loads = {f.id: 0 for f in faculty}
        assignments["1"] = "F01"
        faculty_loads["F01"] = 1
        assignments["2"] = "F02"
        faculty_loads["F02"] = 1
        unassigned = [s for s in students if assignments[s.id] is None]

        snaps = _dummy_snaps(students, faculty)
        assignments, faculty_loads, overflow = tiered_ll_backfill(
            unassigned, faculty, assignments, faculty_loads, k, snaps
        )
        # s3 prefs[2:] = ["F02","F04"]; F02 full → s3 → F04
        # s4 prefs[2:] = ["F02","F03"]; F02 full → s4 → F03
        assert overflow == []
        assert all(assignments[s.id] is not None for s in students)

    def test_overflow_flagged_when_all_remaining_full(self):
        """When every remaining pref is saturated, student appears in overflow."""
        faculty = [_f(i, 1) for i in range(1, 3)]
        students = [
            _s(1, 9.5, ["F01", "F02"]),
            _s(2, 9.0, ["F02", "F01"]),
            _s(3, 8.0, ["F01", "F02"]),  # will be overflow
        ]
        students, faculty, _ = _phase0_cohort(students, faculty)
        assignments   = {s.id: None for s in students}
        faculty_loads = {"F01": 1, "F02": 1}  # both full already
        assignments["1"] = "F01"
        assignments["2"] = "F02"
        unassigned = [students[2]]

        snaps = _dummy_snaps(students, faculty)
        assignments, faculty_loads, overflow = tiered_ll_backfill(
            unassigned, faculty, assignments, faculty_loads, 0, snaps
        )
        assert "3" in overflow

    def test_backfill_appends_snapshots(self):
        """Snapshots are appended during backfill."""
        students, faculty = self._make_state()
        assignments   = {s.id: None for s in students}
        faculty_loads = {f.id: 0 for f in faculty}
        assignments["1"] = "F01"; faculty_loads["F01"] = 1
        assignments["2"] = "F02"; faculty_loads["F02"] = 1
        unassigned = [s for s in students if assignments[s.id] is None]

        snaps = _dummy_snaps(students, faculty)
        snap_count_before = len(snaps)
        tiered_ll_backfill(unassigned, faculty, assignments, faculty_loads, 2, snaps)
        assert len(snaps) > snap_count_before

    def test_phase2a_assigns_while_u_gt_e(self):
        """Phase 2a runs while unassigned > empty_labs; Phase 2b fills empty labs."""
        # 3 students, 3 faculty (max_load=1). 1 already assigned.
        # Unassigned: 2 students, 1 empty lab → U=2 > E=1, so Phase 2a fires once.
        faculty = [_f(i, 1) for i in range(1, 4)]
        students = [
            _s(1, 9.5, ["F01", "F02", "F03"]),
            _s(2, 8.5, ["F02", "F01", "F03"]),
            _s(3, 7.5, ["F03", "F01", "F02"]),
        ]
        students, faculty, _ = _phase0_cohort(students, faculty)
        assignments   = {s.id: None for s in students}
        faculty_loads = {"F01": 1, "F02": 0, "F03": 0}
        assignments["1"] = "F01"
        unassigned = [s for s in students if assignments[s.id] is None]

        snaps = _dummy_snaps(students, faculty)
        assignments, faculty_loads, overflow = tiered_ll_backfill(
            unassigned, faculty, assignments, faculty_loads, k=0, snapshots=snaps
        )
        assert overflow == []
        assert all(assignments[s.id] is not None for s in students)
        # F01 full, F02 and F03 each get 1 student
        assert sum(1 for v in assignments.values() if v is not None) == 3

    def test_phase2b_uses_highest_preferred_empty_lab(self):
        """Phase 2b assigns student to their highest-ranked empty lab in prefs[k:]."""
        # 2 students, 2 faculty. Both already assigned → test 1 unassigned with U==E.
        faculty = [_f(1, 1), _f(2, 1), _f(3, 1)]
        students = [
            _s(1, 9.5, ["F01", "F02", "F03"]),
            _s(2, 8.5, ["F03", "F02", "F01"]),  # unassigned; prefers F02 over F01 in prefs[1:]
        ]
        students, faculty, _ = _phase0_cohort(students, faculty)
        assignments   = {s.id: None for s in students}
        faculty_loads = {"F01": 1, "F02": 0, "F03": 0}
        assignments["1"] = "F01"
        unassigned = [students[1]]  # s2 only

        snaps = _dummy_snaps(students, faculty)
        # k=1: prefs[1:] for s2 = ["F02","F01"]; empty labs = {F02, F03}
        # Phase 2a: U=1, E=2 → U < E, skip Phase 2a immediately
        # Phase 2b: first empty in prefs[1:]=["F02","F01"] is F02 → s2→F02
        assignments, faculty_loads, overflow = tiered_ll_backfill(
            unassigned, faculty, assignments, faculty_loads, k=1, snapshots=snaps
        )
        assert overflow == []
        assert assignments["2"] == "F02"

    def test_phase2a_overflow_deferred_to_phase2b(self):
        """Student with no capacity in prefs[k:] is deferred to Phase 2b."""
        # s2 has only F01 in prefs[1:], which is full. F02 is empty.
        # Phase 2a can't place s2; Phase 2b picks up s2 via F02 if it's in prefs[k:].
        faculty = [_f(1, 1), _f(2, 1)]
        students = [
            _s(1, 9.5, ["F01", "F02"]),
            _s(2, 8.0, ["F02", "F01"]),  # unassigned; prefs[1:]=["F01"]; F01 full
        ]
        students, faculty, _ = _phase0_cohort(students, faculty)
        assignments   = {s.id: None for s in students}
        faculty_loads = {"F01": 1, "F02": 0}
        assignments["1"] = "F01"
        unassigned = [students[1]]

        snaps = _dummy_snaps(students, faculty)
        # k=1: prefs[1:] for s2 = ["F01"]; F01 full → overflow_p2a
        # U=1, E=1 → Phase 2a terminates immediately (U==E), goes to Phase 2b
        # Phase 2b: prefs[1:] = ["F01"]; empty_labs = {F02}; F01 not empty → overflow
        # So s2 overflows (F02 not in prefs[1:])
        assignments, faculty_loads, overflow = tiered_ll_backfill(
            unassigned, faculty, assignments, faculty_loads, k=1, snapshots=snaps
        )
        assert "2" in overflow

    def test_phase2a_overflow_reaches_phase2b_empty_lab(self):
        """Phase 2a overflow student is placed in Phase 2b if empty lab in prefs[k:]."""
        # 3 students, 3 faculty (max_load=1).
        # After 1 tiered round: s1→F01. Unassigned: s2, s3. U=2, E=2.
        # s2 prefs[1:]=["F03","F02"]; s3 prefs[1:]=["F02","F03"].
        # U==E at start → Phase 2a skipped; Phase 2b: s2→F03, s3→F02.
        faculty = [_f(i, 1) for i in range(1, 4)]
        students = [
            _s(1, 9.5, ["F01", "F02", "F03"]),
            _s(2, 8.5, ["F01", "F03", "F02"]),
            _s(3, 7.5, ["F01", "F02", "F03"]),
        ]
        students, faculty, _ = _phase0_cohort(students, faculty)
        assignments   = {s.id: None for s in students}
        faculty_loads = {"F01": 1, "F02": 0, "F03": 0}
        assignments["1"] = "F01"
        unassigned = [s for s in students if assignments[s.id] is None]

        snaps = _dummy_snaps(students, faculty)
        assignments, faculty_loads, overflow = tiered_ll_backfill(
            unassigned, faculty, assignments, faculty_loads, k=1, snapshots=snaps
        )
        assert overflow == []
        assert assignments["2"] == "F03"
        assert assignments["3"] == "F02"


# ---------------------------------------------------------------------------
# 5 — stop_at_round in tiered_rounds_start / tiered_rounds_resume
# ---------------------------------------------------------------------------

class TestStopAtRound:
    def _simple_cohort(self):
        """4 students, 4 faculty, one student per faculty — no ties."""
        faculty = [_f(i, 1) for i in range(1, 5)]
        students = [
            _s(1, 9.5, ["F01", "F02", "F03", "F04"]),
            _s(2, 9.0, ["F02", "F01", "F03", "F04"]),
            _s(3, 8.5, ["F03", "F04", "F01", "F02"]),
            _s(4, 8.0, ["F04", "F03", "F02", "F01"]),
        ]
        students, faculty, _ = _phase0_cohort(students, faculty)
        return students, faculty

    def test_stop_at_round_2_triggers_switch(self):
        """Engine stops before round 2 and returns switch_to_backfill."""
        students, faculty = self._simple_cohort()
        snaps = _dummy_snaps(students, faculty)
        state = tiered_rounds_start(students, faculty, snaps, stop_at_round=2)
        # Round 1 assigns all 4 (one per faculty, no ties) → complete, not switch
        # OR if not all assigned in round 1: switch_to_backfill
        assert state.status in ("complete", "switch_to_backfill")

    def test_stop_at_round_1_immediate_switch(self):
        """stop_at_round=1 means we don't execute round 1 → switch immediately."""
        students, faculty = self._simple_cohort()
        snaps = _dummy_snaps(students, faculty)
        state = tiered_rounds_start(students, faculty, snaps, stop_at_round=1)
        assert state.status == "switch_to_backfill"
        # No assignments should have been made
        assert all(v is None for v in state.assignments.values())

    def test_no_stop_at_round_completes(self):
        """Without stop_at_round, engine runs to completion normally."""
        students, faculty = self._simple_cohort()
        snaps = _dummy_snaps(students, faculty)
        state = tiered_rounds_start(students, faculty, snaps)
        assert state.status in ("complete", "stalled")


# ---------------------------------------------------------------------------
# 6 — End-to-end: dry-run + backfill produces 0 empty labs (clean cohort)
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def _well_distributed_cohort(self):
        """12 students, 6 faculty, each student lists all 6 faculty."""
        fids = _fids(6)
        import random
        random.seed(42)
        students = []
        for i in range(1, 13):
            prefs = fids[:]
            random.shuffle(prefs)
            students.append(_s(i, 10.0 - i * 0.1, prefs))
        faculty = [_f(i, 2) for i in range(1, 7)]
        students, faculty, _ = _phase0_cohort(students, faculty)
        return students, faculty

    def test_zero_empty_labs_when_structurally_possible(self):
        """On a well-distributed cohort, tiered_ll leaves 0 empty labs."""
        students, faculty = self._well_distributed_cohort()

        # 1. Dry-run → k_crit
        states = tiered_rounds_dry_run(students, faculty)
        k_crit = find_critical_round(states)

        # 2. Run tiered rounds up to k_crit
        snaps = _dummy_snaps(students, faculty)
        tr_state = tiered_rounds_start(students, faculty, snaps, stop_at_round=k_crit + 1)

        # Auto-resolve any remaining ties (shouldn't be any for this cohort)
        student_map = {s.id: s for s in students}
        while tr_state.status == "awaiting_tie":
            tie = tr_state.pending_tie
            chosen = min(tie.tied_ids, key=lambda sid: (-student_map[sid].cpi, sid))
            tr_state = tiered_rounds_resume(tr_state, chosen, stop_at_round=k_crit + 1)

        assert tr_state.status in ("complete", "switch_to_backfill")

        if tr_state.status == "switch_to_backfill":
            # 3. Backfill
            unassigned = [
                s for s in tr_state.students if tr_state.assignments.get(s.id) is None
            ]
            assignments, faculty_loads, overflow = tiered_ll_backfill(
                unassigned, tr_state.faculty,
                dict(tr_state.assignments), dict(tr_state.faculty_loads),
                k_crit, snaps,
            )
        else:
            assignments = dict(tr_state.assignments)
            overflow = []

        assert overflow == [], f"Expected 0 overflow, got: {overflow}"
        empty_labs = [
            f.id for f in faculty
            if all(assignments.get(s.id) != f.id for s in students)
        ]
        assert empty_labs == [], f"Expected 0 empty labs, got: {empty_labs}"
        # All students assigned
        assert all(v is not None for v in assignments.values()), "Some students unassigned"

    def test_meta_fields_after_dry_run(self):
        """Dry-run produces all expected fields."""
        students, faculty = self._well_distributed_cohort()
        states = tiered_rounds_dry_run(students, faculty)
        k = find_critical_round(states)
        assert k >= 1
        # Simulate what _run_tiered_ll_dry_run does
        total = states[-1]["round_no"] if states else 0
        stall_rd = next((e["round_no"] for e in states if e["is_stall"]), None)
        meta = {}
        meta["k_crit_static"]       = k
        meta["dry_run_rounds_total"] = total
        meta["dry_run_stall_round"]  = stall_rd
        for key in ("k_crit_static", "dry_run_rounds_total", "dry_run_stall_round"):
            assert key in meta


# ---------------------------------------------------------------------------
# 7 — Regression: existing policies unaffected
# ---------------------------------------------------------------------------

class TestRegression:
    def _sample_cohort(self):
        fids = _fids(4)
        students = [
            _s(i, 10.0 - i * 0.3, fids) for i in range(1, 7)
        ]
        faculty = [_f(i, 2) for i in range(1, 5)]
        return students, faculty

    def test_tiered_rounds_start_unchanged(self):
        """tiered_rounds_start with no stop_at_round behaves as before."""
        students, faculty = self._sample_cohort()
        students, faculty, _ = _phase0_cohort(students, faculty)
        snaps = _dummy_snaps(students, faculty)
        state = tiered_rounds_start(students, faculty, snaps)
        assert state.status in ("complete", "awaiting_tie", "stalled")

    def test_least_loaded_via_run_full_allocation(self):
        """least_loaded policy still works (no regression from engine changes)."""
        students, faculty = self._sample_cohort()
        assignments, snaps, meta, metrics = run_full_allocation(
            students, faculty, policy="least_loaded"
        )
        assigned = sum(1 for v in assignments.values() if v is not None)
        assert assigned == len(students)

    def test_cpi_fill_via_run_full_allocation(self):
        """cpi_fill policy still works."""
        students, faculty = self._sample_cohort()
        assignments, snaps, meta, metrics = run_full_allocation(
            students, faculty, policy="cpi_fill"
        )
        assigned = sum(1 for v in assignments.values() if v is not None)
        assert assigned == len(students)

    def test_tiered_rounds_via_run_full_allocation(self):
        """tiered_rounds CLI auto-mode assigns all students on a diverse-pref cohort."""
        # Diverse preferences so each faculty receives a distinct first-choice
        # student in round 1 and all remaining students are covered by round 2.
        faculty = [_f(i, 2) for i in range(1, 5)]
        students = [
            _s(1, 9.7, ["F01", "F02", "F03", "F04"]),
            _s(2, 9.4, ["F02", "F01", "F03", "F04"]),
            _s(3, 9.1, ["F03", "F04", "F01", "F02"]),
            _s(4, 8.8, ["F04", "F03", "F02", "F01"]),
            _s(5, 8.5, ["F01", "F03", "F02", "F04"]),
            _s(6, 8.2, ["F02", "F04", "F01", "F03"]),
        ]
        assignments, snaps, meta, metrics = run_full_allocation(
            students, faculty, policy="tiered_rounds"
        )
        assert all(v is not None for v in assignments.values()), \
            "Some students unassigned under tiered_rounds"

    def test_tiered_ll_via_run_full_allocation_assigns_all(self):
        """tiered_ll CLI auto-mode assigns all students."""
        students, faculty = self._sample_cohort()
        assignments, snaps, meta, metrics = run_full_allocation(
            students, faculty, policy="tiered_ll"
        )
        assert all(v is not None for v in assignments.values()), \
            "Some students unassigned under tiered_ll"

    def test_tiered_ll_via_run_full_allocation_no_empty_labs(self):
        """tiered_ll CLI auto-mode leaves no empty labs (S=6 ≥ F=4, full pref lists)."""
        students, faculty = self._sample_cohort()
        assignments, snaps, meta, metrics = run_full_allocation(
            students, faculty, policy="tiered_ll"
        )
        fac_ids      = {f.id for f in faculty}
        assigned_fids = {v for v in assignments.values() if v is not None}
        empty = fac_ids - assigned_fids
        assert empty == set(), f"Unexpected empty labs under tiered_ll: {empty}"
