"""
allocation.py — Full allocation engine.

Phases
------
    phase0(students, faculty)
        → Computes tiers, N_tier, max_load.
          Returns (updated students, updated faculty, meta dict, SnapshotList).

    round1(students, faculty, snapshots, r1_picks)
        → Global first-choice pass.
          r1_picks: optional dict {faculty_id: student_id} for pre-committed picks
          (used when loading from a Phase-0 report or in HTML/auto mode).
          Returns (assignments dict, updated faculty loads, SnapshotList).

    main_allocation(students, faculty, assignments, faculty_loads, snapshots)
        → Class A → B → C sequential allocation.
          Returns (final assignments dict, SnapshotList).

Standalone CLI usage
--------------------
    python -m allocator.allocation --phase0-only \\
        --students data/sample_students.csv \\
        --faculty  data/sample_faculty.csv  \\
        --out      reports/

    Runs only Phase 0, writes phase0_report.csv + phase0_meta.csv, then exits.
"""

from __future__ import annotations

import copy
import math
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from .data_loader import save_phase0_report
from .metrics import compute_metrics
from .state import (
    AllocationSnapshot,
    Faculty,
    PendingTie,
    SnapshotList,
    Student,
    TieredRoundsState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(
    step_counter: list,          # mutable single-element list used as counter ref
    phase: str,
    event: str,
    assignments: Dict[str, Optional[str]],
    faculty_loads: Dict[str, int],
    unassigned: Set[str],
    r1_candidates: Optional[Dict[str, List[str]]] = None,
    preference_rank: Optional[Dict[str, int]] = None,
) -> AllocationSnapshot:
    step_counter[0] += 1
    return AllocationSnapshot(
        step=step_counter[0],
        phase=phase,
        event=event,
        assignments=copy.copy(assignments),
        faculty_loads=copy.copy(faculty_loads),
        unassigned=copy.copy(unassigned),
        r1_candidates=copy.copy(r1_candidates) if r1_candidates else {},
        preference_rank=copy.copy(preference_rank) if preference_rank else None,
    )


def _sorted_by_cpi(students: List[Student]) -> List[Student]:
    """Descending CPI, tie-break by student ID (lexicographic)."""
    return sorted(students, key=lambda s: (-s.cpi, s.id))


def _least_loaded_choice(
    student: Student,
    candidate_faculty_ids: List[str],
    faculty_map: Dict[str, Faculty],
    faculty_loads: Dict[str, int],
) -> Optional[Tuple[str, int]]:
    """
    Among candidate_faculty_ids that still have capacity, return
    (faculty_id, preference_rank_1based) for the least-loaded one,
    with ties broken by earliest position in the student's preference list.

    Returns None if no eligible faculty has remaining capacity.
    """
    eligible = [
        fid for fid in candidate_faculty_ids
        if faculty_loads[fid] < faculty_map[fid].max_load
    ]
    if not eligible:
        return None

    min_load = min(faculty_loads[fid] for fid in eligible)
    tied = [fid for fid in eligible if faculty_loads[fid] == min_load]

    # tie-break: earliest in student's own preference list
    pref_index = {fid: i for i, fid in enumerate(student.preferences)}
    tied.sort(key=lambda fid: pref_index.get(fid, len(student.preferences)))
    chosen = tied[0]

    # 1-based rank in the student's full preference list
    rank = pref_index.get(chosen, -1) + 1
    return chosen, rank


def _nonempty_choice(
    student: Student,
    candidate_faculty_ids: List[str],
    faculty_map: Dict[str, Faculty],
    faculty_loads: Dict[str, int],
) -> Optional[Tuple[str, int]]:
    """
    'nonempty' policy: prefer the highest-preferred empty lab (load == 0)
    among candidates with remaining capacity.  If no empty lab exists,
    fall back to the highest-preferred faculty that still has capacity
    (earliest in the student's preference list, regardless of load).

    Returns (faculty_id, preference_rank_1based), or None if no candidate
    has remaining capacity.
    """
    pref_index = {fid: i for i, fid in enumerate(student.preferences)}
    eligible = [
        fid for fid in candidate_faculty_ids
        if faculty_loads[fid] < faculty_map[fid].max_load
    ]
    if not eligible:
        return None

    empty = [fid for fid in eligible if faculty_loads[fid] == 0]
    pool = empty if empty else eligible
    pool.sort(key=lambda fid: pref_index.get(fid, len(student.preferences)))
    chosen = pool[0]
    rank = pref_index.get(chosen, -1) + 1
    return chosen, rank


def _highest_preferred_empty(
    student: Student,
    faculty_map: Dict[str, Faculty],
    faculty_loads: Dict[str, int],
) -> Optional[Tuple[str, int]]:
    """
    Phase 2 selection rule for 'cpi_fill' policy.

    Iterate through student.preferences in order (full list, no N_tier cap).
    Return (faculty_id, rank_1based) for the first faculty whose
    faculty_loads[fid] == 0 (empty lab).

    Returns None if no empty lab is found — this indicates a protocol-state
    inconsistency and the caller should raise RuntimeError.
    """
    for rank, fid in enumerate(student.preferences, start=1):
        if fid in faculty_loads and faculty_loads[fid] == 0:
            return fid, rank
    return None


# ---------------------------------------------------------------------------
# Phase 0
# ---------------------------------------------------------------------------

def phase0(
    students: List[Student],
    faculty: List[Faculty],
    out_dir: Optional[str] = None,
    optimize: bool = False,
) -> Tuple[List[Student], List[Faculty], dict, SnapshotList]:
    """
    Phase 0: Compute tiers, N_tier, max_load per faculty.
    Optionally write the Phase-0 report to out_dir.

    Protocol rules implemented:
    - Tiers based on 70th / 90th CPI percentiles with ±0.1 grace band.
    - If >40% of students cluster in one band → quartiles.
    - If S < 10 → all Class A, N_tier = 2.
    - N_tier standard: N_A=3, N_B=5, N_C=All (None).
    - N_tier scaled (S/F > 4): N_A=4, N_B=6, N_C=All.
    - Faculty max_load: CSV override if present, else floor(S/F)+1.

    Returns
    -------
    (students, faculty, meta, snapshots)
        students : updated with .tier and .n_tier
        faculty  : updated with .max_load filled in
        meta     : dict of cohort-level parameters (also written to CSV)
        snapshots: SnapshotList (single Phase-0 snapshot)
    """
    S = len(students)
    F = len(faculty)
    ratio = S / F if F else float("inf")

    cpis = np.array([s.cpi for s in students])

    # --- common max_load (formula) ---
    common_max_load = math.floor(S / F) + 1 if F else S

    # fill in formula value for faculty without an explicit max_load
    for fac in faculty:
        if fac.max_load == -1:
            fac.max_load = common_max_load

    faculty_map = {f.id: f for f in faculty}
    faculty_loads = {f.id: 0 for f in faculty}

    # --- special case: tiny cohort ---
    if S < 10:
        for s in students:
            s.tier = "A"
            s.n_tier = 2
        meta = _build_meta(S, F, ratio, "tiny-cohort", None, None, None, None, None, 0.1,
                           3, 5, common_max_load)
        meta.update({
            "N_A_baseline": 3, "N_B_baseline": 5,
            "caps_optimized": False, "structural_deficit": False, "E_after_B": None,
        })
        snaps = SnapshotList()
        assignments = {s.id: None for s in students}
        unassigned  = {s.id for s in students}
        snaps.append(_snap(
            [0], "Phase0",
            f"Tiny cohort (S={S}<10): all students → Class A, N_tier=2",
            assignments, faculty_loads, unassigned,
        ))
        if out_dir:
            save_phase0_report(students, meta, out_dir)
        return students, faculty, meta, snaps

    # --- determine tier mode ---
    p70 = float(np.percentile(cpis, 70))
    p90 = float(np.percentile(cpis, 90))
    grace = 0.1

    # check clustering: would >40% fall in a single percentile band?
    n_top    = int(np.sum(cpis >= p90 - grace))
    n_mid    = int(np.sum((cpis >= p70 - grace) & (cpis < p90 - grace)))
    n_bottom = int(np.sum(cpis < p70 - grace))

    if max(n_top, n_mid, n_bottom) / S > 0.40:
        mode = "quartile"
        p25 = float(np.percentile(cpis, 25))
        p50 = float(np.percentile(cpis, 50))
        p75 = float(np.percentile(cpis, 75))
        for s in students:
            if s.cpi >= p75:
                s.tier = "A"
            elif s.cpi >= p50:
                s.tier = "B1"
            elif s.cpi >= p25:
                s.tier = "B2"
            else:
                s.tier = "C"
        p_low, p_mid, p_high = p25, p50, p75
        p_low_pct, p_high_pct = 25, 75
    else:
        mode = "percentile"
        for s in students:
            if s.cpi >= p90 - grace:
                s.tier = "A"
            elif s.cpi >= p70 - grace:
                s.tier = "B"
            else:
                s.tier = "C"
        p_low, p_mid, p_high = p70, None, p90
        p_low_pct, p_high_pct = 70, 90

    # --- N_tier ---
    if ratio > 4:
        N_A, N_B = 4, 6
    else:
        N_A, N_B = 3, 5

    for s in students:
        if s.tier == "A":
            s.n_tier = min(N_A, len(s.preferences)) or N_A
        elif s.tier in ("B", "B1", "B2"):
            s.n_tier = min(N_B, len(s.preferences)) or N_B
        else:
            s.n_tier = None    # Class C → global cap

    # --- build snapshot ---
    assignments = {s.id: None for s in students}
    unassigned  = {s.id for s in students}
    counts = {t: sum(1 for s in students if s.tier == t)
              for t in ("A", "B", "B1", "B2", "C")}
    if mode == "quartile":
        tier_str = (f"A={counts['A']} B1={counts['B1']} "
                    f"B2={counts['B2']} C={counts['C']}")
        pct_str = (f"p{p_low_pct}={p_low:.2f} p50={p_mid:.2f} "
                   f"p{p_high_pct}={p_high:.2f}")
    else:
        tier_str = f"A={counts['A']} B={counts['B']} C={counts['C']}"
        pct_str = f"p{p_low_pct}={p_low:.2f} p{p_high_pct}={p_high:.2f}"
    event = (
        f"Phase 0 complete | mode={mode} | "
        f"{pct_str} grace=±{grace} | "
        f"S={S} F={F} ratio={ratio:.2f} | "
        f"N_A={N_A} N_B={N_B} N_C=All | "
        f"max_load(formula)={common_max_load} | "
        f"Class {tier_str}"
    )

    meta = _build_meta(S, F, ratio, mode, p_low, p_mid, p_high, p_low_pct, p_high_pct, grace,
                       N_A, N_B, common_max_load)

    snaps = SnapshotList()
    snaps.append(_snap([0], "Phase0", event, assignments, faculty_loads, unassigned))

    # --- baseline cap fields (always present in meta) ---
    meta.update({
        "N_A_baseline":     N_A,
        "N_B_baseline":     N_B,
        "caps_optimized":   False,
        "structural_deficit": False,
        "E_after_B":        None,
    })

    # --- Adaptive LL: optimize caps if requested ---
    if optimize:
        risk = check_empty_lab_risk(students, faculty, meta)
        if risk and risk[0] == "e_gt_c":
            N_A_opt, N_B_opt, E_opt, structural = phase0_optimize_caps(students, faculty, meta)
            meta["N_A"] = N_A_opt
            meta["N_B"] = N_B_opt
            meta["caps_optimized"] = (N_A_opt != N_A or N_B_opt != N_B)
            meta["structural_deficit"] = structural
            meta["E_after_B"] = E_opt
            for s in students:
                if s.tier == "A":
                    s.n_tier = min(N_A_opt, len(s.preferences)) or N_A_opt
                elif s.tier in ("B", "B1", "B2"):
                    s.n_tier = min(N_B_opt, len(s.preferences)) or N_B_opt

    if out_dir:
        save_phase0_report(students, meta, out_dir)

    return students, faculty, meta, snaps


def _build_meta(S, F, ratio, mode, p_low, p_mid, p_high, p_low_pct, p_high_pct, grace, N_A, N_B, common_max_load) -> dict:
    return {
        "cohort_size":      S,
        "faculty_count":    F,
        "ratio":            round(ratio, 4),
        "mode":             mode,
        "p_low_pct":        p_low_pct if p_low_pct is not None else "",
        "p_high_pct":       p_high_pct if p_high_pct is not None else "",
        "p_low":            round(p_low, 4) if p_low is not None else "",
        "p_mid":            round(p_mid, 4) if p_mid is not None else "",
        "p_high":           round(p_high, 4) if p_high is not None else "",
        "grace":            grace,
        "N_A":              N_A,
        "N_B":              N_B,
        "common_max_load":  common_max_load,
    }


# ---------------------------------------------------------------------------
# Empty-lab risk analysis (used by LL and Adaptive LL)
# ---------------------------------------------------------------------------

def simulate_tiers_ab(
    students: List[Student],
    faculty: List[Faculty],
    N_A: int,
    N_B: int,
) -> int:
    """
    Cheap deterministic dry-run of Round 1 + Tiers A+B under the LL rule.
    No snapshots, no mutations to students or faculty objects.
    Requires students to have .tier set (call after phase0 tier classification).

    Returns E_after_B: number of faculty with zero assigned students after the
    simulated Round 1 + Tier A + Tier B passes.
    """
    faculty_map   = {f.id: f for f in faculty}
    faculty_loads = {f.id: 0 for f in faculty}
    assigned: Set[str] = set()
    fac_ids = {f.id for f in faculty}

    # Round 1: highest-CPI first-choice student wins each faculty's single pick
    buckets: Dict[str, List[Student]] = defaultdict(list)
    for s in students:
        if s.preferences and s.preferences[0] in fac_ids:
            buckets[s.preferences[0]].append(s)
    for fid, applicants in buckets.items():
        picked = _sorted_by_cpi(applicants)[0]
        assigned.add(picked.id)
        faculty_loads[fid] += 1

    def _run_dry(pool: List[Student], cap: int) -> None:
        for s in _sorted_by_cpi(pool):
            if s.id in assigned:
                continue
            result = _least_loaded_choice(s, s.preferences[:cap], faculty_map, faculty_loads)
            if result:
                fid, _ = result
                assigned.add(s.id)
                faculty_loads[fid] += 1

    quartile_mode = any(s.tier in ("B1", "B2") for s in students)
    _run_dry([s for s in students if s.tier == "A"], N_A)
    if quartile_mode:
        _run_dry([s for s in students if s.tier in ("A", "B1")], N_B)
        _run_dry([s for s in students if s.tier in ("A", "B1", "B2")], N_B)
    else:
        _run_dry([s for s in students if s.tier in ("A", "B")], N_B)

    return sum(1 for load in faculty_loads.values() if load == 0)


def check_empty_lab_risk(
    students: List[Student],
    faculty: List[Faculty],
    meta: dict,
) -> Optional[Tuple[str, int]]:
    """
    Check for empty-lab risk after Phase 0a tier classification.

    Returns None (no risk), or (level, count) where:
      "s_lt_f"  S < F; count = guaranteed empty labs (F − S).
      "e_gt_c"  E_after_B > |C|; count = guaranteed empty labs (E_after_B − |C|).

    Prerequisite: students have .tier set and meta contains N_A, N_B.
    """
    S, F = len(students), len(faculty)
    if S < F:
        return ("s_lt_f", F - S)
    tier_c = sum(1 for s in students if s.tier == "C")
    E = simulate_tiers_ab(students, faculty, meta["N_A"], meta["N_B"])
    if E > tier_c:
        return ("e_gt_c", E - tier_c)
    return None


def phase0_optimize_caps(
    students: List[Student],
    faculty: List[Faculty],
    meta: dict,
) -> Tuple[int, int, int, bool]:
    """
    Find the minimum N_A, N_B caps such that E_after_B <= |C| (Adaptive LL).

    Invariant: N_A <= N_B <= F (Tier A always at least as protected as Tier B).
    N_B expands first; N_A expands only after N_B reaches F.

    Returns (N_A_opt, N_B_opt, E_after_B, structural) where
    structural=True means no window adjustment can resolve the empty-lab deficit.
    """
    F = len(faculty)
    tier_c = sum(1 for s in students if s.tier == "C")
    N_A, N_B = meta["N_A"], meta["N_B"]

    while True:
        E = simulate_tiers_ab(students, faculty, N_A, N_B)
        if E <= tier_c:
            return N_A, N_B, E, False
        if N_B < F:
            N_B += 1
        elif N_A < N_B:
            N_A += 1
        else:                    # N_A = N_B = F, still E > |C|
            return N_A, N_B, E, True


# ---------------------------------------------------------------------------
# Round 1 — Global first-choice pass
# ---------------------------------------------------------------------------

def build_r1_candidate_lists(
    students: List[Student],
    faculty: List[Faculty],
) -> Dict[str, List[str]]:
    """
    For each faculty, collect student IDs whose 1st preference is that faculty,
    sorted by CPI descending (tie-break: student ID).

    Returns
    -------
    dict: faculty_id -> [student_id, ...]   (only faculties with ≥1 applicant)
    """
    from collections import defaultdict
    buckets: Dict[str, List[Student]] = defaultdict(list)
    fac_ids = {f.id for f in faculty}

    for s in students:
        if s.preferences and s.preferences[0] in fac_ids:
            buckets[s.preferences[0]].append(s)

    return {
        fid: [s.id for s in _sorted_by_cpi(bucket)]
        for fid, bucket in buckets.items()
    }


def round1(
    students: List[Student],
    faculty: List[Faculty],
    snapshots: SnapshotList,
    r1_picks: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, Optional[str]], Dict[str, int], SnapshotList]:
    """
    Round 1: each faculty picks exactly one student from their 1st-choice
    applicant list (sorted by CPI desc).

    Parameters
    ----------
    students   : list of Student (with .tier set)
    faculty    : list of Faculty (with .max_load set)
    snapshots  : SnapshotList to append to (Phase-0 snap already in it)
    r1_picks   : optional {faculty_id: student_id}
                 If None → auto-mode: top-CPI student is picked automatically.
                 In Dash interactive mode the app passes in the operator's choices.

    Returns
    -------
    (assignments, faculty_loads, snapshots)
    """
    faculty_map   = {f.id: f for f in faculty}
    faculty_loads = {f.id: 0 for f in faculty}   # always start fresh; current_load is not tracked
    assignments: Dict[str, Optional[str]] = {s.id: None for s in students}
    unassigned  = {s.id for s in students}

    step_ctr = [snapshots.last().step if snapshots.last() else 0]

    candidate_lists = build_r1_candidate_lists(students, faculty)

    # snapshot showing all candidate lists before any picks
    snapshots.append(_snap(
        step_ctr, "Round1",
        f"Round 1 begins: {len(candidate_lists)} faculties have 1st-choice applicants",
        assignments, faculty_loads, unassigned,
        r1_candidates=candidate_lists,
    ))

    for fid, ranked_students in candidate_lists.items():
        fac = faculty_map[fid]
        if not ranked_students:
            continue

        # determine pick: operator-supplied or auto (top CPI)
        if r1_picks and fid in r1_picks:
            picked_sid = r1_picks[fid]
            if picked_sid not in ranked_students:
                raise ValueError(
                    f"Round-1 pick for faculty {fid}: "
                    f"student {picked_sid} is not in their 1st-choice list"
                )
        else:
            picked_sid = ranked_students[0]   # auto: highest CPI

        assignments[picked_sid] = fid
        unassigned.discard(picked_sid)
        faculty_loads[fid] += 1

        picked_student_name = next(
            (s.name for s in students if s.id == picked_sid), picked_sid
        )
        event = (
            f"Round 1 | Faculty {fac.name} ({fid}) picks "
            f"{picked_student_name} ({picked_sid}) "
            f"[CPI={next(s.cpi for s in students if s.id==picked_sid):.2f}] "
            f"from {len(ranked_students)} applicant(s)"
        )
        snapshots.append(_snap(
            step_ctr, "Round1", event,
            assignments, faculty_loads, unassigned,
            r1_candidates=candidate_lists,
            preference_rank={picked_sid: 1},
        ))

    snapshots.append(_snap(
        step_ctr, "Round1",
        f"Round 1 complete: {len(assignments)-len(unassigned)} assigned, "
        f"{len(unassigned)} carry to main allocation",
        assignments, faculty_loads, unassigned,
    ))

    return assignments, faculty_loads, snapshots


# ---------------------------------------------------------------------------
# Main allocation — 3.3.1 + 3.3.2
# ---------------------------------------------------------------------------

def main_allocation(
    students: List[Student],
    faculty: List[Faculty],
    assignments: Dict[str, Optional[str]],
    faculty_loads: Dict[str, int],
    snapshots: SnapshotList,
    N_A: int,
    N_B: int,
    policy: str = "least_loaded",
) -> Tuple[Dict[str, Optional[str]], SnapshotList]:
    """
    Main allocation: Class A → Class B → Class C (3.3.1 + 3.3.2).

    Mutates assignments and faculty_loads in place; appends snapshots.

    Parameters
    ----------
    policy : str
        "least_loaded" (default) — assign to the least-loaded eligible
        faculty, tie-broken by preference rank.
        "nonempty" — prefer the highest-preferred empty lab among eligible
        faculty; if none are empty, assign the highest-preferred with
        remaining capacity.

    Returns (assignments, snapshots).
    """
    _POLICIES = {"least_loaded", "nonempty"}
    if policy not in _POLICIES:
        raise ValueError(f"Unknown policy {policy!r}. Choose from {_POLICIES}.")

    def _choice(student, candidates):
        if policy == "nonempty":
            return _nonempty_choice(student, candidates, faculty_map, faculty_loads)
        return _least_loaded_choice(student, candidates, faculty_map, faculty_loads)

    faculty_map  = {f.id: f for f in faculty}
    student_map  = {s.id: s for s in students}
    unassigned   = {sid for sid, fid in assignments.items() if fid is None}
    step_ctr     = [snapshots.last().step]
    all_fids     = [f.id for f in faculty]

    def _assign(sid: str, fid: str, rank: int, phase: str) -> None:
        assignments[sid] = fid
        unassigned.discard(sid)
        faculty_loads[fid] += 1
        s = student_map[sid]
        f = faculty_map[fid]
        snapshots.append(_snap(
            step_ctr, phase,
            f"{phase} | {s.name} ({sid}, Tier {s.tier}, CPI {s.cpi:.2f}) → "
            f"{f.name} ({fid}) | pref rank {rank} | load now {faculty_loads[fid]}",
            assignments, faculty_loads, unassigned,
            preference_rank={sid: rank},
        ))

    # -----------------------------------------------------------------------
    # Class A round
    # -----------------------------------------------------------------------
    class_a = _sorted_by_cpi([student_map[sid] for sid in unassigned
                               if student_map[sid].tier == "A"])
    snapshots.append(_snap(
        step_ctr, "ClassA",
        f"Class A round begins: {len(class_a)} students, cap N_A={N_A}",
        assignments, faculty_loads, unassigned,
    ))

    for s in class_a:
        cap = s.preferences[:N_A]
        result = _choice(s, cap)
        if result:
            fid, rank = result
            _assign(s.id, fid, rank, "ClassA")
        # else: no capacity within N_A → promote to Class B

    leftover_a = [sid for sid in unassigned if student_map[sid].tier == "A"]
    if leftover_a:
        snapshots.append(_snap(
            step_ctr, "ClassA",
            f"Class A round: {len(leftover_a)} student(s) promoted to Class B pool",
            assignments, faculty_loads, unassigned,
        ))

    # -----------------------------------------------------------------------
    # Class B / B1 round  (original B or B1 + promoted A)
    # -----------------------------------------------------------------------
    quartile_mode = any(student_map[sid].tier in ("B1", "B2") for sid in student_map)

    if quartile_mode:
        pool_b1_ids = {sid for sid in unassigned
                       if student_map[sid].tier in ("A", "B1")}
        pool_b1 = _sorted_by_cpi([student_map[sid] for sid in pool_b1_ids])
        orig_b1 = sum(1 for s in pool_b1 if s.tier == "B1")

        snapshots.append(_snap(
            step_ctr, "ClassB1",
            f"Class B1 round begins: {len(pool_b1)} students "
            f"({len(leftover_a)} promoted A + {orig_b1} original B1), cap N_B={N_B}",
            assignments, faculty_loads, unassigned,
        ))

        for s in pool_b1:
            cap = s.preferences[:N_B]
            result = _choice(s, cap)
            if result:
                fid, rank = result
                _assign(s.id, fid, rank, "ClassB1")

        leftover_b1 = [sid for sid in unassigned
                       if student_map[sid].tier in ("A", "B1")]
        if leftover_b1:
            snapshots.append(_snap(
                step_ctr, "ClassB1",
                f"Class B1 round: {len(leftover_b1)} student(s) promoted to Class B2 pool",
                assignments, faculty_loads, unassigned,
            ))

        # --- Class B2 round  (original B2 + promoted from B1) ---
        pool_b2_ids = {sid for sid in unassigned
                       if student_map[sid].tier in ("A", "B1", "B2")}
        pool_b2 = _sorted_by_cpi([student_map[sid] for sid in pool_b2_ids])
        orig_b2   = sum(1 for s in pool_b2 if s.tier == "B2")
        promoted  = len(pool_b2) - orig_b2

        snapshots.append(_snap(
            step_ctr, "ClassB2",
            f"Class B2 round begins: {len(pool_b2)} students "
            f"({promoted} promoted + {orig_b2} original B2), cap N_B={N_B}",
            assignments, faculty_loads, unassigned,
        ))

        for s in pool_b2:
            cap = s.preferences[:N_B]
            result = _choice(s, cap)
            if result:
                fid, rank = result
                _assign(s.id, fid, rank, "ClassB2")

        leftover_b2 = [sid for sid in unassigned
                       if student_map[sid].tier in ("A", "B1", "B2")]
        if leftover_b2:
            snapshots.append(_snap(
                step_ctr, "ClassB2",
                f"Class B2 round: {len(leftover_b2)} student(s) merged into Class C",
                assignments, faculty_loads, unassigned,
            ))

    else:
        # Percentile mode — single Class B round
        pool_b_ids = {sid for sid in unassigned
                      if student_map[sid].tier in ("A", "B")}
        pool_b = _sorted_by_cpi([student_map[sid] for sid in pool_b_ids])

        snapshots.append(_snap(
            step_ctr, "ClassB",
            f"Class B round begins: {len(pool_b)} students "
            f"({len(leftover_a)} promoted A + "
            f"{len(pool_b)-len(leftover_a)} original B), cap N_B={N_B}",
            assignments, faculty_loads, unassigned,
        ))

        for s in pool_b:
            cap = s.preferences[:N_B]
            result = _choice(s, cap)
            if result:
                fid, rank = result
                _assign(s.id, fid, rank, "ClassB")

        leftover_b = [sid for sid in unassigned
                      if student_map[sid].tier in ("A", "B")]
        if leftover_b:
            snapshots.append(_snap(
                step_ctr, "ClassB",
                f"Class B round: {len(leftover_b)} student(s) merged into Class C",
                assignments, faculty_loads, unassigned,
            ))

    # -----------------------------------------------------------------------
    # Class C round  (original C + merged A + merged B)  — global cap
    # -----------------------------------------------------------------------
    pool_c = _sorted_by_cpi([student_map[sid] for sid in unassigned])
    orig_c_count = sum(1 for s in pool_c if s.tier == "C")

    snapshots.append(_snap(
        step_ctr, "ClassC",
        f"Class C round begins: {len(pool_c)} students "
        f"({orig_c_count} original C, {len(pool_c)-orig_c_count} merged) "
        "| global cap (all faculty with capacity)",
        assignments, faculty_loads, unassigned,
    ))

    for s in pool_c:
        result = _choice(s, all_fids)
        if result:
            fid, rank = result
            _assign(s.id, fid, rank, "ClassC")

    still_unassigned = [sid for sid in assignments if assignments[sid] is None]
    snapshots.append(_snap(
        step_ctr, "Final",
        f"Allocation complete | assigned={len(assignments)-len(still_unassigned)} "
        f"| unassigned={len(still_unassigned)}",
        assignments, faculty_loads, unassigned,
    ))

    return assignments, snapshots


# ---------------------------------------------------------------------------
# CPI-Fill allocation — two-phase procedure
# ---------------------------------------------------------------------------

def cpi_fill_phase1(
    students: List[Student],
    faculty: List[Faculty],
    assignments: Dict[str, Optional[str]],
    faculty_loads: Dict[str, int],
    snapshots: SnapshotList,
) -> Tuple[Dict[str, Optional[str]], Dict[str, int], SnapshotList, dict]:
    """
    Run Phase 1 of the CPI-Fill policy.

    Processes unassigned students in descending CPI order, assigning each to
    their highest-preferred advisor with remaining capacity. Stops when
    len(unassigned) == len(empty_labs) (the stoppage condition).

    Returns
    -------
    (assignments, faculty_loads, snapshots, stats)
        stats keys: "phase1_assigned", "unassigned_count", "empty_labs_count",
                    "total_students"
    """
    faculty_map = {f.id: f for f in faculty}
    student_map = {s.id: s for s in students}
    unassigned  = {sid for sid, fid in assignments.items() if fid is None}
    empty_labs  = {fid for fid, load in faculty_loads.items() if load == 0}
    step_ctr    = [snapshots.last().step]

    U = len(unassigned)
    E = len(empty_labs)

    if U < E:
        import warnings
        warnings.warn(
            f"CPI-Fill: not enough students (U={U}) to guarantee non-empty labs "
            f"(E={E}). Proceeding with Phase 2 only.",
            stacklevel=2,
        )

    snapshots.append(_snap(
        step_ctr, "CPIFill",
        f"CPI-Fill begins | U={U} E={E} U−E={U - E}",
        assignments, faculty_loads, unassigned,
    ))

    def _phase1_choice(student: Student) -> Optional[Tuple[str, int]]:
        for rank, fid in enumerate(student.preferences, start=1):
            if fid in faculty_map and faculty_loads[fid] < faculty_map[fid].max_load:
                return fid, rank
        return None

    def _phase1_assign(s: Student) -> None:
        nonlocal phase1_assigned
        result = _phase1_choice(s)
        if result is None:
            return
        fid, rank = result
        assignments[s.id] = fid
        unassigned.discard(s.id)
        faculty_loads[fid] += 1
        if faculty_loads[fid] == 1:
            empty_labs.discard(fid)
        phase1_assigned += 1
        f = faculty_map[fid]
        snapshots.append(_snap(
            step_ctr, "Phase1",
            f"Phase 1 | {s.name} ({s.id}, CPI {s.cpi:.2f}) → "
            f"{f.name} ({fid}) | pref rank {rank} | load now {faculty_loads[fid]}",
            assignments, faculty_loads, unassigned,
            preference_rank={s.id: rank},
        ))

    phase1_assigned = 0

    if U == E:
        snapshots.append(_snap(
            step_ctr, "Phase1",
            f"Phase 1 skipped (U == E == {U}): proceeding directly to Phase 2",
            assignments, faculty_loads, unassigned,
        ))
    elif E == 0:
        for s in _sorted_by_cpi([student_map[sid] for sid in unassigned]):
            _phase1_assign(s)
        snapshots.append(_snap(
            step_ctr, "Phase1",
            f"Phase 1 complete (E=0, no stopping condition) | "
            f"assigned={phase1_assigned} | U={len(unassigned)} E={len(empty_labs)}",
            assignments, faculty_loads, unassigned,
        ))
    else:
        for s in _sorted_by_cpi([student_map[sid] for sid in unassigned]):
            if len(unassigned) == len(empty_labs):
                break
            _phase1_assign(s)
        snapshots.append(_snap(
            step_ctr, "Phase1",
            f"Phase 1 complete | assigned={phase1_assigned} | "
            f"U={len(unassigned)} E={len(empty_labs)}",
            assignments, faculty_loads, unassigned,
        ))

    stats = {
        "phase1_assigned":  phase1_assigned,
        "unassigned_count": len(unassigned),
        "empty_labs_count": len(empty_labs),
        "total_students":   len(students),
    }
    return assignments, faculty_loads, snapshots, stats


def cpi_fill_phase2(
    students: List[Student],
    faculty: List[Faculty],
    assignments: Dict[str, Optional[str]],
    faculty_loads: Dict[str, int],
    snapshots: SnapshotList,
) -> Tuple[Dict[str, Optional[str]], SnapshotList, bool]:
    """
    Run Phase 2 of the CPI-Fill policy.

    Assigns each remaining (unassigned) student to their highest-preferred
    empty lab. Appends the Final snapshot.

    Returns
    -------
    (assignments, snapshots, phase2_skipped)
        phase2_skipped is True when Phase 2 queue was empty (all students
        were already assigned after Phase 1).
    """
    faculty_map = {f.id: f for f in faculty}
    student_map = {s.id: s for s in students}
    unassigned  = {sid for sid, fid in assignments.items() if fid is None}
    empty_labs  = {fid for fid, load in faculty_loads.items() if load == 0}
    step_ctr    = [snapshots.last().step]

    phase2_queue = _sorted_by_cpi([student_map[sid] for sid in unassigned])
    snapshots.append(_snap(
        step_ctr, "Phase2",
        f"Phase 2 begins | {len(phase2_queue)} student(s) | "
        f"{len(empty_labs)} empty lab(s) to fill",
        assignments, faculty_loads, unassigned,
    ))

    for s in phase2_queue:
        result = _highest_preferred_empty(s, faculty_map, faculty_loads)
        if result is None:
            raise RuntimeError(
                f"CPI-Fill Phase 2: no empty lab found for student {s.id} ({s.name}). "
                "Protocol-state inconsistency — check that all faculty are in the "
                "student's preference list."
            )
        fid, rank = result
        assignments[s.id] = fid
        unassigned.discard(s.id)
        faculty_loads[fid] += 1
        empty_labs.discard(fid)
        f = faculty_map[fid]
        snapshots.append(_snap(
            step_ctr, "Phase2",
            f"Phase 2 | {s.name} ({s.id}, CPI {s.cpi:.2f}) → "
            f"{f.name} ({fid}) | pref rank {rank} | load now {faculty_loads[fid]}",
            assignments, faculty_loads, unassigned,
            preference_rank={s.id: rank},
        ))

    snapshots.append(_snap(
        step_ctr, "Phase2",
        f"Phase 2 complete | assigned={len(phase2_queue)} | "
        f"empty labs remaining={len(empty_labs)}",
        assignments, faculty_loads, unassigned,
    ))

    still_unassigned = [sid for sid in assignments if assignments[sid] is None]
    snapshots.append(_snap(
        step_ctr, "Final",
        f"Allocation complete | assigned={len(assignments)-len(still_unassigned)} "
        f"| unassigned={len(still_unassigned)}",
        assignments, faculty_loads, unassigned,
    ))

    phase2_skipped = len(phase2_queue) == 0
    return assignments, snapshots, phase2_skipped


def cpi_fill_allocation(
    students: List[Student],
    faculty: List[Faculty],
    assignments: Dict[str, Optional[str]],
    faculty_loads: Dict[str, int],
    snapshots: SnapshotList,
) -> Tuple[Dict[str, Optional[str]], SnapshotList, bool]:
    """
    CPI-Fill policy: convenience wrapper that runs Phase 1 then Phase 2.

    Returns (assignments, snapshots, phase2_skipped).
    """
    assignments, faculty_loads, snapshots, _ = cpi_fill_phase1(
        students, faculty, assignments, faculty_loads, snapshots,
    )
    return cpi_fill_phase2(
        students, faculty, assignments, faculty_loads, snapshots,
    )


# ---------------------------------------------------------------------------
# CPI-tiered preference rounds — resumable engine
# ---------------------------------------------------------------------------

def _tr_append_complete_snapshot(
    snapshots: SnapshotList,
    assignments: Dict[str, Optional[str]],
    faculty_loads: Dict[str, int],
) -> None:
    assigned = sum(1 for v in assignments.values() if v is not None)
    unassigned = sum(1 for v in assignments.values() if v is None)
    step = snapshots.last().step if snapshots.last() else 0
    snapshots.append(AllocationSnapshot(
        step=step + 1,
        phase="Final",
        event=(
            f"Allocation complete | assigned={assigned} | unassigned={unassigned}"
        ),
        assignments=copy.copy(assignments),
        faculty_loads=copy.copy(faculty_loads),
        unassigned={sid for sid, fid in assignments.items() if fid is None},
    ))


def _tr_append_stall_snapshot(
    snapshots: SnapshotList,
    assignments: Dict[str, Optional[str]],
    faculty_loads: Dict[str, int],
    reason: str,
) -> None:
    unassigned = {sid for sid, fid in assignments.items() if fid is None}
    step = snapshots.last().step if snapshots.last() else 0
    snapshots.append(AllocationSnapshot(
        step=step + 1,
        phase="Stall",
        event=f"STALL — {reason} | {len(unassigned)} student(s) unassigned",
        assignments=copy.copy(assignments),
        faculty_loads=copy.copy(faculty_loads),
        unassigned=unassigned,
    ))


def _tr_execute_round(state: TieredRoundsState) -> TieredRoundsState:
    """Execute one preference round. Returns an updated TieredRoundsState."""
    from collections import defaultdict

    round_no = state.round_no
    n = round_no - 1          # 0-indexed position in each preference list

    student_map = {s.id: s for s in state.students}
    faculty_map = {f.id: f for f in state.faculty}
    assignments = state.assignments      # mutated in-place
    faculty_loads = state.faculty_loads  # mutated in-place
    saturated = state.saturated_advisors

    unassigned: List[str] = [sid for sid, fid in assignments.items() if fid is None]

    # --- Group unassigned students by their n-th preference ---
    groups: Dict[str, List[Student]] = defaultdict(list)
    students_no_pref: List[str] = []
    targeted_saturated: Set[str] = set()

    for sid in unassigned:
        s = student_map[sid]
        if n >= len(s.preferences):
            students_no_pref.append(sid)
        else:
            fid = s.preferences[n]
            if fid in saturated:
                targeted_saturated.add(fid)
            else:
                groups[fid].append(s)

    # --- Classify each advisor group as an immediate pick or a tie ---
    immediate_picks: Dict[str, str] = {}   # advisor_id -> chosen student_id
    ties: List[PendingTie] = []

    for fid, candidates in groups.items():
        if not candidates:
            continue
        candidates_sorted = sorted(candidates, key=lambda s: (-s.cpi, s.id))
        top_cpi = candidates_sorted[0].cpi
        tied_students = [s for s in candidates_sorted if s.cpi == top_cpi]
        fac = faculty_map[fid]

        if len(tied_students) == 1:
            immediate_picks[fid] = candidates_sorted[0].id
        else:
            reason = (
                f"Round {round_no}: CPI tie at {top_cpi:.2f} for advisor "
                f"{fac.name} — tied candidates: "
                f"{', '.join(s.name for s in tied_students)}"
            )
            ties.append(PendingTie(
                round_no=round_no,
                advisor_id=fid,
                advisor_name=fac.name,
                candidate_ids=[s.id for s in candidates_sorted],
                candidate_names={s.id: s.name for s in candidates_sorted},
                candidate_cpis={s.id: s.cpi for s in candidates_sorted},
                tied_ids=[s.id for s in tied_students],
                tied_cpi=top_cpi,
                reason=reason,
            ))

    # Ties serialised by decreasing tied CPI (decision A2)
    ties.sort(key=lambda t: -t.tied_cpi)

    # --- Apply immediate picks ---
    newly_saturated: Set[str] = set()
    assigned_this_round: Dict[str, str] = {}
    step = state.snapshots.last().step if state.snapshots.last() else 0

    for fid, sid in immediate_picks.items():
        s = student_map[sid]
        f = faculty_map[fid]
        rank = s.preferences.index(fid) + 1
        assignments[sid] = fid
        faculty_loads[fid] += 1
        assigned_this_round[sid] = fid
        if faculty_loads[fid] >= f.max_load:
            newly_saturated.add(fid)
        step += 1
        state.snapshots.append(AllocationSnapshot(
            step=step,
            phase=f"PrefRound{round_no}",
            event=(
                f"Round {round_no} | {s.name} ({sid}, CPI {s.cpi:.2f}) → "
                f"{f.name} ({fid}) | pref rank {rank} | "
                f"load now {faculty_loads[fid]}"
            ),
            assignments=copy.copy(assignments),
            faculty_loads=copy.copy(faculty_loads),
            unassigned={sid for sid, fid in assignments.items() if fid is None},
            preference_rank={sid: rank},
        ))

    # --- Round summary snapshot ---
    unassigned_now: Set[str] = {sid for sid, fid in assignments.items() if fid is None}
    step += 1
    state.snapshots.append(AllocationSnapshot(
        step=step,
        phase=f"PrefRound{round_no}",
        event=(
            f"Round {round_no} summary | assigned={len(assigned_this_round)}"
            + (f" | {len(ties)} tie(s) pending" if ties else "")
            + f" | {len(unassigned_now)} remaining"
        ),
        assignments=copy.copy(assignments),
        faculty_loads=copy.copy(faculty_loads),
        unassigned=copy.copy(unassigned_now),
    ))

    # --- Trace record ---
    trace_entry: Dict[str, Any] = {
        "round_no": round_no,
        "active_student_ids": [
            sid for sid in unassigned if sid not in students_no_pref
        ],
        "student_active_preferences": {
            sid: student_map[sid].preferences[n]
            for sid in unassigned
            if n < len(student_map[sid].preferences)
        },
        "skipped_advisor_ids": list(targeted_saturated),
        "candidate_pools": {
            fid: [s.id for s in cands]
            for fid, cands in groups.items()
        },
        "unambiguous_picks": dict(immediate_picks),
        "ties": [
            {
                "advisor_id": t.advisor_id,
                "advisor_name": t.advisor_name,
                "tied_ids": list(t.tied_ids),
                "tied_cpi": t.tied_cpi,
            }
            for t in ties
        ],
        "manual_decisions": [],
        "assigned_this_round": dict(assigned_this_round),
        "forwarded_to_next_round": list(unassigned_now),
        "advisor_loads_after": dict(faculty_loads),
        "newly_saturated": list(newly_saturated),
    }
    new_trace = state.trace_log + [trace_entry]
    new_saturated = saturated | newly_saturated

    # --- Determine outcome ---
    if not unassigned_now:
        _tr_append_complete_snapshot(state.snapshots, assignments, faculty_loads)
        return TieredRoundsState(
            round_no=round_no, students=state.students, faculty=state.faculty,
            assignments=assignments, faculty_loads=faculty_loads,
            snapshots=state.snapshots, saturated_advisors=new_saturated,
            pending_tie=None, pending_tie_queue=[],
            trace_log=new_trace, status="complete", stall_unassigned=[],
        )

    if ties:
        return TieredRoundsState(
            round_no=round_no, students=state.students, faculty=state.faculty,
            assignments=assignments, faculty_loads=faculty_loads,
            snapshots=state.snapshots, saturated_advisors=new_saturated,
            pending_tie=ties[0], pending_tie_queue=ties[1:],
            trace_log=new_trace, status="awaiting_tie", stall_unassigned=[],
        )

    if not groups and students_no_pref:
        # Some students exhausted their preference list — defensive stall
        reason = (
            f"students with exhausted preference lists: "
            f"{', '.join(students_no_pref)}"
        )
        _tr_append_stall_snapshot(state.snapshots, assignments, faculty_loads, reason)
        return TieredRoundsState(
            round_no=round_no, students=state.students, faculty=state.faculty,
            assignments=assignments, faculty_loads=faculty_loads,
            snapshots=state.snapshots, saturated_advisors=new_saturated,
            pending_tie=None, pending_tie_queue=[],
            trace_log=new_trace, status="stalled",
            stall_unassigned=list(unassigned_now),
        )

    # Normal case: some picks made (or all n-th prefs were saturated);
    # advance to the next round.
    return TieredRoundsState(
        round_no=round_no + 1, students=state.students, faculty=state.faculty,
        assignments=assignments, faculty_loads=faculty_loads,
        snapshots=state.snapshots, saturated_advisors=new_saturated,
        pending_tie=None, pending_tie_queue=[],
        trace_log=new_trace, status="running", stall_unassigned=[],
    )


def _tr_run_to_pause(state: TieredRoundsState) -> TieredRoundsState:
    """Loop _tr_execute_round until a tie, completion, or stall."""
    F = len(state.faculty)
    while state.status == "running":
        if state.round_no > F:
            # All preference positions exhausted — genuine stall
            stall_ids = [sid for sid, fid in state.assignments.items() if fid is None]
            _tr_append_stall_snapshot(
                state.snapshots, state.assignments, state.faculty_loads,
                f"all {F} preference positions exhausted with "
                f"{len(stall_ids)} student(s) still unassigned",
            )
            from dataclasses import replace as _dc_replace
            return _dc_replace(state, status="stalled", stall_unassigned=stall_ids)
        state = _tr_execute_round(state)
    return state


def tiered_rounds_start(
    students: List[Student],
    faculty: List[Faculty],
    snapshots: SnapshotList,
) -> TieredRoundsState:
    """
    Initialise and start the CPI-tiered preference rounds engine after Phase 0.

    Phase 0 must have already been run (student.tier and student.n_tier set).
    The engine runs autonomously until it needs a manual tie-break or finishes.

    Parameters
    ----------
    students  : students list with .tier set by phase0()
    faculty   : faculty list with .max_load set by phase0()
    snapshots : SnapshotList already containing the Phase-0 snapshot

    Returns
    -------
    TieredRoundsState with status in {"awaiting_tie", "complete", "stalled"}
    """
    faculty_ids = {f.id for f in faculty}
    faculty_map = {f.id: f for f in faculty}

    # Defensive validation
    for s in students:
        if not s.preferences:
            raise ValueError(
                f"Student {s.id} ({s.name!r}) has an empty preference list. "
                "All students must list every available faculty member."
            )
        unknown = [fid for fid in s.preferences if fid not in faculty_ids]
        if unknown:
            raise ValueError(
                f"Student {s.id} ({s.name!r}) references unknown faculty IDs: "
                f"{unknown}. Preference sheet may be malformed."
            )

    total_cap = sum(f.max_load for f in faculty)
    if total_cap < len(students):
        raise ValueError(
            f"Total faculty capacity ({total_cap}) is less than the number "
            f"of students ({len(students)}). Cannot assign all students."
        )

    assignments: Dict[str, Optional[str]] = {s.id: None for s in students}
    faculty_loads: Dict[str, int] = {f.id: 0 for f in faculty}

    step = snapshots.last().step if snapshots.last() else 0
    snapshots.append(AllocationSnapshot(
        step=step + 1,
        phase="PrefRounds",
        event=(
            f"CPI-tiered preference rounds begin | "
            f"{len(students)} students | {len(faculty)} advisors"
        ),
        assignments=copy.copy(assignments),
        faculty_loads=copy.copy(faculty_loads),
        unassigned=set(assignments.keys()),
    ))

    initial = TieredRoundsState(
        round_no=1,
        students=_sorted_by_cpi(students),
        faculty=faculty,
        assignments=assignments,
        faculty_loads=faculty_loads,
        snapshots=snapshots,
        saturated_advisors=set(),
        pending_tie=None,
        pending_tie_queue=[],
        trace_log=[],
        status="running",
        stall_unassigned=[],
    )
    return _tr_run_to_pause(initial)


def tiered_rounds_resume(
    state: TieredRoundsState,
    chosen_student_id: str,
) -> TieredRoundsState:
    """
    Resolve the current pending tie by allocating chosen_student_id to the
    pending advisor, then continue running until the next tie or completion.

    Parameters
    ----------
    state              : TieredRoundsState with status == "awaiting_tie"
    chosen_student_id  : must be in state.pending_tie.tied_ids

    Returns
    -------
    Updated TieredRoundsState with status in {"awaiting_tie", "complete", "stalled"}
    """
    if state.status != "awaiting_tie":
        raise ValueError(
            f"Cannot resume: engine is not awaiting a tie decision "
            f"(status={state.status!r})."
        )
    tie = state.pending_tie
    if tie is None:
        raise ValueError("pending_tie is None despite status='awaiting_tie'.")
    if chosen_student_id not in tie.tied_ids:
        raise ValueError(
            f"Chosen student {chosen_student_id!r} is not in the tied set "
            f"{tie.tied_ids!r} for advisor {tie.advisor_id!r}."
        )

    student_map = {s.id: s for s in state.students}
    faculty_map = {f.id: f for f in state.faculty}
    s = student_map[chosen_student_id]
    f = faculty_map[tie.advisor_id]
    rank = s.preferences.index(tie.advisor_id) + 1

    assignments = state.assignments
    faculty_loads = state.faculty_loads
    assignments[chosen_student_id] = tie.advisor_id
    faculty_loads[tie.advisor_id] += 1

    newly_saturated: Set[str] = set()
    if faculty_loads[tie.advisor_id] >= f.max_load:
        newly_saturated.add(tie.advisor_id)
    new_saturated = state.saturated_advisors | newly_saturated

    step = state.snapshots.last().step if state.snapshots.last() else 0
    state.snapshots.append(AllocationSnapshot(
        step=step + 1,
        phase=f"PrefRound{tie.round_no}",
        event=(
            f"Round {tie.round_no} | TIE RESOLVED | "
            f"{s.name} ({s.id}, CPI {s.cpi:.2f}) → "
            f"{f.name} ({tie.advisor_id}) | pref rank {rank} | "
            f"load now {faculty_loads[tie.advisor_id]}"
        ),
        assignments=copy.copy(assignments),
        faculty_loads=copy.copy(faculty_loads),
        unassigned={sid for sid, fid in assignments.items() if fid is None},
        preference_rank={chosen_student_id: rank},
    ))

    # Update trace: append decision to the current round's record
    new_trace = [dict(e) for e in state.trace_log]
    if new_trace and new_trace[-1]["round_no"] == tie.round_no:
        new_trace[-1] = dict(new_trace[-1])
        new_trace[-1]["manual_decisions"] = list(
            new_trace[-1]["manual_decisions"]
        ) + [{
            "advisor_id": tie.advisor_id,
            "advisor_name": tie.advisor_name,
            "chosen_student_id": chosen_student_id,
            "tied_ids": list(tie.tied_ids),
            "tied_cpi": tie.tied_cpi,
        }]

    unassigned_now = {sid for sid, fid in assignments.items() if fid is None}

    if not unassigned_now:
        _tr_append_complete_snapshot(state.snapshots, assignments, faculty_loads)
        return TieredRoundsState(
            round_no=tie.round_no, students=state.students, faculty=state.faculty,
            assignments=assignments, faculty_loads=faculty_loads,
            snapshots=state.snapshots, saturated_advisors=new_saturated,
            pending_tie=None, pending_tie_queue=[],
            trace_log=new_trace, status="complete", stall_unassigned=[],
        )

    # More ties in the same round — serve the next one
    if state.pending_tie_queue:
        next_tie = state.pending_tie_queue[0]
        return TieredRoundsState(
            round_no=tie.round_no, students=state.students, faculty=state.faculty,
            assignments=assignments, faculty_loads=faculty_loads,
            snapshots=state.snapshots, saturated_advisors=new_saturated,
            pending_tie=next_tie, pending_tie_queue=state.pending_tie_queue[1:],
            trace_log=new_trace, status="awaiting_tie", stall_unassigned=[],
        )

    # All ties in this round resolved — advance to the next round
    next_state = TieredRoundsState(
        round_no=tie.round_no + 1, students=state.students, faculty=state.faculty,
        assignments=assignments, faculty_loads=faculty_loads,
        snapshots=state.snapshots, saturated_advisors=new_saturated,
        pending_tie=None, pending_tie_queue=[],
        trace_log=new_trace, status="running", stall_unassigned=[],
    )
    return _tr_run_to_pause(next_state)


# ---------------------------------------------------------------------------
# Convenience: run full allocation in one call
# ---------------------------------------------------------------------------

def run_full_allocation(
    students: List[Student],
    faculty: List[Faculty],
    r1_picks: Optional[Dict[str, str]] = None,
    out_dir: Optional[str] = None,
    policy: str = "least_loaded",
) -> Tuple[Dict[str, Optional[str]], SnapshotList, dict, dict]:
    """
    Run Phase 0 → (Round 1 →) Main allocation end-to-end.

    Round 1 is skipped when policy="cpi_fill"; it runs for all other policies.

    Parameters
    ----------
    students  : raw Student list (tier/n_tier not yet set)
    faculty   : raw Faculty list (max_load=-1 where not specified)
    r1_picks  : optional Round-1 picks dict (see round1()); ignored for cpi_fill
    out_dir   : if provided, Phase-0 report CSVs are written here
    policy    : assignment policy.
                "least_loaded" (default) — Phase 0 → Round 1 → assign to the
                least-loaded eligible faculty, tie-broken by preference rank.
                "nonempty" — Phase 0 → Round 1 → prefer the highest-preferred
                empty lab; fall back to highest-preferred with remaining capacity.
                "cpi_fill" — Phase 0 → Phase 1 (CPI order, highest-preferred
                with capacity, stopping condition) → Phase 2 (highest-preferred
                empty lab). Round 1 is not run.

    Returns
    -------
    (assignments, snapshots, meta, metrics)
        assignments : {student_id: faculty_id | None}
        snapshots   : SnapshotList of all allocation steps
        meta        : cohort-level parameters dict from Phase 0
        metrics     : satisfaction metrics dict from compute_metrics
                      (keys: "npss", "overflow_count", "mean_psi",
                       "per_tier", "per_student")
    """
    _POLICIES = {"least_loaded", "nonempty", "cpi_fill", "tiered_rounds", "adaptive_ll"}
    if policy not in _POLICIES:
        raise ValueError(f"Unknown policy {policy!r}. Choose from {_POLICIES}.")
    if policy == "tiered_rounds":
        raise NotImplementedError(
            "The 'tiered_rounds' policy requires interactive tie-breaking and "
            "cannot be run via run_full_allocation(). Use the Dash UI or call "
            "tiered_rounds_start() / tiered_rounds_resume() directly."
        )

    students, faculty, meta, snaps = phase0(
        students, faculty, out_dir=out_dir, optimize=(policy == "adaptive_ll")
    )
    N_A = meta["N_A"]
    N_B = meta["N_B"]
    if policy == "cpi_fill":
        # Round 1 is skipped — CPI-Fill goes directly Phase 0 → Phase 1 → Phase 2.
        assignments   = {s.id: None for s in students}
        faculty_loads = {f.id: 0    for f in faculty}
        assignments, snaps, _ = cpi_fill_allocation(
            students, faculty, assignments, faculty_loads, snaps,
        )
    else:
        assignments, faculty_loads, snaps = round1(students, faculty, snaps, r1_picks)
        # adaptive_ll uses the same LL assignment rule with optimized caps
        main_policy = "least_loaded" if policy == "adaptive_ll" else policy
        assignments, snaps = main_allocation(
            students, faculty, assignments, faculty_loads, snaps, N_A, N_B,
            policy=main_policy,
        )
    metrics = compute_metrics(
        students, assignments,
        F=len(faculty),
        faculty_ids=[f.id for f in faculty],
        faculty=faculty,
    )
    return assignments, snaps, meta, metrics


# ---------------------------------------------------------------------------
# CLI entry-point (python -m allocator.allocation ...)
# ---------------------------------------------------------------------------

def _cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="MS Thesis Advisor Allocation Engine",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--students",     required=True,  help="Path to students CSV/Excel")
    parser.add_argument("--faculty",      required=True,  help="Path to faculty CSV/Excel")
    parser.add_argument("--out",          default="reports", help="Output directory for reports")
    parser.add_argument(
        "--phase0-only",
        action="store_true",
        help=(
            "Run Phase 0 only: compute tiers, write phase0_report.csv and\n"
            "phase0_meta.csv to --out, then exit without running allocation."
        ),
    )
    parser.add_argument(
        "--policy",
        default="least_loaded",
        choices=["least_loaded", "nonempty", "cpi_fill"],
        help=(
            "Assignment policy for the main allocation round.\n"
            "  least_loaded : assign to the least-loaded eligible faculty,\n"
            "                 tie-broken by preference rank (default).\n"
            "  nonempty     : prefer the highest-preferred empty lab;\n"
            "                 if none are empty, assign the highest-preferred\n"
            "                 faculty with remaining capacity.\n"
            "  cpi_fill     : two-phase procedure — Phase 1 processes students\n"
            "                 in CPI order (N_tier cap) until unassigned count\n"
            "                 equals empty-lab count; Phase 2 assigns each\n"
            "                 remaining student to their highest-preferred\n"
            "                 empty lab (full preference list, no cap)."
        ),
    )
    parser.add_argument(
        "--from-report",
        metavar="REPORT_DIR",
        default=None,
        help=(
            "Skip Phase 0 and load tier assignments from an existing\n"
            "phase0_report.csv + phase0_meta.csv in REPORT_DIR.\n"
            "Still requires --faculty for capacity data."
        ),
    )

    args = parser.parse_args()

    from .data_loader import (
        load_faculty,
        load_phase0_report,
        load_students,
        validate_preferences,
    )

    faculty = load_faculty(args.faculty)

    if args.from_report:
        from pathlib import Path
        rdir = Path(args.from_report)
        students, meta = load_phase0_report(
            rdir / "phase0_report.csv",
            rdir / "phase0_meta.csv",
        )
        print(f"Loaded Phase-0 report from {args.from_report}")
        print(f"  Cohort: {meta['cohort_size']} students | "
              f"Faculty: {meta['faculty_count']} | "
              f"N_A={meta['N_A']} N_B={meta['N_B']}")
    else:
        students = load_students(args.students)
        validate_preferences(students, faculty)

        if args.phase0_only:
            from pathlib import Path
            students, faculty, meta, _ = phase0(
                students, faculty, out_dir=args.out
            )
            print(f"\nPhase-0 report written to: {args.out}/")
            print(f"  Cohort: {meta['cohort_size']} students | "
                  f"Faculty: {meta['faculty_count']} | "
                  f"Mode: {meta['mode']}")
            print(f"  p{meta['p_low_pct']}={meta['p_low']}  p{meta['p_high_pct']}={meta['p_high']}  grace=±{meta['grace']}")
            print(f"  N_A={meta['N_A']}  N_B={meta['N_B']}  "
                  f"max_load(formula)={meta['common_max_load']}")
            counts = {}
            for s in students:
                counts[s.tier] = counts.get(s.tier, 0) + 1
            for tier in ("A", "B", "C"):
                print(f"  Class {tier}: {counts.get(tier, 0)} students")
            return

    # full allocation
    assignments, snaps, meta, metrics = run_full_allocation(
        students, faculty, policy=args.policy
    )
    final = snaps.last()
    assigned = sum(1 for v in final.assignments.values() if v is not None)
    print(f"\nAllocation complete: {assigned}/{len(students)} assigned")
    print(f"Total steps recorded: {len(snaps)}")

    # ---- Satisfaction Metrics ----
    npss          = metrics["npss"]
    mean_psi      = metrics["mean_psi"]
    overflow_count = metrics["overflow_count"]
    per_tier      = metrics["per_tier"]
    per_student   = metrics["per_student"]
    advisor       = metrics.get("advisor", {})

    print("\nSatisfaction Metrics Report")
    print("===========================")

    print("\n-- Student Satisfaction --")
    print(f"NPSS (primary)      : {npss:.4f}   [CPI-weighted, tier-aware]")
    print(f"Mean PSI (secondary): {mean_psi:.4f}   [equal-weighted, global rank]")
    print(f"Overflow count      : {overflow_count}")
    print()
    print("Per-tier breakdown:")
    for tier in ("A", "B", "B1", "B2", "C"):
        td = per_tier.get(tier, {})
        count = td.get("count", 0)
        if count == 0:
            continue
        rate       = td.get("within_window_rate", 0.0) * 100
        mean_rank  = td.get("mean_rank")
        npss_score = td.get("mean_npss_score", 0.0)
        psi_score  = td.get("mean_psi_score", 0.0)
        rank_str   = f"{mean_rank:.1f}" if mean_rank is not None else "N/A"
        print(
            f"  Class {tier:<3} | within-window: {rate:6.1f}% | "
            f"mean rank: {rank_str:>4} | NPSS: {npss_score:.4f} | "
            f"PSI: {psi_score:.4f} | n={count}"
        )

    if advisor:
        qmode          = advisor.get("quartile_mode", False)
        tier_map_note  = "A=1,B1=2,B2=3,C=4" if qmode else "A=1,B=2,C=3"
        mean_bt        = advisor.get("mean_best_tier", 0.0)
        worst_bt       = advisor.get("worst_best_tier", 0)
        frac_a         = advisor.get("fraction_with_A", 0.0)
        adv_a          = advisor.get("advisors_with_A", 0)
        total_adv      = advisor.get("total_advisors", 0)
        adv_assigned   = advisor.get("advisors_assigned", 0)
        print()
        print("-- Advisor Satisfaction --")
        print(f"Tier mapping        : {tier_map_note}")
        print(f"Mean best-tier      : {mean_bt:.4f}   [lower = better; avg over {adv_assigned} advisors with ≥1 student]")
        print(f"Worst best-tier     : {worst_bt}        [highest value across advisors with ≥1 student]")
        print(f"Fraction with ≥1 A  : {frac_a:.4f}   [{adv_a}/{total_adv} advisors]")

    # ---- Write metrics_report.csv ----
    import csv
    import os
    student_map = {s.id: s for s in students}
    out_dir_path = args.out
    os.makedirs(out_dir_path, exist_ok=True)
    report_path = os.path.join(out_dir_path, "metrics_report.csv")
    with open(report_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "student_id", "name", "tier", "n_tier",
            "assigned_rank", "within_window",
            "npss_score", "cpi_weight", "psi_score",
        ])
        for sid, sd in per_student.items():
            s = student_map.get(sid)
            name      = s.name if s else ""
            tier      = sd["tier"]
            n_tier    = sd["n_tier"]
            rank      = sd["assigned_rank"]
            prefs_len = len(s.preferences) if s else 0
            n_eff     = n_tier if n_tier is not None else prefs_len
            within    = 1 if (rank is not None and n_eff > 0 and rank <= n_eff) else 0
            writer.writerow([
                sid, name, tier, n_tier if n_tier is not None else "",
                rank if rank is not None else "",
                within,
                f"{sd['npss_score']:.6f}",
                f"{sd['cpi_weight']:.6f}",
                f"{sd['psi_score']:.6f}",
            ])
    print(f"\nMetrics report written to: {report_path}")


if __name__ == "__main__":
    _cli()
