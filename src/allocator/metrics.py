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

    Score is (F - rank + 1) / F where F = len(student.preferences).
    The full preference list is used as the denominator for all protocols
    so that NPSS is comparable across protocols regardless of tier caps.

    Parameters
    ----------
    student : Student with .preferences set
    rank    : 1-based preference rank, or None if unassigned
    """
    if rank is None:
        return 0.0

    n = len(student.preferences)
    if n == 0:
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
    faculty: Optional[List] = None,
) -> dict:
    """
    Compute advisor satisfaction and equity metrics for a completed allocation.

    Satisfaction metrics:
        MSES (Mean Student Enthusiasm Score) — per advisor, the mean rank at which
        their assigned students listed them in the preference list. Lower = students
        were more enthusiastic about this advisor. Averaged across all advisors.

        LUR (Load Utilization Rate) — per advisor, actual_load / max_load.
        Averaged across all advisors. Requires the faculty list to be passed.

    Equity metrics:
        Baseline entropy — Shannon entropy of the cohort's tier distribution,
        normalized by log(K). This is the equity ceiling set by the cohort;
        no protocol can exceed it.

        Equity Retention Rate — avg_entropy / baseline_entropy × 100. Measures
        what fraction of the achievable equity the protocol preserved, as a
        percentage. Protocol-attributable; cohort-scale-independent.

        CPI entropy per advisor — normalized Shannon entropy of tier distribution
        within each advisor's cohort. Averaged across all assigned advisors.

        CPI Skewness — Fisher-Pearson sample skewness of advisor mean CPIs.
        Normalized by the std of advisor means (built into the formula), so
        scale-invariant. Returns None when fewer than 3 advisors have students.

    Mode is inferred from the student tiers present (quartile mode if any
    student has tier B1 or B2).

    Parameters
    ----------
    students        : list of Student (with .tier, .cpi, .preferences set)
    assignments     : {student_id: faculty_id | None}
    all_faculty_ids : unused (kept for call-site compatibility)
    faculty         : list of Faculty (with .id and .max_load); required for LUR

    Returns
    -------
    {
        "avg_mses"          : float | None — mean MSES across assigned advisors
        "avg_lur"           : float | None — mean LUR across assigned advisors
        "avg_entropy"       : float        — Σ entropy_i / F_total (empty labs = 0)
        "baseline_entropy"  : float        — Σ H_max(actual_load_i) / F_total; the tightest
                                             ceiling for this particular load distribution —
                                             equity_retention is guaranteed ≤ 100 %
        "equity_retention"  : float        — avg_entropy / baseline_entropy × 100 (percentage)
        "cpi_skewness"      : float | None — sample skewness of advisor mean CPIs; None if n < 3
        "quartile_mode"     : bool         — True if quartile tier labels (A/B1/B2/C) were used
        "K"                 : int          — number of tiers (3 or 4)
        "advisors_assigned" : int          — advisors who received ≥1 student
        "empty_labs"        : int          — F_total - advisors_assigned
        "per_faculty"       : {
            faculty_id: {
                "entropy"      : float       — normalized Shannon entropy [0, 1]
                "mean_cpi"     : float       — mean CPI of assigned students
                "student_count": int
                "mses"         : float | None — mean rank students placed this advisor
                "lur"          : float | None — actual_load / max_load
            }
        }
    }
    """
    # Detect quartile vs percentile mode from student tiers
    quartile_mode = any(s.tier in ("B1", "B2") for s in students if s.tier is not None)
    tier_labels = _QUARTILE_TIERS if quartile_mode else _PERCENTILE_TIERS
    K = len(tier_labels)
    log_K = math.log(K) if K > 1 else 1.0  # denominator for normalization

    # Faculty max-load lookup for LUR
    faculty_max_loads: Dict[str, int] = {}
    if faculty:
        faculty_max_loads = {f.id: f.max_load for f in faculty}

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

        # --- MSES: mean rank at which assigned students listed this advisor ---
        mses_ranks = []
        for s in assigned:
            try:
                mses_ranks.append(s.preferences.index(fid) + 1)
            except ValueError:
                pass
        mses = sum(mses_ranks) / len(mses_ranks) if mses_ranks else None

        # --- LUR: actual_load / max_load ---
        ml = faculty_max_loads.get(fid)
        lur = (n / ml) if (ml and ml > 0) else None

        per_faculty[fid] = {
            "entropy":       normalized_entropy,
            "mean_cpi":      mean_cpi,
            "student_count": n,
            "tier_counts":   tier_counts,
            "mses":          mses,
            "lur":           lur,
        }

    advisors_assigned = len(per_faculty)

    # F_total is the authoritative denominator for both avg_entropy and
    # baseline_entropy so the ratio is comparable across policies regardless
    # of how many labs end up empty.
    F_total = len(faculty) if faculty else advisors_assigned

    # Average normalized entropy — sum over ALL faculty, empty labs contribute 0.
    avg_entropy = (
        sum(d["entropy"] for d in per_faculty.values()) / F_total
        if F_total else 0.0
    )

    # Load-aware entropy ceiling — the maximum avg_entropy achievable for the
    # *actual* load distribution produced by this policy.  For each advisor
    # with n assigned students the per-advisor ceiling is
    #   H_max(n) = log(min(n, K)) / log(K)
    # (an advisor with 1 student cannot have diversity > 0; empty labs = 0).
    # Dividing by F_total keeps the same scale as avg_entropy above, so
    # equity_retention = avg_entropy / baseline_entropy is guaranteed ≤ 1.
    if F_total > 0 and K > 1:
        baseline_entropy = sum(
            (math.log(min(d["student_count"], K)) / log_K)
            for d in per_faculty.values()
        ) / F_total   # empty labs contribute 0 (not in per_faculty)
        if baseline_entropy == 0.0:
            baseline_entropy = 1.0  # guard: all advisors have 1 student → no diversity possible
    else:
        baseline_entropy = 1.0

    # Equity Retention Rate — guaranteed in [0, 100] by construction.
    equity_retention = (avg_entropy / baseline_entropy * 100.0) if baseline_entropy > 0 else 100.0

    # Avg MSES
    mses_vals = [d["mses"] for d in per_faculty.values() if d["mses"] is not None]
    avg_mses: Optional[float] = sum(mses_vals) / len(mses_vals) if mses_vals else None

    # Avg LUR
    lur_vals = [d["lur"] for d in per_faculty.values() if d["lur"] is not None]
    avg_lur: Optional[float] = sum(lur_vals) / len(lur_vals) if lur_vals else None

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

    empty_labs = F_total - advisors_assigned
    return {
        "avg_mses":          avg_mses,
        "avg_lur":           avg_lur,
        "avg_entropy":       avg_entropy,
        "baseline_entropy":  baseline_entropy,
        "equity_retention":  equity_retention,
        "cpi_skewness":      cpi_skewness,
        "quartile_mode":     quartile_mode,
        "K":                 K,
        "advisors_assigned": advisors_assigned,
        "empty_labs":        empty_labs,
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
    faculty: Optional[List] = None,
) -> dict:
    """
    Compute all satisfaction metrics for a completed allocation.

    Parameters
    ----------
    students    : list of Student (with .tier, .n_tier, .cpi, .preferences set)
    assignments : {student_id: faculty_id | None}
    F           : total number of faculty (for PSI denominator)
    faculty_ids : full list of faculty IDs (unused; kept for compatibility)
    faculty     : list of Faculty objects; required for LUR computation

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
            "avg_mses":          float | None,
            "avg_lur":           float | None,
            "avg_entropy":       float,
            "baseline_entropy":  float,
            "equity_retention":  float,
            "cpi_skewness":      float | None,
            "quartile_mode":     bool,
            "K":                 int,
            "advisors_assigned": int,
            "per_faculty": {
                faculty_id: {
                    "entropy": float, "mean_cpi": float, "student_count": int,
                    "mses": float | None, "lur": float | None,
                }
            },
        },
    }
    """
    ranks       = collect_preference_ranks(students, assignments)
    npss_res    = compute_npss(students, ranks)
    psi_res     = compute_psi(students, ranks, F)
    per_tier    = _build_per_tier(students, ranks, F)
    advisor_res = compute_advisor_metrics(
        students, assignments,
        all_faculty_ids=faculty_ids,
        faculty=faculty,
    )

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
