"""
state.py — AllocationSnapshot dataclass and snapshot list.

Each step in the allocation process appends one AllocationSnapshot to a
SnapshotList.  The visualiser and Dash app scrub through this list to
replay the allocation step by step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any


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


# ---------------------------------------------------------------------------
# Tiered-rounds engine state  (for "tiered_rounds" allocation protocol)
# ---------------------------------------------------------------------------

@dataclass
class PendingTie:
    """One manual tie-break decision pausing the tiered-rounds engine."""

    round_no: int
    advisor_id: str
    advisor_name: str
    candidate_ids: List[str]            # all students who named this advisor this round
    candidate_names: Dict[str, str]     # student_id -> name
    candidate_cpis: Dict[str, float]    # student_id -> CPI
    tied_ids: List[str]                 # subset sharing the top CPI
    tied_cpi: float
    reason: str                         # human-readable pause reason


@dataclass
class TieredRoundsState:
    """Resumable engine state for the 'tiered_rounds' allocation protocol."""

    round_no: int
    students: List[Student]
    faculty: List[Faculty]
    assignments: Dict[str, Optional[str]]
    faculty_loads: Dict[str, int]
    snapshots: SnapshotList
    saturated_advisors: Set[str]        # advisors full at end of a previous round
    pending_tie: Optional[PendingTie]   # current tie awaiting resolution
    pending_tie_queue: List[PendingTie] # remaining ties in the current round
    trace_log: List[Dict[str, Any]]     # round-by-round audit records
    status: str                         # "running"|"awaiting_tie"|"awaiting_round_picks"|"complete"|"stalled"|"switch_to_backfill"
    stall_unassigned: List[str]         # IDs of students that could not be assigned
    # populated when status == "awaiting_round_picks": advisor_id → [student_ids] sorted by CPI desc
    pending_round_groups: Dict[str, List[str]] = field(default_factory=dict)
