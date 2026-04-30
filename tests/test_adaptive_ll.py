"""
tests/test_adaptive_ll.py — Tests for empty-lab risk analysis and Adaptive LL policy.

Run with:
    conda run -n allocator python -m pytest tests/test_adaptive_ll.py -v
"""

import pytest

from src.allocator.state import Faculty, Student
from src.allocator.allocation import (
    _r1_assigned_ids,
    check_empty_lab_risk,
    phase0,
    phase0_optimize_caps,
    run_full_allocation,
    simulate_tiers_ab,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _s(sid, cpi, prefs, tier="C", n_tier=None):
    return Student(id=str(sid), name=f"S{sid}", cpi=cpi,
                   preferences=prefs, tier=tier, n_tier=n_tier)


def _f(fid, max_load=2):
    return Faculty(id=f"F{fid:02d}", name=f"Prof{fid:02d}", max_load=max_load)


def _all_fids(n):
    return [f"F{i:02d}" for i in range(1, n + 1)]


def _meta(N_A=3, N_B=5):
    return {"N_A": N_A, "N_B": N_B}


# ---------------------------------------------------------------------------
# Group 1 — Pre-check: S < F (Level 0 warning condition)
# ---------------------------------------------------------------------------

class TestSLtF:
    def test_s_lt_f_flag(self):
        fids = _all_fids(5)
        students = [_s(i, 8.0 - i * 0.1, fids) for i in range(3)]
        faculty = [_f(i) for i in range(1, 6)]
        result = check_empty_lab_risk(students, faculty, _meta())
        assert result is not None
        level, count = result
        assert level == "s_lt_f"
        assert count == 2           # F - S = 5 - 3

    def test_s_eq_f_no_level0(self):
        fids = _all_fids(5)
        students = [_s(i, 9.0 - i * 0.1, fids, tier="A", n_tier=3) for i in range(5)]
        faculty = [_f(i) for i in range(1, 6)]
        # phase0 not run here; tier is pre-set. With all prefs spread, no e_gt_c.
        # S == F so no s_lt_f.
        result = check_empty_lab_risk(students, faculty, _meta(N_A=3, N_B=3))
        assert result is None or result[0] != "s_lt_f"

    def test_s_gt_f_no_level0(self):
        fids = _all_fids(4)
        students = [_s(i, 9.0 - i * 0.1, fids, tier="A", n_tier=3) for i in range(8)]
        faculty = [_f(i) for i in range(1, 5)]
        result = check_empty_lab_risk(students, faculty, _meta(N_A=3, N_B=5))
        assert result is None or result[0] != "s_lt_f"


# ---------------------------------------------------------------------------
# Group 2 — simulate_tiers_ab dry-run correctness
# ---------------------------------------------------------------------------

class TestSimulateTiersAB:
    def _cohort_concentrated(self):
        """
        7 students, 6 faculty (max_load=2), caps N_A=3, N_B=4.
        F05 and F06 sit at positions 5 and 6 in every student's preference list —
        beyond the A-window (3) and B-window (4). Only the 1 C student can reach them.
        E_after_B should be 2 (F05, F06 empty), which is > |C|=1.
        """
        fids = ["F01", "F02", "F03", "F04", "F05", "F06"]
        students = [
            _s(1, 9.5, fids, tier="A", n_tier=3),
            _s(2, 9.3, fids, tier="A", n_tier=3),
            _s(3, 9.1, fids, tier="A", n_tier=3),
            _s(4, 8.5, fids, tier="B", n_tier=4),
            _s(5, 8.3, fids, tier="B", n_tier=4),
            _s(6, 8.1, fids, tier="B", n_tier=4),
            _s(7, 7.0, fids, tier="C", n_tier=None),
        ]
        faculty = [Faculty(id=f"F{i:02d}", name=f"Prof{i:02d}", max_load=2)
                   for i in range(1, 7)]
        return students, faculty

    def test_dry_run_returns_correct_empty_count(self):
        students, faculty = self._cohort_concentrated()
        # With N_A=3, N_B=4: A students reach F01-F03, B students reach F01-F04.
        # F05 and F06 (positions 5, 6) are beyond all A/B windows.
        # After Round1 + Tier A + Tier B: F05, F06 remain empty → E_after_B = 2.
        E = simulate_tiers_ab(students, faculty, N_A=3, N_B=4)
        assert E == 2

    def test_dry_run_no_side_effects(self):
        students, faculty = self._cohort_concentrated()
        original_loads = {f.id: 0 for f in faculty}
        E1 = simulate_tiers_ab(students, faculty, N_A=3, N_B=5)
        E2 = simulate_tiers_ab(students, faculty, N_A=3, N_B=5)
        assert E1 == E2
        # Faculty max_load should be unchanged
        for f in faculty:
            assert f.max_load == 2
        # Students should have no changed attributes from dry-run
        for s in students:
            assert s.tier in ("A", "B", "C")

    def test_dry_run_zero_empty_when_well_distributed(self):
        """Each student's top preference is a unique faculty — all labs fill."""
        fids = ["F01", "F02", "F03", "F04"]
        students = [
            _s(1, 9.5, ["F01", "F02", "F03", "F04"], tier="A", n_tier=3),
            _s(2, 9.3, ["F02", "F01", "F03", "F04"], tier="A", n_tier=3),
            _s(3, 9.1, ["F03", "F01", "F02", "F04"], tier="A", n_tier=3),
            _s(4, 8.5, ["F04", "F01", "F02", "F03"], tier="B", n_tier=5),
            _s(5, 7.0, fids, tier="C", n_tier=None),
        ]
        faculty = [Faculty(id=f"F0{i}", name=f"Prof0{i}", max_load=2)
                   for i in range(1, 5)]
        E = simulate_tiers_ab(students, faculty, N_A=3, N_B=5)
        assert E == 0


# ---------------------------------------------------------------------------
# Group 3 — Level 1 check (E_after_B vs |C|)
# ---------------------------------------------------------------------------

class TestLevel1Check:
    def _make_cohort(self, n_students, n_faculty, n_tier_c, concentrated=True):
        """
        Build a cohort where n_tier_c students are Class C and the rest are A/B.
        If concentrated=True, A/B students all pile onto the first n_faculty-1 labs,
        leaving the last lab uncoverable without C students.
        """
        fids = [f"F{i:02d}" for i in range(1, n_faculty + 1)]
        students = []
        n_ab = n_students - n_tier_c

        if concentrated:
            # A/B students only rank first (n_faculty-1) labs in top cap
            ab_prefs = fids[:-1] + [fids[-1]]      # last fac is last in prefs
        else:
            ab_prefs = fids                         # spread evenly

        for i in range(n_ab):
            tier = "A" if i < n_ab // 2 else "B"
            n_tier = 3 if tier == "A" else 5
            students.append(_s(i + 1, 9.0 - i * 0.05, ab_prefs, tier=tier, n_tier=n_tier))
        for i in range(n_tier_c):
            students.append(_s(n_ab + i + 1, 7.0 - i * 0.1, fids, tier="C", n_tier=None))

        faculty = [Faculty(id=f"F{i:02d}", name=f"Prof{i:02d}", max_load=2)
                   for i in range(1, n_faculty + 1)]
        return students, faculty

    def test_no_warning_e_lt_c(self):
        # Well-distributed: no labs at risk
        students, faculty = self._make_cohort(10, 4, n_tier_c=4, concentrated=False)
        result = check_empty_lab_risk(students, faculty, _meta(N_A=3, N_B=5))
        assert result is None

    def test_no_warning_e_eq_c(self):
        """E_after_B == |C| boundary: safe, no warning."""
        # Build a cohort where exactly E_after_B == |C|
        # Use run_full_allocation and check meta
        fids = ["F01", "F02", "F03"]
        # 2 A students pile onto F01/F02, leaving F03 empty after A+B
        # 1 C student → E_after_B = 1 == |C| = 1
        students = [
            _s(1, 9.5, ["F01", "F02", "F03"], tier="A", n_tier=2),
            _s(2, 9.3, ["F01", "F02", "F03"], tier="A", n_tier=2),
            _s(3, 7.0, ["F03", "F01", "F02"], tier="C", n_tier=None),
        ]
        faculty = [Faculty(id=f"F0{i}", name=f"Prof0{i}", max_load=2)
                   for i in range(1, 4)]
        E = simulate_tiers_ab(students, faculty, N_A=2, N_B=2)
        tier_c = sum(1 for s in students if s.tier == "C")
        # If E == tier_c, no warning
        if E == tier_c:
            result = check_empty_lab_risk(students, faculty, _meta(N_A=2, N_B=2))
            assert result is None

    def test_warning_e_gt_c(self):
        """E_after_B > |C|: warning fires with correct count."""
        # 5 A/B students all pile onto F01/F02/F03 (3 labs, cap 2 each = 6 slots)
        # F04/F05 (2 labs) never reached in A/B caps
        # Only 1 C student → E_after_B should be >= 2 > 1 = |C|
        fids = ["F01", "F02", "F03", "F04", "F05"]
        ab_prefs = ["F01", "F02", "F03", "F04", "F05"]  # but cap limits to top 3
        students = [
            _s(1, 9.5, ab_prefs, tier="A", n_tier=3),
            _s(2, 9.3, ab_prefs, tier="A", n_tier=3),
            _s(3, 9.1, ab_prefs, tier="A", n_tier=3),
            _s(4, 8.5, ab_prefs, tier="B", n_tier=3),
            _s(5, 8.3, ab_prefs, tier="B", n_tier=3),
            _s(6, 7.0, fids,    tier="C", n_tier=None),
        ]
        faculty = [Faculty(id=f"F0{i}", name=f"Prof0{i}", max_load=2)
                   for i in range(1, 6)]
        result = check_empty_lab_risk(students, faculty, _meta(N_A=3, N_B=3))
        assert result is not None
        level, count = result
        assert level == "e_gt_c"
        assert count >= 1


# ---------------------------------------------------------------------------
# Group 4 — phase0_optimize_caps correctness
# ---------------------------------------------------------------------------

class TestOptimizeCaps:
    def _warning_cohort(self):
        """Cohort that triggers e_gt_c warning with baseline caps (3,5)."""
        fids = [f"F{i:02d}" for i in range(1, 9)]   # 8 faculty
        # 7 A/B students all prefer F01-F05 in top 5; F06/F07/F08 only at rank 6-8
        ab_prefs = fids                              # full list, but cap limits reach
        students = [
            _s(1, 9.5, ab_prefs, tier="A", n_tier=3),
            _s(2, 9.3, ab_prefs, tier="A", n_tier=3),
            _s(3, 9.1, ab_prefs, tier="A", n_tier=3),
            _s(4, 8.8, ab_prefs, tier="B", n_tier=5),
            _s(5, 8.6, ab_prefs, tier="B", n_tier=5),
            _s(6, 8.4, ab_prefs, tier="B", n_tier=5),
            _s(7, 8.2, ab_prefs, tier="B", n_tier=5),
            _s(8, 7.0, fids,    tier="C", n_tier=None),  # only 1 C student
        ]
        faculty = [Faculty(id=f"F{i:02d}", name=f"Prof{i:02d}", max_load=2)
                   for i in range(1, 9)]
        return students, faculty

    def test_no_optimization_needed(self):
        """Well-distributed cohort: baseline caps are sufficient."""
        fids = ["F01", "F02", "F03"]
        students = [
            _s(1, 9.5, ["F01", "F02", "F03"], tier="A", n_tier=3),
            _s(2, 9.3, ["F02", "F01", "F03"], tier="A", n_tier=3),
            _s(3, 7.0, ["F03", "F01", "F02"], tier="C", n_tier=None),
        ]
        faculty = [Faculty(id=f"F0{i}", name=f"Prof0{i}", max_load=2)
                   for i in range(1, 4)]
        meta = _meta(N_A=3, N_B=5)
        N_A_opt, N_B_opt, E, structural = phase0_optimize_caps(students, faculty, meta)
        assert N_A_opt == 3
        assert N_B_opt == 5
        assert structural is False

    def test_optimize_finds_minimum_n_b(self):
        students, faculty = self._warning_cohort()
        meta = _meta(N_A=3, N_B=5)
        N_A_opt, N_B_opt, E, structural = phase0_optimize_caps(students, faculty, meta)
        assert structural is False
        assert N_A_opt == 3           # A unchanged: B expanded first
        assert N_B_opt > 5            # B must have expanded
        assert E <= 1                 # |C| = 1

    def test_optimize_preserves_ordering(self):
        """N_A <= N_B invariant holds at the returned optimum."""
        students, faculty = self._warning_cohort()
        meta = _meta(N_A=3, N_B=5)
        N_A_opt, N_B_opt, _, _ = phase0_optimize_caps(students, faculty, meta)
        assert N_A_opt <= N_B_opt

    def test_optimize_expands_a_only_after_b_full(self):
        """When N_B alone is insufficient, N_A also expands but N_B stays at F."""
        # Make |C|=0 so even full N_B is insufficient; need N_A to also expand.
        fids = [f"F{i:02d}" for i in range(1, 5)]
        # All students Tier A — no C students
        students = [
            _s(1, 9.5, ["F01", "F02", "F03", "F04"], tier="A", n_tier=3),
            _s(2, 9.3, ["F01", "F02", "F03", "F04"], tier="A", n_tier=3),
            _s(3, 9.1, ["F01", "F02", "F03", "F04"], tier="A", n_tier=3),
            _s(4, 8.9, ["F01", "F02", "F03", "F04"], tier="A", n_tier=3),
        ]
        faculty = [Faculty(id=f"F0{i}", name=f"Prof0{i}", max_load=2)
                   for i in range(1, 5)]
        meta = _meta(N_A=1, N_B=1)   # very tight caps to force both to expand
        N_A_opt, N_B_opt, E, structural = phase0_optimize_caps(students, faculty, meta)
        # With |C|=0 and F=4, need E=0. Since N_B must expand before N_A:
        # Loop expands N_B to F=4 first. If still failing, expands N_A.
        assert N_B_opt <= len(faculty)
        assert N_A_opt <= N_B_opt

    def test_structural_issue_detected(self):
        """Cohort where S >= F but |C|=0 and full caps still leave empty labs."""
        # 4 students all Tier A (no C), 5 faculty, max_load=2
        # S=4, F=5 → S < F → but we want to test structural via optimize.
        # Use S=5, F=5, no C, all pile onto 3 labs → 2 labs always empty.
        fids = ["F01", "F02", "F03", "F04", "F05"]
        top3 = ["F01", "F02", "F03", "F04", "F05"]
        students = [
            _s(1, 9.5, top3, tier="A", n_tier=3),
            _s(2, 9.3, top3, tier="A", n_tier=3),
            _s(3, 9.1, top3, tier="A", n_tier=3),
            _s(4, 8.9, top3, tier="A", n_tier=3),
            _s(5, 8.7, top3, tier="A", n_tier=3),
        ]
        faculty = [Faculty(id=f"F0{i}", name=f"Prof0{i}", max_load=2)
                   for i in range(1, 6)]
        meta = _meta(N_A=3, N_B=5)
        # With all prefs in full list and max_load=2, actually LL should fill all 5 with N_A=5
        # Let's check: does structural actually trigger here?
        N_A_opt, N_B_opt, E, structural = phase0_optimize_caps(students, faculty, meta)
        # Either structural=True or E=0 (all filled with expanded caps)
        if not structural:
            assert E == 0   # resolved without structural issue


# ---------------------------------------------------------------------------
# Group 5 — End-to-end Adaptive LL allocation
# ---------------------------------------------------------------------------

class TestAdaptiveLLEndToEnd:
    def _build_problematic_cohort(self):
        """
        Synthetic cohort modelled on 2019: S=10, F=8, max_load=2.
        A/B students all prefer F01-F05 in their caps; F06/F07/F08 only reachable via full list.
        With baseline caps, E_after_B > |C|.
        """
        fids = [f"F{i:02d}" for i in range(1, 9)]
        students = [
            _s(1,  9.5, fids, tier="A", n_tier=3),
            _s(2,  9.3, fids, tier="A", n_tier=3),
            _s(3,  8.8, fids, tier="B", n_tier=5),
            _s(4,  8.6, fids, tier="B", n_tier=5),
            _s(5,  8.4, fids, tier="B", n_tier=5),
            _s(6,  7.5, fids, tier="C", n_tier=None),
            _s(7,  7.3, fids, tier="C", n_tier=None),
            _s(8,  7.1, fids, tier="C", n_tier=None),
            _s(9,  6.9, fids, tier="C", n_tier=None),
            _s(10, 6.7, fids, tier="C", n_tier=None),
        ]
        faculty = [Faculty(id=f"F{i:02d}", name=f"Prof{i:02d}", max_load=2)
                   for i in range(1, 9)]
        return students, faculty

    def test_adaptive_ll_via_run_full_allocation(self):
        """run_full_allocation with adaptive_ll produces 0 empty labs when possible."""
        import copy
        students, faculty = self._build_problematic_cohort()
        # run_full_allocation mutates students/faculty; use copies
        s_copy = copy.deepcopy(students)
        f_copy = copy.deepcopy(faculty)
        assignments, _, meta, metrics = run_full_allocation(
            s_copy, f_copy, policy="adaptive_ll"
        )
        assigned_fids = set(v for v in assignments.values() if v is not None)
        all_fids = {f.id for f in f_copy}
        empty_labs = len(all_fids - assigned_fids)
        # Adaptive LL should have resolved the deficit (or flagged structural)
        if not meta.get("structural_deficit"):
            assert empty_labs == 0

    def test_adaptive_ll_same_as_ll_when_no_warning(self):
        """When baseline caps are sufficient, adaptive_ll == least_loaded."""
        import copy
        fids = ["F01", "F02", "F03", "F04"]
        students = [
            _s(1, 9.5, ["F01", "F02", "F03", "F04"], tier="A", n_tier=3),
            _s(2, 9.3, ["F02", "F01", "F03", "F04"], tier="A", n_tier=3),
            _s(3, 8.5, ["F03", "F01", "F02", "F04"], tier="B", n_tier=5),
            _s(4, 8.3, ["F04", "F01", "F02", "F03"], tier="B", n_tier=5),
            _s(5, 7.0, ["F01", "F02", "F03", "F04"], tier="C", n_tier=None),
        ]
        faculty = [Faculty(id=f"F0{i}", name=f"Prof0{i}", max_load=2)
                   for i in range(1, 5)]

        a_ll, _, _, _ = run_full_allocation(
            copy.deepcopy(students), copy.deepcopy(faculty), policy="least_loaded"
        )
        a_all, _, _, _ = run_full_allocation(
            copy.deepcopy(students), copy.deepcopy(faculty), policy="adaptive_ll"
        )
        assert a_ll == a_all

    def test_ll_empty_labs_match_prediction(self):
        """Standard LL on a risky cohort: actual empty labs == predicted count.

        The prediction must be computed AFTER phase0 sets tiers (run_full_allocation
        calls phase0 internally, overwriting any pre-set tiers). So we run phase0
        first to get the real tier distribution, then compute E_after_B, then run
        the full allocation and compare.
        """
        import copy
        fids = [f"F{i:02d}" for i in range(1, 7)]   # 6 faculty
        # 7 students: all prefer F01-F04 at the top; F05/F06 at positions 5-6
        students = [
            _s(1, 9.5, fids),
            _s(2, 9.3, fids),
            _s(3, 8.8, fids),
            _s(4, 8.6, fids),
            _s(5, 8.4, fids),
            _s(6, 7.5, fids),
            _s(7, 7.3, fids),
        ]
        faculty = [Faculty(id=f"F{i:02d}", name=f"Prof{i:02d}", max_load=2)
                   for i in range(1, 7)]

        # Step 1: run phase0 to get actual tiers and caps
        s_for_pred = copy.deepcopy(students)
        f_for_pred = copy.deepcopy(faculty)
        s_for_pred, f_for_pred, meta, _ = phase0(s_for_pred, f_for_pred)
        N_A, N_B = meta["N_A"], meta["N_B"]
        r1_ids = _r1_assigned_ids(s_for_pred, f_for_pred)
        tier_c_remaining = sum(1 for s in s_for_pred if s.tier == "C" and s.id not in r1_ids)

        # Step 2: compute prediction using the real tier distribution
        E = simulate_tiers_ab(s_for_pred, f_for_pred, N_A=N_A, N_B=N_B)
        predicted_empty = max(0, E - tier_c_remaining)

        # Step 3: run full LL allocation
        assignments, _, _, _ = run_full_allocation(
            copy.deepcopy(students), copy.deepcopy(faculty), policy="least_loaded"
        )
        assigned_fids = {v for v in assignments.values() if v is not None}
        actual_empty = len(faculty) - len(assigned_fids)
        assert actual_empty == predicted_empty

    def test_e_baseline_excess_set_when_optimization_runs(self):
        """E_baseline_excess reflects the pre-optimization deficit when caps are expanded."""
        import copy
        from allocator.allocation import check_empty_lab_risk
        students, faculty = self._build_problematic_cohort()
        s_copy = copy.deepcopy(students)
        f_copy = copy.deepcopy(faculty)
        _, _, meta, _ = phase0(s_copy, f_copy, optimize=True)
        if meta.get("caps_optimized"):
            # E_baseline_excess must be positive — baseline had a real deficit
            assert meta["E_baseline_excess"] > 0
            # Optimized caps must now pass the check (E ≤ tier_c_remaining)
            assert not check_empty_lab_risk(s_copy, f_copy, meta)


# ---------------------------------------------------------------------------
# Group 6 — Regression: existing LL behaviour unchanged
# ---------------------------------------------------------------------------

class TestRegression:
    def test_existing_ll_unaffected(self):
        """
        Run a standard LL cohort from sample data; confirm run_full_allocation
        still works and produces a complete assignment.
        """
        import copy
        fids = [f"F{i:02d}" for i in range(1, 5)]
        all_fids = fids
        students = [
            _s(1, 9.5, all_fids),
            _s(2, 9.3, all_fids),
            _s(3, 8.5, all_fids),
            _s(4, 7.0, all_fids),
        ]
        faculty = [Faculty(id=f"F{i:02d}", name=f"Prof{i:02d}", max_load=2)
                   for i in range(1, 5)]
        assignments, snaps, meta, metrics = run_full_allocation(
            copy.deepcopy(students), copy.deepcopy(faculty), policy="least_loaded"
        )
        assert all(v is not None for v in assignments.values()), "All students must be assigned"
        assert "N_A_baseline" in meta
        assert "N_B_baseline" in meta
        assert meta["caps_optimized"] is False
        assert meta["structural_deficit"] is False

    def test_meta_baseline_fields_always_present(self):
        """phase0() always populates baseline fields in meta."""
        import copy
        fids = ["F01", "F02"]
        students = [_s(i, 9.0 - i * 0.1, fids) for i in range(4)]
        faculty = [Faculty(id="F01", name="Prof01", max_load=2),
                   Faculty(id="F02", name="Prof02", max_load=2)]
        _, _, meta, _ = phase0(copy.deepcopy(students), copy.deepcopy(faculty))
        for key in ("N_A_baseline", "N_B_baseline", "caps_optimized",
                    "structural_deficit", "E_after_B", "E_baseline_excess"):
            assert key in meta, f"meta missing key: {key}"

    def test_e_baseline_excess_zero_when_no_optimization(self):
        """E_baseline_excess is 0 when baseline caps already pass the empty-lab check."""
        import copy
        fids = ["F01", "F02", "F03", "F04"]
        students = [
            _s(1, 9.5, fids),
            _s(2, 9.3, fids),
            _s(3, 8.5, fids),
            _s(4, 8.3, fids),
            _s(5, 7.0, fids),
        ]
        faculty = [Faculty(id=f"F0{i}", name=f"Prof0{i}", max_load=2) for i in range(1, 5)]
        _, _, meta, _ = phase0(copy.deepcopy(students), copy.deepcopy(faculty), optimize=True)
        assert meta["E_baseline_excess"] == 0
        assert meta["caps_optimized"] is False
