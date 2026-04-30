"""
test_cli.py — Tests for CLI extensions: run_full_allocation with tiered policies
and the analyze.py compare subcommand.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).parent.parent
SAMPLE_STUDENTS = REPO_ROOT / "data" / "sample_students.csv"
SAMPLE_FACULTY  = REPO_ROOT / "data" / "sample_faculty.csv"
SRC_DIR     = REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_sample():
    sys.path.insert(0, str(SRC_DIR))
    from allocator.data_loader import load_students, load_faculty
    students = load_students(str(SAMPLE_STUDENTS))
    faculty  = load_faculty(str(SAMPLE_FACULTY))
    return students, faculty


# ---------------------------------------------------------------------------
# run_full_allocation: tiered_rounds with auto_tiebreak
# ---------------------------------------------------------------------------

def test_run_full_allocation_tiered_rounds_auto():
    """tiered_rounds with auto_tiebreak=True should assign all (or at most stall
    a few), returning a valid assignments dict with no exceptions."""
    sys.path.insert(0, str(SRC_DIR))
    from allocator.allocation import run_full_allocation

    students, faculty = _load_sample()
    assignments, snaps, meta, metrics = run_full_allocation(
        students, faculty, policy="tiered_rounds", auto_tiebreak=True
    )

    assert isinstance(assignments, dict)
    assert len(assignments) == len(students)
    # All students should have an entry (may be None only if stalled)
    for sid in [s.id for s in students]:
        assert sid in assignments
    # For 24 students, 8 faculty, we expect all assigned (no structural deficit)
    assigned_count = sum(1 for v in assignments.values() if v is not None)
    assert assigned_count == len(students), (
        f"Expected all {len(students)} students assigned; got {assigned_count}"
    )
    assert metrics["npss"] >= 0.0
    assert "advisor" in metrics


# ---------------------------------------------------------------------------
# run_full_allocation: tiered_ll with auto_tiebreak
# ---------------------------------------------------------------------------

def test_run_full_allocation_tiered_ll_auto():
    """tiered_ll with auto_tiebreak=True should assign all students and populate
    k_crit_static in meta."""
    sys.path.insert(0, str(SRC_DIR))
    from allocator.allocation import run_full_allocation

    students, faculty = _load_sample()
    assignments, snaps, meta, metrics = run_full_allocation(
        students, faculty, policy="tiered_ll", auto_tiebreak=True
    )

    assert isinstance(assignments, dict)
    assert len(assignments) == len(students)
    assigned_count = sum(1 for v in assignments.values() if v is not None)
    assert assigned_count == len(students), (
        f"Expected all {len(students)} students assigned; got {assigned_count}"
    )
    # k_crit_static should be set in meta
    assert "k_crit_static" in meta, "meta should contain k_crit_static for tiered_ll"
    assert isinstance(meta["k_crit_static"], int)
    assert metrics["npss"] >= 0.0


# ---------------------------------------------------------------------------
# run_full_allocation: tiered_rounds without auto_tiebreak raises ValueError
# ---------------------------------------------------------------------------

def test_run_full_allocation_tiered_rounds_no_auto_raises():
    """tiered_rounds without auto_tiebreak=True should raise ValueError."""
    sys.path.insert(0, str(SRC_DIR))
    from allocator.allocation import run_full_allocation

    students, faculty = _load_sample()
    with pytest.raises(ValueError, match="auto_tiebreak"):
        run_full_allocation(students, faculty, policy="tiered_rounds", auto_tiebreak=False)


# ---------------------------------------------------------------------------
# CLI help smoke test
# ---------------------------------------------------------------------------

def test_cli_help_smoke():
    """python -m allocator.allocation --help should exit 0."""
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    result = subprocess.run(
        [sys.executable, "-m", "allocator.allocation", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"--help exited {result.returncode}:\n{result.stderr}"
    assert "tiered_rounds" in result.stdout
    assert "tiered_ll" in result.stdout
    assert "--auto-tiebreak" in result.stdout


# ---------------------------------------------------------------------------
# analyze compare smoke test
# ---------------------------------------------------------------------------

def test_analyze_compare_smoke():
    """analyze compare on sample data should produce comparison_report.md."""
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable, "-m", "allocator.analyze", "compare",
                "--students", str(SAMPLE_STUDENTS),
                "--faculty",  str(SAMPLE_FACULTY),
                "--policies", "least_loaded", "cpi_fill",
                "--out", tmpdir,
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, (
            f"analyze compare exited {result.returncode}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        report = Path(tmpdir) / "comparison_report.md"
        assert report.exists(), "comparison_report.md should be created"
        content = report.read_text()
        assert "least_loaded" in content
        assert "cpi_fill" in content
