"""
data_loader.py — CSV / Excel ingestion, validation, and Phase-0-report I/O.

Public API
----------
    load_students(path)      -> List[Student]
    load_faculty(path)       -> List[Faculty]   (max_load may be NaN → filled later)
    save_phase0_report(...)  -> writes  <path>/phase0_report.csv
    load_phase0_report(path) -> (List[Student], phase0_meta dict)

Input formats
-------------
students file columns:
    student_id  name  cpi  pref_1  pref_2  ...  pref_N

faculty file columns:
    faculty_id  name  [max_load]   ← max_load column is optional;
                                     blank / absent → formula value filled in
                                     by allocation.py Phase 0.

Phase-0 report columns (CSV):
    student_id  name  cpi  tier  n_tier  pref_1  pref_2  ...

Phase-0 meta row:
    A separate single-row CSV:  phase0_meta.csv
    Columns: cohort_size, faculty_count, ratio, N_A, N_B, common_max_load,
             mode, p_low_pct, p_high_pct, p_low, p_high, grace
    p_low_pct / p_high_pct: which percentile was used for each tier boundary
        (25/75 in quartile mode, 70/90 in percentile mode, blank for tiny-cohort)
    p_low / p_high: the actual CPI value at that percentile
"""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .state import Faculty, Student

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pref_columns(df: pd.DataFrame) -> List[str]:
    """Return ordered list of pref_N column names present in df."""
    return sorted(
        [c for c in df.columns if c.lower().startswith("pref_")],
        key=lambda c: int(c.split("_")[1]),
    )


def _clean_id(val) -> str:
    return str(val).strip()


# ---------------------------------------------------------------------------
# Load students
# ---------------------------------------------------------------------------

def load_students(path: str | Path) -> List[Student]:
    """
    Load student data from a CSV or Excel file.

    Required columns : student_id, name, cpi
    Preference cols  : pref_1, pref_2, ..., pref_N  (at least pref_1)

    Returns a list of Student objects with tier=None (set later in Phase 0).
    """
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)

    df.columns = [c.strip().lower() for c in df.columns]

    required = {"student_id", "name", "cpi"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"students file missing columns: {missing}")

    pref_cols = _pref_columns(df)
    if not pref_cols:
        raise ValueError("students file must have at least one pref_1 column")

    students: List[Student] = []
    seen_ids: set[str] = set()

    for _, row in df.iterrows():
        sid = _clean_id(row["student_id"])
        if not sid:
            continue
        if sid in seen_ids:
            raise ValueError(f"Duplicate student_id: {sid}")
        seen_ids.add(sid)

        try:
            cpi = float(row["cpi"])
        except (ValueError, TypeError):
            raise ValueError(f"Student {sid}: cpi must be numeric, got {row['cpi']!r}")

        prefs: List[str] = []
        seen_prefs: set[str] = set()
        for col in pref_cols:
            val = str(row.get(col, "")).strip()
            if val and val.lower() not in ("nan", "none", ""):
                fid = _clean_id(val)
                if fid in seen_prefs:
                    raise ValueError(
                        f"Student {sid}: duplicate faculty {fid!r} in preferences"
                    )
                seen_prefs.add(fid)
                prefs.append(fid)

        students.append(
            Student(
                id=sid,
                name=str(row["name"]).strip(),
                cpi=cpi,
                preferences=prefs,
            )
        )

    if not students:
        raise ValueError("students file contains no valid rows")

    return students


# ---------------------------------------------------------------------------
# Load faculty
# ---------------------------------------------------------------------------

def load_faculty(path: str | Path) -> List[Faculty]:
    """
    Load faculty data from a CSV or Excel file.

    Required columns : faculty_id, name
    Optional column  : max_load  (integer; blank / absent → None, filled by Phase 0)

    Returns Faculty objects with max_load=-1 where not specified.
    -1 is a sentinel meaning "use formula value".
    """
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)

    df.columns = [c.strip().lower() for c in df.columns]

    required = {"faculty_id", "name"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"faculty file missing columns: {missing}")

    has_max_load = "max_load" in df.columns

    faculty: List[Faculty] = []
    seen_ids: set[str] = set()

    for _, row in df.iterrows():
        fid = _clean_id(row["faculty_id"])
        if not fid:
            continue
        if fid in seen_ids:
            raise ValueError(f"Duplicate faculty_id: {fid}")
        seen_ids.add(fid)

        max_load: int = -1   # sentinel → formula
        if has_max_load:
            raw = str(row.get("max_load", "")).strip()
            if raw and raw.lower() not in ("nan", "none", ""):
                try:
                    max_load = int(raw)
                    if max_load < 1:
                        raise ValueError
                except ValueError:
                    raise ValueError(
                        f"Faculty {fid}: max_load must be a positive integer, got {raw!r}"
                    )

        faculty.append(
            Faculty(
                id=fid,
                name=str(row["name"]).strip(),
                max_load=max_load,
            )
        )

    if not faculty:
        raise ValueError("faculty file contains no valid rows")

    return faculty


# ---------------------------------------------------------------------------
# Cross-validate preferences
# ---------------------------------------------------------------------------

def validate_preferences(students: List[Student], faculty: List[Faculty]) -> None:
    """
    Raise ValueError if any student preference ID is not in the faculty list.
    Call after loading both files.
    """
    known_fids = {f.id for f in faculty}
    errors: List[str] = []
    for s in students:
        bad = [p for p in s.preferences if p not in known_fids]
        if bad:
            errors.append(f"  Student {s.id} ({s.name}): unknown faculty IDs {bad}")
    if errors:
        raise ValueError("Preference validation failed:\n" + "\n".join(errors))


# ---------------------------------------------------------------------------
# Phase-0 report I/O
# ---------------------------------------------------------------------------

def save_phase0_report(
    students: List[Student],
    meta: dict,
    out_dir: str | Path,
) -> Tuple[Path, Path]:
    """
    Write two CSV files into out_dir:
        phase0_report.csv  — one row per student with tier, n_tier, preferences
        phase0_meta.csv    — one row with cohort-level parameters

    Parameters
    ----------
    students : list of Student objects (must have .tier and .n_tier set)
    meta     : dict produced by allocation.phase0()  (see allocation.py)
    out_dir  : directory path (created if absent)

    Returns
    -------
    (report_path, meta_path)
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "phase0_report.csv"
    meta_path   = out_dir / "phase0_meta.csv"

    # --- student report ---
    max_prefs = max((len(s.preferences) for s in students), default=0)
    pref_headers = [f"pref_{i+1}" for i in range(max_prefs)]

    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["student_id", "name", "cpi", "tier", "n_tier"] + pref_headers
        )
        for s in students:
            padded = s.preferences + [""] * (max_prefs - len(s.preferences))
            writer.writerow([s.id, s.name, s.cpi, s.tier, s.n_tier] + padded)

    # --- meta ---
    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(meta.keys()))
        writer.writeheader()
        writer.writerow(meta)

    return report_path, meta_path


def load_phase0_report(
    report_path: str | Path,
    meta_path: str | Path,
) -> Tuple[List[Student], dict]:
    """
    Load a previously saved Phase-0 report and reconstruct Student objects
    (with .tier and .n_tier already populated).

    Parameters
    ----------
    report_path : path to phase0_report.csv
    meta_path   : path to phase0_meta.csv

    Returns
    -------
    (students, meta_dict)
    """
    report_path = Path(report_path)
    meta_path   = Path(meta_path)

    df = pd.read_csv(report_path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"student_id", "name", "cpi", "tier", "n_tier"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"phase0_report.csv missing columns: {missing}")

    pref_cols = _pref_columns(df)
    students: List[Student] = []

    for _, row in df.iterrows():
        sid = _clean_id(row["student_id"])
        if not sid:
            continue
        cpi = float(row["cpi"])
        tier = str(row["tier"]).strip()

        raw_ntier = str(row["n_tier"]).strip().upper()
        n_tier: Optional[int]
        if raw_ntier in ("ALL", "NONE", "NAN", ""):
            n_tier = None          # Class C → global cap, handled by allocator
        else:
            n_tier = int(raw_ntier)

        prefs: List[str] = []
        for col in pref_cols:
            val = str(row.get(col, "")).strip()
            if val and val.lower() not in ("nan", "none", ""):
                prefs.append(_clean_id(val))

        students.append(
            Student(
                id=sid,
                name=str(row["name"]).strip(),
                cpi=cpi,
                preferences=prefs,
                tier=tier,
                n_tier=n_tier,
            )
        )

    # --- meta ---
    meta_df = pd.read_csv(meta_path)
    meta = meta_df.iloc[0].to_dict()
    # coerce numeric fields
    for key in ("cohort_size", "faculty_count", "N_A", "N_B", "common_max_load"):
        if key in meta:
            meta[key] = int(float(meta[key]))
    for key in ("ratio", "p_low", "p_high", "grace"):
        if key in meta:
            meta[key] = float(meta[key]) if meta[key] != "" else None
    for key in ("p_low_pct", "p_high_pct"):
        if key in meta:
            meta[key] = int(float(meta[key])) if meta[key] != "" else None

    return students, meta
