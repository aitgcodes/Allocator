"""
tests/test_metrics.py — Unit and integration tests for the NPSS/PSI metrics.

Run with:
    conda run -n allocator python -m pytest tests/test_metrics.py -v
"""

from src.allocator.state import Student, Faculty
from src.allocator.metrics import (
    collect_preference_ranks,
    npss_per_student_score,
    psi_per_student_score,
    compute_metrics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_student(sid, cpi, preferences, tier="A", n_tier=3):
    return Student(id=sid, name=f"Student {sid}", cpi=cpi,
                   preferences=preferences, tier=tier, n_tier=n_tier)


# ---------------------------------------------------------------------------
# Test 1 — Perfect allocation: every student gets their 1st choice
# ---------------------------------------------------------------------------

def test_perfect_allocation():
    """NPSS = 1.0 and mean PSI = 1.0 when every student gets rank 1."""
    students = [
        _make_student("s1", 9.0, ["f1", "f2", "f3"], tier="A", n_tier=3),
        _make_student("s2", 8.0, ["f2", "f1", "f3"], tier="B", n_tier=5),
        _make_student("s3", 7.0, ["f3", "f1", "f2"], tier="C", n_tier=None),
    ]
    # Update n_tier for C
    students[2].n_tier = None
    assignments = {"s1": "f1", "s2": "f2", "s3": "f3"}
    F = 3

    metrics = compute_metrics(students, assignments, F)

    assert abs(metrics["npss"] - 1.0) < 1e-9, f"NPSS should be 1.0, got {metrics['npss']}"
    assert abs(metrics["mean_psi"] - 1.0) < 1e-9, f"Mean PSI should be 1.0, got {metrics['mean_psi']}"
    assert metrics["overflow_count"] == 0


# ---------------------------------------------------------------------------
# Test 2 — All overflow: NPSS = 0.0, mean PSI > 0
# ---------------------------------------------------------------------------

def test_all_overflow():
    """
    Every student placed outside their window → NPSS = 0.0.
    PSI still > 0 because it doesn't penalise overflow.
    """
    # n_tier = 2 for all; assign at rank 3 (outside window)
    students = [
        _make_student("s1", 9.0, ["f1", "f2", "f3", "f4"], tier="A", n_tier=2),
        _make_student("s2", 8.0, ["f2", "f1", "f3", "f4"], tier="A", n_tier=2),
    ]
    # s1 assigned to f3 (rank 3 > n_tier=2), s2 assigned to f3 (rank 3 > n_tier=2)
    assignments = {"s1": "f3", "s2": "f3"}
    F = 4

    metrics = compute_metrics(students, assignments, F)

    assert abs(metrics["npss"] - 0.0) < 1e-9, f"NPSS should be 0.0, got {metrics['npss']}"
    assert metrics["mean_psi"] > 0.0, f"PSI should be > 0 even with overflow, got {metrics['mean_psi']}"
    assert metrics["overflow_count"] == 2
    # PSI for rank 3 out of F=4: 1 - 2/3 ≈ 0.333
    expected_psi = 1.0 - (3 - 1) / (4 - 1)
    assert abs(metrics["mean_psi"] - expected_psi) < 1e-9


# ---------------------------------------------------------------------------
# Test 3 — Mixed tiers: verify NPSS against hand-computed value
# ---------------------------------------------------------------------------

def test_mixed_tiers():
    """
    Small cohort with 2 Class A (n_tier=3), 3 Class B (n_tier=5), 2 Class C (n_tier=None/7).
    Verify NPSS against hand-computed value.
    """
    prefs_all = ["f1", "f2", "f3", "f4", "f5", "f6", "f7"]
    students = [
        # Class A, n_tier=3
        Student("a1", "A1", 9.0, prefs_all, tier="A", n_tier=3),  # rank 1 → score 3/3=1.0
        Student("a2", "A2", 8.5, prefs_all, tier="A", n_tier=3),  # rank 2 → score 2/3≈0.667
        # Class B, n_tier=5
        Student("b1", "B1", 8.0, prefs_all, tier="B", n_tier=5),  # rank 3 → score 3/5=0.6
        Student("b2", "B2", 7.5, prefs_all, tier="B", n_tier=5),  # rank 5 → score 1/5=0.2
        Student("b3", "B3", 7.0, prefs_all, tier="B", n_tier=5),  # rank 6 > 5 → score 0.0 (overflow)
        # Class C, n_tier=None → len(prefs)=7
        Student("c1", "C1", 6.5, prefs_all, tier="C", n_tier=None),  # rank 4 → score 4/7≈0.571
        Student("c2", "C2", 6.0, prefs_all, tier="C", n_tier=None),  # rank 7 → score 1/7≈0.143
    ]
    assignments = {
        "a1": "f1",  # rank 1
        "a2": "f2",  # rank 2
        "b1": "f3",  # rank 3
        "b2": "f5",  # rank 5
        "b3": "f6",  # rank 6 → overflow for B (n_tier=5)
        "c1": "f4",  # rank 4
        "c2": "f7",  # rank 7
    }
    F = 7

    # Hand-compute NPSS
    total_cpi = 9.0 + 8.5 + 8.0 + 7.5 + 7.0 + 6.5 + 6.0  # = 52.5
    scores = {
        "a1": 3/3,      # 1.0
        "a2": 2/3,      # 0.6667
        "b1": 3/5,      # 0.6
        "b2": 1/5,      # 0.2
        "b3": 0.0,      # overflow
        "c1": 4/7,      # 0.5714
        "c2": 1/7,      # 0.1429
    }
    cpis = {"a1": 9.0, "a2": 8.5, "b1": 8.0, "b2": 7.5, "b3": 7.0, "c1": 6.5, "c2": 6.0}
    expected_npss = sum(cpis[sid] / total_cpi * scores[sid] for sid in cpis)

    metrics = compute_metrics(students, assignments, F)

    assert abs(metrics["npss"] - expected_npss) < 1e-9, \
        f"NPSS mismatch: expected {expected_npss:.6f}, got {metrics['npss']:.6f}"
    assert metrics["overflow_count"] == 1  # only b3 overflows


# ---------------------------------------------------------------------------
# Test 4 — Class C denominator
# ---------------------------------------------------------------------------

def test_class_c_denominator():
    """
    A Class C student assigned at rank k out of F faculty should score
    (F - k + 1) / F for NPSS (since n_tier = None → uses len(preferences)).
    """
    F = 10
    prefs = [f"f{i}" for i in range(1, F + 1)]  # f1..f10
    student = Student("c1", "C1", 7.5, prefs, tier="C", n_tier=None)

    # Rank 4: score should be (10 - 4 + 1) / 10 = 7/10 = 0.7
    score = npss_per_student_score(student, 4)
    assert abs(score - 7 / 10) < 1e-9, f"Expected 0.7, got {score}"

    # Rank 10: score should be (10 - 10 + 1) / 10 = 1/10 = 0.1
    score_last = npss_per_student_score(student, 10)
    assert abs(score_last - 1 / 10) < 1e-9, f"Expected 0.1, got {score_last}"

    # Full compute_metrics check
    students = [student]
    assignments = {"c1": "f4"}
    metrics = compute_metrics(students, assignments, F)
    assert abs(metrics["npss"] - 0.7) < 1e-9


# ---------------------------------------------------------------------------
# Test 5 — Tiny cohort (all Class A, n_tier=2)
# ---------------------------------------------------------------------------

def test_tiny_cohort():
    """
    Class A with n_tier=2:
    - rank 1 → NPSS = 1.0
    - rank 2 → NPSS = 0.5
    - rank 3 → NPSS = 0.0 (outside window)
    Verify PSI values independently.
    """
    prefs = ["f1", "f2", "f3", "f4"]
    F = 4
    s_rank1 = Student("s1", "S1", 9.0, prefs, tier="A", n_tier=2)
    s_rank2 = Student("s2", "S2", 9.0, prefs, tier="A", n_tier=2)
    s_rank3 = Student("s3", "S3", 9.0, prefs, tier="A", n_tier=2)

    assert abs(npss_per_student_score(s_rank1, 1) - 1.0) < 1e-9
    assert abs(npss_per_student_score(s_rank2, 2) - 0.5) < 1e-9
    assert abs(npss_per_student_score(s_rank3, 3) - 0.0) < 1e-9

    # PSI for F=4: rank 1→1.0, rank 2→2/3≈0.667, rank 3→1/3≈0.333
    assert abs(psi_per_student_score(1, F) - 1.0) < 1e-9
    assert abs(psi_per_student_score(2, F) - 2/3) < 1e-9
    assert abs(psi_per_student_score(3, F) - 1/3) < 1e-9


# ---------------------------------------------------------------------------
# Test 6 — CPI weighting dominance
# ---------------------------------------------------------------------------

def test_cpi_weighting():
    """
    Two students with very different CPIs.
    Higher-CPI student's score dominates NPSS but not PSI (equal-weighted).

    s_high: CPI=9.0, assigned rank 1 (within window n_tier=2) → NPSS score = 1.0
    s_low:  CPI=1.0, assigned rank 3 (outside window n_tier=2) → NPSS score = 0.0

    NPSS = 0.9 * 1.0 + 0.1 * 0.0 = 0.9
    PSI (equal-weighted): rank 1 → 1.0, rank 3 out of F=4 → 1 - 2/3 = 0.333
    mean_psi = (1.0 + 0.333) / 2 = 0.667
    """
    prefs = ["f1", "f2", "f3", "f4"]
    F = 4
    # n_tier=2: window covers ranks 1-2 only
    s_high = Student("sh", "High", 9.0, prefs, tier="A", n_tier=2)
    s_low  = Student("sl", "Low",  1.0, prefs, tier="A", n_tier=2)
    students = [s_high, s_low]
    # s_high: rank 1 (within window) → NPSS = 1.0
    # s_low:  rank 3 (outside window, n_tier=2) → NPSS = 0.0
    assignments = {"sh": "f1", "sl": "f3"}

    metrics = compute_metrics(students, assignments, F)

    # NPSS: w_high = 9/10 = 0.9, w_low = 1/10 = 0.1
    expected_npss = (9.0 / 10.0) * 1.0 + (1.0 / 10.0) * 0.0
    assert abs(metrics["npss"] - expected_npss) < 1e-9, \
        f"NPSS: expected {expected_npss}, got {metrics['npss']}"

    # PSI (equal-weighted, F=4):
    # s_high rank 1 → 1.0; s_low rank 3 → 1 - 2/3 = 1/3
    expected_psi = (1.0 + (1.0 - 2.0 / 3.0)) / 2
    assert abs(metrics["mean_psi"] - expected_psi) < 1e-9, \
        f"Mean PSI: expected {expected_psi}, got {metrics['mean_psi']}"

    # NPSS (0.9) > mean_psi (≈0.667) because high-CPI student dominates NPSS
    assert metrics["npss"] > metrics["mean_psi"]


# ---------------------------------------------------------------------------
# Test 7 — Zero CPI guard
# ---------------------------------------------------------------------------

def test_zero_cpi_guard():
    """A student with cpi=0.0 should not cause division-by-zero."""
    prefs = ["f1", "f2"]
    F = 2
    s = Student("s1", "Zero", 0.0, prefs, tier="A", n_tier=2)
    students = [s]
    assignments = {"s1": "f1"}

    # Should not raise
    metrics = compute_metrics(students, assignments, F)
    assert "npss" in metrics
    assert 0.0 <= metrics["npss"] <= 1.0


# ---------------------------------------------------------------------------
# Test 8 — PSI formula
# ---------------------------------------------------------------------------

def test_psi_formula():
    """For F=10, rank=3 → PSI = 1 - 2/9 ≈ 0.7778. Verify exactly."""
    result = psi_per_student_score(3, 10)
    expected = 1.0 - (3 - 1) / (10 - 1)  # 1 - 2/9
    assert abs(result - expected) < 1e-12, f"Expected {expected}, got {result}"


# ---------------------------------------------------------------------------
# Test 9 — PSI boundary values
# ---------------------------------------------------------------------------

def test_psi_boundary_values():
    """rank=1 → PSI=1.0; rank=F → PSI=0.0."""
    F = 8
    assert abs(psi_per_student_score(1, F) - 1.0) < 1e-12, "rank=1 should give PSI=1.0"
    assert abs(psi_per_student_score(F, F) - 0.0) < 1e-12, "rank=F should give PSI=0.0"


# ---------------------------------------------------------------------------
# Test 10 — PSI ignores window
# ---------------------------------------------------------------------------

def test_psi_ignores_window():
    """
    A Class A student at rank 5 (outside N_A=3) should score:
    - NPSS = 0.0 (outside protection window)
    - PSI > 0 (PSI ignores window, scores based on global rank)
    """
    F = 10
    prefs = [f"f{i}" for i in range(1, F + 1)]
    student = Student("s1", "S1", 9.0, prefs, tier="A", n_tier=3)

    npss_score = npss_per_student_score(student, 5)
    psi_score  = psi_per_student_score(5, F)

    assert npss_score == 0.0, f"NPSS should be 0.0 for rank 5 > n_tier=3, got {npss_score}"
    expected_psi = 1.0 - (5 - 1) / (10 - 1)  # 1 - 4/9
    assert abs(psi_score - expected_psi) < 1e-12, \
        f"PSI should be {expected_psi}, got {psi_score}"
    assert psi_score > 0.0, "PSI should be > 0 for rank 5 out of 10"


# ---------------------------------------------------------------------------
# Test 11 — PSI degenerate case (F=1)
# ---------------------------------------------------------------------------

def test_psi_degenerate_f1():
    """F=1 → PSI = 1.0 regardless of rank."""
    assert abs(psi_per_student_score(1, 1) - 1.0) < 1e-12, "F=1 should give PSI=1.0"
    # Even with rank>1 (which shouldn't happen in practice), guard covers it
    assert abs(psi_per_student_score(None, 1) - 0.0) < 1e-12, "rank=None should give PSI=0.0"


# ---------------------------------------------------------------------------
# Test 12 — compute_metrics round-trip integration test
# ---------------------------------------------------------------------------

def test_compute_metrics_round_trip():
    """
    Run compute_metrics on a minimal complete set of students.
    Assert all required keys present and values in [0, 1].
    """
    prefs = ["f1", "f2", "f3", "f4", "f5"]
    F = 5
    students = [
        Student("s1", "S1", 9.0, prefs, tier="A",  n_tier=3),
        Student("s2", "S2", 8.0, prefs, tier="B",  n_tier=5),
        Student("s3", "S3", 7.0, prefs, tier="C",  n_tier=None),
        Student("s4", "S4", 8.5, prefs, tier="B1", n_tier=5),
        Student("s5", "S5", 7.5, prefs, tier="B2", n_tier=5),
    ]
    assignments = {
        "s1": "f1",
        "s2": "f3",
        "s3": "f5",
        "s4": "f2",
        "s5": "f4",
    }

    metrics = compute_metrics(students, assignments, F)

    # Required top-level keys
    assert "npss"           in metrics, "Missing 'npss' key"
    assert "mean_psi"       in metrics, "Missing 'mean_psi' key"
    assert "per_tier"       in metrics, "Missing 'per_tier' key"
    assert "per_student"    in metrics, "Missing 'per_student' key"
    assert "overflow_count" in metrics, "Missing 'overflow_count' key"

    # Values in [0, 1]
    assert 0.0 <= metrics["npss"]     <= 1.0, f"NPSS out of range: {metrics['npss']}"
    assert 0.0 <= metrics["mean_psi"] <= 1.0, f"Mean PSI out of range: {metrics['mean_psi']}"

    # per_student has entries for all students
    assert set(metrics["per_student"].keys()) == {"s1", "s2", "s3", "s4", "s5"}

    # Each per_student entry has required keys
    for sid, ps in metrics["per_student"].items():
        assert "tier"          in ps, f"Missing 'tier' in per_student[{sid}]"
        assert "n_tier"        in ps, f"Missing 'n_tier' in per_student[{sid}]"
        assert "assigned_rank" in ps, f"Missing 'assigned_rank' in per_student[{sid}]"
        assert "npss_score"    in ps, f"Missing 'npss_score' in per_student[{sid}]"
        assert "psi_score"     in ps, f"Missing 'psi_score' in per_student[{sid}]"
        assert "cpi_weight"    in ps, f"Missing 'cpi_weight' in per_student[{sid}]"
        assert 0.0 <= ps["npss_score"] <= 1.0
        assert 0.0 <= ps["psi_score"]  <= 1.0

    # per_tier keys exist for the tiers we used
    for tier in ("A", "B", "B1", "B2", "C"):
        assert tier in metrics["per_tier"], f"Missing tier '{tier}' in per_tier"

    # CPI weights should sum to ~1.0
    weight_sum = sum(ps["cpi_weight"] for ps in metrics["per_student"].values())
    assert abs(weight_sum - 1.0) < 1e-9, f"CPI weights should sum to 1.0, got {weight_sum}"
