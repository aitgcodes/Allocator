"""
metrics.py — Student satisfaction metrics for MS Thesis Advisor Allocation.

Primary metric   — NPSS (Normalized Preference Satisfaction Score):
    CPI-weighted, tier-aware, window-enforcing.

Secondary metric — PSI (Preference Satisfaction Index):
    Global rank score, equal-weighted, policy-agnostic.
"""

from __future__ import annotations

import math
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

_PERCENTILE_TIERS = ["A", "B", "C"]
_QUARTILE_TIERS   = ["A", "B1", "B2", "C"]


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
    Compute advisor-fairness metrics for a completed allocation.

    Metric 1 — CPI entropy per advisor:
        For each advisor, bucket their assigned students into CPI tiers, compute
        Shannon entropy H(a) = -∑ p_k log p_k (with 0·log0 = 0), and normalize
        by log(K) where K is the number of tiers, so the score lies in [0, 1].
        Also reports the average normalized entropy across all assigned advisors.

    Metric 2 — Skewness of advisor mean CPIs:
        For each advisor, compute the mean CPI of their assigned students.
        Then compute the sample skewness of those advisor-wise means:
            n / ((n-1)(n-2)) * ∑ ((x_i - x̄) / s)³
        Returns None when fewer than 3 advisors have students.

    Mode is inferred from the student tiers present (quartile mode if any
    student has tier B1 or B2).

    Parameters
    ----------
    students        : list of Student (with .tier and .cpi set)
    assignments     : {student_id: faculty_id | None}
    all_faculty_ids : unused (kept for call-site compatibility)

    Returns
    -------
    {
        "avg_entropy"       : float        — mean normalized entropy across assigned advisors
        "cpi_skewness"      : float | None — sample skewness of advisor mean CPIs; None if n < 3
        "quartile_mode"     : bool         — True if quartile tier labels (A/B1/B2/C) were used
        "K"                 : int          — number of tiers (3 or 4)
        "advisors_assigned" : int          — advisors who received ≥1 student
        "per_faculty"       : {
            faculty_id: {
                "entropy"      : float  — normalized Shannon entropy [0, 1]
                "mean_cpi"     : float  — mean CPI of assigned students
                "student_count": int
            }
        }
    }
    """
    # Detect quartile vs percentile mode from student tiers
    quartile_mode = any(s.tier in ("B1", "B2") for s in students if s.tier is not None)
    tier_labels = _QUARTILE_TIERS if quartile_mode else _PERCENTILE_TIERS
    K = len(tier_labels)
    log_K = math.log(K) if K > 1 else 1.0  # denominator for normalization

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

    # Compute per-advisor metrics
    per_faculty: Dict[str, dict] = {}
    for fid, assigned in faculty_students.items():
        n = len(assigned)

        # --- Metric 1: normalized CPI entropy ---
        tier_counts: Dict[str, int] = {t: 0 for t in tier_labels}
        for s in assigned:
            t = s.tier if s.tier in tier_counts else (tier_labels[-1])
            tier_counts[t] += 1

        entropy = 0.0
        for count in tier_counts.values():
            if count > 0:
                p = count / n
                entropy -= p * math.log(p)
        normalized_entropy = entropy / log_K

        # --- Metric 2 component: mean CPI ---
        mean_cpi = sum(s.cpi for s in assigned) / n

        per_faculty[fid] = {
            "entropy":       normalized_entropy,
            "mean_cpi":      mean_cpi,
            "student_count": n,
            "tier_counts":   tier_counts,
        }

    advisors_assigned = len(per_faculty)

    # Average normalized entropy across all assigned advisors
    avg_entropy = (
        sum(d["entropy"] for d in per_faculty.values()) / advisors_assigned
        if advisors_assigned else 0.0
    )

    # --- Metric 2: sample skewness of advisor mean CPIs ---
    cpi_skewness: Optional[float] = None
    if advisors_assigned >= 3:
        means = [d["mean_cpi"] for d in per_faculty.values()]
        n_adv = len(means)
        x_bar = sum(means) / n_adv
        variance = sum((x - x_bar) ** 2 for x in means) / (n_adv - 1)
        s = math.sqrt(variance) if variance > 0 else 0.0
        if s > 0:
            cpi_skewness = (
                n_adv / ((n_adv - 1) * (n_adv - 2))
                * sum(((x - x_bar) / s) ** 3 for x in means)
            )
        else:
            cpi_skewness = 0.0

    return {
        "avg_entropy":       avg_entropy,
        "cpi_skewness":      cpi_skewness,
        "quartile_mode":     quartile_mode,
        "K":                 K,
        "advisors_assigned": advisors_assigned,
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
            "avg_entropy":       float,
            "cpi_skewness":      float | None,
            "quartile_mode":     bool,
            "K":                 int,
            "advisors_assigned": int,
            "per_faculty":       {faculty_id: {"entropy": float, "mean_cpi": float, "student_count": int}},
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
