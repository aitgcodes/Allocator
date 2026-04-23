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
# Preference-cleaning helpers (also used by preprocess_students)
# ---------------------------------------------------------------------------

def _dedup_pref_row(row: pd.Series) -> pd.Series:
    """Remove duplicate (non-empty) preferences, shifting remaining ones up."""
    seen: set[str] = set()
    result: list[str] = []
    for val in row:
        if pd.isna(val) or val == "":
            continue
        if val not in seen:
            seen.add(val)
            result.append(val)
    result += [""] * (len(row) - len(result))
    return pd.Series(result, index=row.index)

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
# Preprocess raw form exports
# ---------------------------------------------------------------------------

def preprocess_students(
    path: str | Path,
    faculty: List[Faculty],
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Load a raw student file (CSV or Excel), apply three cleaning steps, and
    return a cleaned DataFrame ready for load_students() plus a list of
    human-readable warning strings describing what changed.

    Cleaning steps (in order):
    1. Map faculty names → IDs using the faculty list.  Any value already
       matching a faculty ID is passed through unchanged, so the function
       works on files that already use IDs.
    2. Remove duplicate preferences per student (shift remaining entries up).
    3. Backfill trailing empty slots with faculty the student did not mention,
       in alphabetical order by name, so every student has a complete ranking
       across all faculty.

    Parameters
    ----------
    path    : path to the raw students CSV or Excel file
    faculty : authoritative faculty list — defines the full set for backfill

    Returns
    -------
    (cleaned_df, warnings)
        cleaned_df columns: student_id, name, cpi, pref_1, ..., pref_N
            where N = len(faculty)
        warnings: list of message strings; empty if no changes were needed
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

    # Build name→ID and ID→name maps from the faculty list
    name_to_id: Dict[str, str] = {f.name: f.id for f in faculty}
    all_fids: set[str] = {f.id for f in faculty}
    # Alphabetical faculty names for backfill ordering
    all_faculty_names_sorted = sorted(f.name for f in faculty)
    fid_by_sorted_name: List[str] = [name_to_id[n] for n in all_faculty_names_sorted]

    n_faculty = len(faculty)

    # Ensure we have enough pref columns (pad with empty ones as needed)
    out = df[["student_id", "name", "cpi"]].copy()
    for i, col in enumerate(pref_cols, start=1):
        out[f"pref_{i}"] = df[col].str.strip().fillna("")
    for i in range(len(pref_cols) + 1, n_faculty + 1):
        out[f"pref_{i}"] = ""

    pref_out_cols = [f"pref_{i}" for i in range(1, n_faculty + 1)]

    # Step 1 — name → ID mapping
    def _map_name_to_id(val: str) -> str:
        if not val or pd.isna(val):
            return ""
        if val in all_fids:
            return val          # already an ID
        return name_to_id.get(val, val)  # map name; unknown values pass through

    before_map = out[pref_out_cols].copy()
    for col in pref_out_cols:
        out[col] = out[col].apply(_map_name_to_id)
    map_changed = int((out[pref_out_cols].fillna("") != before_map.fillna("")).any(axis=1).sum())

    # Step 2 — deduplication
    before_dedup = out[pref_out_cols].copy()
    out[pref_out_cols] = out[pref_out_cols].apply(_dedup_pref_row, axis=1)
    dedup_changed = (out[pref_out_cols].fillna("") != before_dedup.fillna("")).any(axis=1).sum()

    # Step 3 — backfill missing faculty
    def _fill_trailing(row: pd.Series) -> pd.Series:
        listed = {p for p in row if p and not pd.isna(p)}
        missed = iter(fid for fid in fid_by_sorted_name if fid not in listed)
        result = []
        for p in row:
            if not p or pd.isna(p):
                result.append(next(missed, ""))
            else:
                result.append(p)
        return pd.Series(result, index=row.index)

    before_fill = out[pref_out_cols].copy()
    out[pref_out_cols] = out[pref_out_cols].apply(_fill_trailing, axis=1)
    fill_changed = (out[pref_out_cols].fillna("") != before_fill.fillna("")).any(axis=1).sum()

    warnings: List[str] = []
    if map_changed:
        warnings.append(f"Converted faculty names → IDs in {map_changed} student row(s).")
    if dedup_changed:
        warnings.append(f"Removed duplicate preferences in {dedup_changed} student row(s).")
    if fill_changed:
        warnings.append(f"Backfilled missing preferences in {fill_changed} student row(s).")

    # Drop fully-blank rows
    out = out[~((out["student_id"].fillna("") == "") & (out["name"].fillna("") == ""))]

    return out[["student_id", "name", "cpi"] + pref_out_cols], warnings, map_changed


# ---------------------------------------------------------------------------
# Cross-validate preferences
# ---------------------------------------------------------------------------

def validate_preferences(students: List[Student], faculty: List[Faculty]) -> None:
    """
    Raise ValueError if any student preference ID is not in the faculty list.
    Call after loading both files.
    """
    known_fids = {f.id for f in faculty}
    known_names = {f.name for f in faculty}
    errors: List[str] = []
    name_confusion = False
    for s in students:
        bad = [p for p in s.preferences if p not in known_fids]
        if bad:
            errors.append(f"  Student {s.id} ({s.name}): unknown faculty IDs {bad}")
            if not name_confusion and any(p in known_names for p in bad):
                name_confusion = True
    if errors:
        msg = "Preference validation failed:\n" + "\n".join(errors)
        if name_confusion:
            msg += (
                "\nHint: preferences appear to use faculty names instead of IDs. "
                "Use 'Clean & Load' to convert them automatically."
            )
        raise ValueError(msg)


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
    for key in ("ratio", "p_low", "p_mid", "p_high", "grace"):
        if key in meta:
            meta[key] = float(meta[key]) if str(meta[key]) not in ("", "nan", "NaN") else None
    for key in ("p_low_pct", "p_high_pct"):
        if key in meta:
            meta[key] = int(float(meta[key])) if meta[key] != "" else None

    return students, meta
