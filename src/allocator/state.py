"""
state.py — AllocationSnapshot dataclass and snapshot list.

Each step in the allocation process appends one AllocationSnapshot to a
SnapshotList.  The visualiser and Dash app scrub through this list to
replay the allocation step by step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Core domain objects (shared across the package)
# ---------------------------------------------------------------------------

@dataclass
class Student:
    """Represents one master's student."""
    id: str
    name: str
    cpi: float
    preferences: List[str]          # ordered faculty IDs, no duplicates
    tier: Optional[str] = None      # 'A' | 'B' | 'C'  — set during Phase 0
    n_tier: Optional[int] = None    # effective preference-protection cap


@dataclass
class Faculty:
    """Represents one faculty advisor."""
    id: str
    name: str
    max_load: int                   # upper bound on students
    min_load: int = 1               # lower bound (protocol: no empty labs)
    current_load: int = 0


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

@dataclass
class AllocationSnapshot:
    """
    A complete picture of the allocation state at a single moment.

    Fields
    ------
    step            : monotonically increasing counter (0 = initial state)
    phase           : human-readable phase label
    event           : one-line description of what just happened
    assignments     : student_id  ->  faculty_id  (None if unassigned)
    faculty_loads   : faculty_id  ->  current student count
    unassigned      : set of student IDs not yet placed
    r1_candidates   : faculty_id  ->  [student_ids sorted by CPI desc]
                      populated only while Round 1 selection is in progress
    preference_rank : student_id  ->  rank used for this assignment (1-based)
                      populated only for the student just assigned; None otherwise
    """

    step: int
    phase: str
    event: str
    assignments: Dict[str, Optional[str]]
    faculty_loads: Dict[str, int]
    unassigned: Set[str]
    r1_candidates: Dict[str, List[str]] = field(default_factory=dict)
    preference_rank: Optional[Dict[str, int]] = None   # {student_id: rank}


# ---------------------------------------------------------------------------
# SnapshotList — thin wrapper around a plain list
# ---------------------------------------------------------------------------

class SnapshotList:
    """
    Ordered sequence of AllocationSnapshots produced during a run.

    Usage
    -----
        snapshots = SnapshotList()
        snapshots.append(snap)
        for snap in snapshots:
            ...
        snap = snapshots[i]
        n    = len(snapshots)
    """

    def __init__(self) -> None:
        self._snaps: List[AllocationSnapshot] = []

    def append(self, snap: AllocationSnapshot) -> None:
        self._snaps.append(snap)

    def __getitem__(self, idx: int) -> AllocationSnapshot:
        return self._snaps[idx]

    def __len__(self) -> int:
        return len(self._snaps)

    def __iter__(self):
        return iter(self._snaps)

    def last(self) -> Optional[AllocationSnapshot]:
        return self._snaps[-1] if self._snaps else None
