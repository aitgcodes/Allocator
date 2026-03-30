"""
Convert a form-exported CSV (with Name, Roll No., Preference 1/2/… columns)
into the CSV formats required by the Allocator app:

  preference_sheet.csv  — student preferences
    student_id, name, cpi, pref_1, pref_2, …

  faculty_list.csv      — unique faculty names from all preference columns
    faculty_id, name, max_load

Column mapping:
  student_id ← Roll No.
  name       ← Name
  cpi        ← CPI column if present in input, otherwise left blank
  pref_N     ← Preference N  (auto-detected, any count)

Usage
-----
    python make_preference_sheet.py input.csv
    python make_preference_sheet.py input.csv --output preference_sheet.csv
    python make_preference_sheet.py input.csv --faculty-output faculty_list.csv
    python make_preference_sheet.py input.csv --cpi-col "CGPA"
"""

import argparse
import re
import sys
import pandas as pd
from pathlib import Path


# ---------------------------------------------------------------------------
# Column-detection helpers
# ---------------------------------------------------------------------------

def find_col(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    """Return the first column name that matches (case-insensitive, substring)."""
    for candidate in candidates:
        cand_lower = candidate.lower()
        for col in df.columns:
            if cand_lower == col.strip().lower():   # exact match first
                return col
        for col in df.columns:
            if cand_lower in col.strip().lower():   # then substring match
                return col
    raise KeyError(
        f"Could not find a '{label}' column. "
        f"Tried: {candidates}. "
        f"Available columns: {list(df.columns)}"
    )


def find_pref_cols(df: pd.DataFrame) -> list[str]:
    """
    Return preference columns sorted by their numeric index.
    Matches names like: 'Preference 1', 'preference1', 'Pref. 2', 'Choice 3' …
    """
    pattern = re.compile(r'(?:preference|pref\.?|choice)\s*(\d+)', re.IGNORECASE)
    matches = []
    for col in df.columns:
        m = pattern.search(col.strip())
        if m:
            matches.append((int(m.group(1)), col))
    if not matches:
        raise KeyError(
            "No preference columns found. "
            "Expected names like 'Preference 1', 'Pref 2', 'Choice 3', …"
        )
    matches.sort(key=lambda x: x[0])
    return [col for _, col in matches]


def _dedup_pref_row(row: pd.Series) -> pd.Series:
    """Remove duplicate (non-empty) preferences, shifting remaining ones up."""
    seen: set[str] = set()
    result: list[str] = []
    for val in row:
        if pd.isna(val) or val == "":
            continue          # skip empty slots; don't count as "seen"
        if val not in seen:
            seen.add(val)
            result.append(val)
        # duplicate → skip (effectively shifts rest up)
    # Pad end with empty strings to preserve column count
    result += [""] * (len(row) - len(result))
    return pd.Series(result, index=row.index)


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def convert(
    input_path: Path,
    output_path: Path,
    faculty_output_path: Path,
    cpi_col_hint: str | None = None,
):
    df = pd.read_csv(input_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # -- Locate required columns -------------------------------------------
    name_col = find_col(df, ["Name", "Student Name", "Full Name"], "Name")
    roll_col = find_col(df, ["Roll No.", "Roll No", "Roll Number", "Roll", "RollNo", "ID"], "Roll No.")

    # CPI is optional: user can pass --cpi-col, or we auto-detect
    cpi_candidates = [cpi_col_hint] if cpi_col_hint else []
    cpi_candidates += ["CPI", "CGPA", "GPA", "cpi", "cgpa", "gpa"]
    try:
        cpi_col = find_col(df, cpi_candidates, "CPI")
    except KeyError:
        cpi_col = None
        print("Warning: No CPI/CGPA column found — 'cpi' column will be left blank.")

    pref_cols = find_pref_cols(df)
    print(f"Found {len(pref_cols)} preference column(s): {pref_cols}")

    # -- Build student output dataframe ------------------------------------
    out = pd.DataFrame()
    out["student_id"] = df[roll_col].str.strip()
    out["name"]       = df[name_col].str.strip()
    out["cpi"]        = df[cpi_col].str.strip() if cpi_col else ""

    for i, col in enumerate(pref_cols, start=1):
        out[f"pref_{i}"] = df[col].str.strip()

    # Collect all unique faculty names from the raw input (used to fill trailing slots)
    all_faculty: set[str] = set()
    for col in pref_cols:
        for val in df[col].dropna():
            val = val.strip()
            if val:
                all_faculty.add(val)

    # Extend output to cover every faculty (total columns = total unique faculty)
    n_faculty = len(all_faculty)
    for i in range(len(pref_cols) + 1, n_faculty + 1):
        out[f"pref_{i}"] = ""

    # Deduplicate per-student preference lists (shift on duplicates)
    pref_out_cols = [f"pref_{i}" for i in range(1, n_faculty + 1)]
    deduped = out[pref_out_cols].apply(_dedup_pref_row, axis=1)
    changed = (deduped.fillna("") != out[pref_out_cols].fillna("")).any(axis=1)
    if changed.any():
        print(f"Warning: Removed duplicate preferences in {changed.sum()} student row(s).")
    out[pref_out_cols] = deduped

    # Fill trailing empty slots with faculty the student missed (alphabetical order)
    def _fill_trailing(row: pd.Series) -> pd.Series:
        listed = {p for p in row if p and not pd.isna(p)}
        missed = iter(sorted(all_faculty - listed))
        result = []
        for p in row:
            if (pd.isna(p) or p == ""):
                result.append(next(missed, ""))
            else:
                result.append(p)
        return pd.Series(result, index=row.index)

    out[pref_out_cols] = out[pref_out_cols].apply(_fill_trailing, axis=1)

    # Trim to exactly the right pref columns (input may have had more or fewer)
    out = out[["student_id", "name", "cpi"] + pref_out_cols]

    # Drop rows where both student_id and name are blank (e.g., trailing empty rows)
    out = out[~(out["student_id"].isna() & out["name"].isna())]
    out = out[~((out["student_id"] == "") & (out["name"] == ""))]

    out.to_csv(output_path, index=False)
    print(f"Saved {len(out)} student(s) → {output_path}")

    # -- Build faculty output dataframe ------------------------------------
    # Collect all non-empty faculty names from every preference column, preserving
    # first-seen order, then deduplicate.
    seen: dict[str, None] = {}
    for col in pref_cols:
        for name in df[col].dropna():
            name = name.strip()
            if name:
                seen[name] = None   # dict preserves insertion order, keys = unique names

    unique_faculty = list(seen.keys())
    faculty_df = pd.DataFrame({
        "faculty_id": [f"F{i:02d}" for i in range(1, len(unique_faculty) + 1)],
        "name":       unique_faculty,
        "max_load":   "",
    })

    faculty_df.to_csv(faculty_output_path, index=False)
    print(f"Saved {len(faculty_df)} unique faculty → {faculty_output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a form CSV to Allocator preference_sheet.csv and faculty_list.csv."
    )
    parser.add_argument("input", help="Path to input CSV file")
    parser.add_argument(
        "--output", "-o",
        default="preference_sheet.csv",
        help="Student output file path (default: preference_sheet.csv)"
    )
    parser.add_argument(
        "--faculty-output", "-f",
        default="faculty_list.csv",
        help="Faculty output file path (default: faculty_list.csv)"
    )
    parser.add_argument(
        "--cpi-col",
        default=None,
        metavar="COLUMN",
        help="Exact column name for CPI/CGPA if auto-detection fails"
    )
    args = parser.parse_args()

    input_path          = Path(args.input)
    output_path         = Path(args.output)
    faculty_output_path = Path(args.faculty_output)

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    convert(input_path, output_path, faculty_output_path, cpi_col_hint=args.cpi_col)


if __name__ == "__main__":
    main()
