"""
metrics.py — Student satisfaction metrics for MS Thesis Advisor Allocation.

Primary metric   — NPSS (Normalized Preference Satisfaction Score):
    CPI-weighted, tier-aware, window-enforcing.

Secondary metric — PSI (Preference Satisfaction Index):
    Global rank score, equal-weighted, policy-agnostic.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from .state import Student


# ---------------------------------------------------------------------------
# Step 1: collect preference ranks from final assignments
# ---------------------------------------------------------------------------

def collect_preference_ranks(
    students: List[Student],
    assignments: Dict[str, Optional[str]],
) -> Dict[str, Optional[int]]:
    """
    For each student, compute the 1-based rank of their assigned faculty
    within their preference list.

    Returns
    -------
    {student_id: rank_or_None}
        rank_or_None is None if the student is unassigned or (defensive
        fallback) if the assigned faculty is not in their preference list.
    """
    ranks: Dict[str, Optional[int]] = {}
    for s in students:
        assigned_fid = assignments.get(s.id)
        if assigned_fid is None:
            ranks[s.id] = None
        else:
            try:
                ranks[s.id] = s.preferences.index(assigned_fid) + 1
            except ValueError:
                # Defensive fallback: assigned faculty not in preference list
                ranks[s.id] = None
    return ranks


# ---------------------------------------------------------------------------
# Per-student scoring functions
# ---------------------------------------------------------------------------

def npss_per_student_score(
    student: Student,
    rank: Optional[int],
) -> float:
    """
    Compute NPSS score for a single student.

    Score is (n - rank + 1) / n if assigned within their protection window,
    0.0 otherwise.

    Parameters
    ----------
    student : Student with .n_tier and .preferences set
    rank    : 1-based preference rank, or None if unassigned
    """
    if rank is None:
        return 0.0

    # Determine effective window size n
    if student.n_tier is not None:
        n = student.n_tier
    else:
        # Class C: use full preference list length
        n = len(student.preferences)

    if n == 0:
        return 0.0

    if rank > n:
        # Outside protection window
        return 0.0

    return (n - rank + 1) / n


def psi_per_student_score(
    rank: Optional[int],
    F: int,
) -> float:
    """
    Compute PSI score for a single student.

    PSI = 1 - (rank - 1) / (F - 1), scaled so rank 1 → 1.0, rank F → 0.0.
    PSI is policy-agnostic: no tier window is applied.

    Parameters
    ----------
    rank : 1-based preference rank, or None if unassigned
    F    : total number of faculty (denominator)
    """
    if rank is None:
        return 0.0
    if F <= 1:
        return 1.0
    return 1.0 - (rank - 1) / (F - 1)


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

_TIER_LABELS = ["A", "B", "B1", "B2", "C"]

# Tier → numeric value for advisor-satisfaction computation.
# Percentile mode uses A/B/C; quartile mode uses A/B1/B2/C.
_PERCENTILE_TIER_VALUE: Dict[str, int] = {"A": 1, "B": 2, "C": 3}
_QUARTILE_TIER_VALUE:   Dict[str, int] = {"A": 1, "B1": 2, "B2": 3, "C": 4}


def _build_per_tier(
    students: List[Student],
    ranks: Dict[str, Optional[int]],
    F: int,
) -> Dict[str, dict]:
    """
    Build shared per-tier breakdown dict used by both compute_npss and compute_psi.

    Returns
    -------
    {tier: {count, within_window_rate, mean_npss_score, mean_rank, overflow_count, mean_psi_score}}
    """
    tier_data: Dict[str, dict] = {
        t: {
            "count": 0,
            "within_window": 0,
            "npss_scores": [],
            "psi_scores": [],
            "ranks": [],
            "overflow": 0,
        }
        for t in _TIER_LABELS
    }

    for s in students:
        tier = s.tier or "C"
        if tier not in tier_data:
            tier_data[tier] = {
                "count": 0,
                "within_window": 0,
                "npss_scores": [],
                "psi_scores": [],
                "ranks": [],
                "overflow": 0,
            }
        d = tier_data[tier]
        rank = ranks.get(s.id)

        d["count"] += 1

        # NPSS score
        npss_score = npss_per_student_score(s, rank)
        d["npss_scores"].append(npss_score)

        # PSI score
        psi_score = psi_per_student_score(rank, F)
        d["psi_scores"].append(psi_score)

        # Mean rank (only assigned students)
        if rank is not None:
            d["ranks"].append(rank)

        # Within-window check (NPSS definition)
        if s.n_tier is not None:
            n = s.n_tier
        else:
            n = len(s.preferences)

        if rank is not None and n > 0 and rank <= n:
            d["within_window"] += 1
        else:
            d["overflow"] += 1

    # Convert to summary dicts
    result: Dict[str, dict] = {}
    for t in _TIER_LABELS:
        d = tier_data[t]
        count = d["count"]
        if count == 0:
            result[t] = {
                "count": 0,
                "mean_rank": None,
                "within_window_rate": 0.0,
                "mean_npss_score": 0.0,
                "mean_psi_score": 0.0,
                "overflow_count": 0,
            }
        else:
            mean_rank = (sum(d["ranks"]) / len(d["ranks"])) if d["ranks"] else None
            within_rate = d["within_window"] / count
            mean_npss = sum(d["npss_scores"]) / count
            mean_psi  = sum(d["psi_scores"])  / count
            result[t] = {
                "count": count,
                "mean_rank": mean_rank,
                "within_window_rate": within_rate,
                "mean_npss_score": mean_npss,
                "mean_psi_score": mean_psi,
                "overflow_count": d["overflow"],
            }

    return result


def compute_npss(
    students: List[Student],
    ranks: Dict[str, Optional[int]],
) -> dict:
    """
    Compute the NPSS (primary metric).

    NPSS = sum(w_i * score_i) where w_i = CPI_i / sum(CPI).

    Returns
    -------
    {
        "npss": float,
        "overflow_count": int,
        "per_tier": {tier: {...}},
        "per_student_npss": {student_id: float},
        "weights": {student_id: float},
    }
    """
    total_cpi = sum(s.cpi for s in students)
    if total_cpi == 0.0:
        # Guard against zero CPI: use equal weights
        total_cpi = len(students) if students else 1.0
        weights = {s.id: 1.0 / len(students) for s in students} if students else {}
    else:
        weights = {s.id: s.cpi / total_cpi for s in students}

    per_student_npss: Dict[str, float] = {}
    npss = 0.0
    for s in students:
        score = npss_per_student_score(s, ranks.get(s.id))
        per_student_npss[s.id] = score
        npss += weights[s.id] * score

    # Total overflow count across all tiers
    overflow_count = sum(
        1 for s in students
        if (lambda r, n: r is None or (n > 0 and r > n))(
            ranks.get(s.id),
            s.n_tier if s.n_tier is not None else len(s.preferences),
        )
    )

    return {
        "npss": npss,
        "overflow_count": overflow_count,
        "per_student_npss": per_student_npss,
        "weights": weights,
    }


def compute_psi(
    students: List[Student],
    ranks: Dict[str, Optional[int]],
    F: int,
) -> dict:
    """
    Compute the PSI (secondary metric).

    mean_psi = mean(psi_per_student_score(rank, F)) across all students.

    Returns
    -------
    {
        "mean_psi": float,
        "per_student_psi": {student_id: float},
    }
    """
    if not students:
        return {"mean_psi": 0.0, "per_student_psi": {}}

    per_student_psi: Dict[str, float] = {}
    total_psi = 0.0
    for s in students:
        score = psi_per_student_score(ranks.get(s.id), F)
        per_student_psi[s.id] = score
        total_psi += score

    mean_psi = total_psi / len(students)

    return {
        "mean_psi": mean_psi,
        "per_student_psi": per_student_psi,
    }


# ---------------------------------------------------------------------------
# Advisor satisfaction metrics
# ---------------------------------------------------------------------------

def compute_advisor_metrics(
    students: List[Student],
    assignments: Dict[str, Optional[str]],
    all_faculty_ids: Optional[List[str]] = None,
) -> dict:
    """
    Compute advisor-satisfaction metrics for a completed allocation.

    For each advisor, the "best tier" is the tier of the strongest student
    assigned to them, using the mapping:
      - Percentile mode (tiers A / B / C):   A=1, B=2, C=3
      - Quartile mode  (tiers A / B1 / B2 / C): A=1, B1=2, B2=3, C=4

    Mode is inferred from the student tiers present (quartile mode if any
    student has tier B1 or B2).

    Parameters
    ----------
    students        : list of Student (with .tier set)
    assignments     : {student_id: faculty_id | None}
    all_faculty_ids : full list of faculty IDs (for fraction denominator).
                      If omitted, the denominator is the number of advisors
                      who received at least one student.

    Returns
    -------
    {
        "mean_best_tier"     : float  — mean of best-tier values (advisors with ≥1 student)
        "worst_best_tier"    : int    — highest (worst) best-tier value across those advisors
        "fraction_with_A"    : float  — fraction of ALL advisors with ≥1 A-tier student
        "advisors_with_A"    : int    — count of advisors with ≥1 A-tier student
        "total_advisors"     : int    — denominator for fraction_with_A
        "advisors_assigned"  : int    — advisors who received ≥1 student
        "quartile_mode"      : bool   — True if quartile tier mapping was used
        "per_faculty"        : {faculty_id: {"best_tier_value": int, "best_tier_label": str}}
    }
    """
    # Detect mode from student tiers
    quartile_mode = any(
        s.tier in ("B1", "B2") for s in students if s.tier is not None
    )
    tier_value = _QUARTILE_TIER_VALUE if quartile_mode else _PERCENTILE_TIER_VALUE

    # Group students by assigned faculty
    faculty_students: Dict[str, List[Student]] = {}
    student_map = {s.id: s for s in students}
    for sid, fid in assignments.items():
        if fid is None:
            continue
        s = student_map.get(sid)
        if s is None:
            continue
        faculty_students.setdefault(fid, []).append(s)

    # Compute best-tier value per advisor
    per_faculty: Dict[str, dict] = {}
    for fid, assigned_students in faculty_students.items():
        best_value: Optional[int] = None
        best_label: str = ""
        for s in assigned_students:
            tier_label = s.tier or "C"
            val = tier_value.get(tier_label)
            if val is None:
                # Unknown tier — treat as worst possible
                val = max(tier_value.values()) + 1
            if best_value is None or val < best_value:
                best_value = val
                best_label = tier_label
        if best_value is not None:
            per_faculty[fid] = {
                "best_tier_value": best_value,
                "best_tier_label": best_label,
            }

    # Aggregate statistics (only over advisors who received ≥1 student)
    best_values = [d["best_tier_value"] for d in per_faculty.values()]
    advisors_assigned = len(best_values)

    mean_best_tier  = (sum(best_values) / advisors_assigned) if advisors_assigned else 0.0
    worst_best_tier = max(best_values) if best_values else 0

    # Fraction with at least one A-tier student
    advisors_with_A = sum(1 for d in per_faculty.values() if d["best_tier_label"] == "A")
    if all_faculty_ids is not None:
        total_advisors = len(all_faculty_ids)
    else:
        total_advisors = advisors_assigned
    fraction_with_A = (advisors_with_A / total_advisors) if total_advisors else 0.0

    return {
        "mean_best_tier":    mean_best_tier,
        "worst_best_tier":   worst_best_tier,
        "fraction_with_A":   fraction_with_A,
        "advisors_with_A":   advisors_with_A,
        "total_advisors":    total_advisors,
        "advisors_assigned": advisors_assigned,
        "quartile_mode":     quartile_mode,
        "per_faculty":       per_faculty,
    }


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def compute_metrics(
    students: List[Student],
    assignments: Dict[str, Optional[str]],
    F: int,
    faculty_ids: Optional[List[str]] = None,
) -> dict:
    """
    Compute all satisfaction metrics for a completed allocation.

    Parameters
    ----------
    students    : list of Student (with .tier, .n_tier, .cpi, .preferences set)
    assignments : {student_id: faculty_id | None}
    F           : total number of faculty (for PSI denominator)
    faculty_ids : full list of faculty IDs (for advisor-satisfaction denominator).
                  If omitted, only advisors who received ≥1 student are counted.

    Returns
    -------
    {
        "npss": float,
        "overflow_count": int,
        "mean_psi": float,
        "per_tier": {
            "<tier>": {
                "count": int,
                "mean_rank": float | None,
                "within_window_rate": float,
                "mean_npss_score": float,
                "mean_psi_score": float,
                "overflow_count": int,
            }, ...
        },
        "per_student": {
            "<student_id>": {
                "tier": str,
                "n_tier": int | None,
                "assigned_rank": int | None,
                "npss_score": float,
                "psi_score": float,
                "cpi_weight": float,
            }, ...
        },
        "advisor": {
            "mean_best_tier":    float,
            "worst_best_tier":   int,
            "fraction_with_A":   float,
            "advisors_with_A":   int,
            "total_advisors":    int,
            "advisors_assigned": int,
            "quartile_mode":     bool,
            "per_faculty":       {faculty_id: {"best_tier_value": int, "best_tier_label": str}},
        },
    }
    """
    ranks       = collect_preference_ranks(students, assignments)
    npss_res    = compute_npss(students, ranks)
    psi_res     = compute_psi(students, ranks, F)
    per_tier    = _build_per_tier(students, ranks, F)
    advisor_res = compute_advisor_metrics(students, assignments, all_faculty_ids=faculty_ids)

    # Build per-student detail
    weights = npss_res["weights"]
    per_student_npss = npss_res["per_student_npss"]
    per_student_psi  = psi_res["per_student_psi"]

    per_student: Dict[str, dict] = {}
    for s in students:
        per_student[s.id] = {
            "tier":          s.tier or "C",
            "n_tier":        s.n_tier,
            "assigned_rank": ranks.get(s.id),
            "npss_score":    per_student_npss.get(s.id, 0.0),
            "psi_score":     per_student_psi.get(s.id, 0.0),
            "cpi_weight":    weights.get(s.id, 0.0),
        }

    return {
        "npss":           npss_res["npss"],
        "overflow_count": npss_res["overflow_count"],
        "mean_psi":       psi_res["mean_psi"],
        "per_tier":       per_tier,
        "per_student":    per_student,
        "advisor":        advisor_res,
    }
