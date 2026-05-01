"""
Reads 2019 and 2020 preference-sheet exports from test/ and writes per-year
anonymized CSVs in raw-form style that "Clean & Load" in the UI can process.

Anonymization rules:
  Student names  → sequential integers  (1, 2, … across both years)
  Roll numbers   → same sequential integers
  CPI            → preserved, normalised to plain float (handles "8.93/10")
  Faculty names  → Prof01, Prof02, …  (globally consistent, zero-padded so
                   alphabetical order matches numeric order)

Preference columns keep their original "Preference N" headers so that
preprocess_students() in data_loader.py normalises them automatically.
Deduplication and preference-list padding are deliberately left to
preprocess_students(); this script only anonymizes names.

The faculty.csv for each year is the union of all unique faculty IDs
that appear in that year's preference columns — no manual curation needed.

Outputs (one pair per year):
  test/2019/anonymized_preferences.csv
  test/2019/faculty.csv
  test/2020/anonymized_preferences.csv
  test/2020/faculty.csv
"""

import re
from pathlib import Path

import pandas as pd

ROOT     = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT / "test"

SOURCES = [
    TEST_DIR / "2019" / "2019 Preference Sheet.xlsx",
    TEST_DIR / "2020" / "2020 Preference Sheet.xlsx",
]

CO_PI_RE = re.compile(r"\s*\(Co PI-[^)]*\)", re.IGNORECASE)


def canonical(name: str) -> str:
    """Strip '(Co PI-…)' suffixes and surrounding whitespace."""
    return CO_PI_RE.sub("", str(name)).strip()


def clean_cpi(raw: str) -> str:
    """Return a plain numeric string; handles 'X/10' forms."""
    s = str(raw).strip()
    if "/" in s:
        s = s.split("/")[0].strip()
    return s


def load_sheet(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Form Responses 1", dtype=str)
    keep      = ["Name", "Roll No.", "CPI (as on date)"]
    pref_cols = [c for c in df.columns if c.strip().lower().startswith("preference")]
    return df[keep + pref_cols].copy()


def build_faculty_map(frames: list[pd.DataFrame]) -> dict[str, str]:
    """
    Scan preference columns across all frames (2019 first, then 2020).
    Assign a globally-unique name Prof01, Prof02, … to each canonical
    faculty name on first appearance.
    Returns: canonical_name → Prof0N
    """
    faculty_map: dict[str, str] = {}
    counter = 0
    for df in frames:
        pref_cols = [c for c in df.columns if c.strip().lower().startswith("preference")]
        for col in pref_cols:
            for cell in df[col]:
                if pd.isna(cell) or str(cell).strip() == "":
                    continue
                name = canonical(cell)
                if name and name not in faculty_map:
                    counter += 1
                    faculty_map[name] = f"Prof{counter:02d}"
    return faculty_map


def process_year(
    df: pd.DataFrame,
    faculty_map: dict[str, str],
    student_offset: int,
    out_dir: Path,
) -> int:
    pref_cols    = [c for c in df.columns if c.strip().lower().startswith("preference")]
    rows         = []
    year_faculty: set[str] = set()

    for i, (_, row) in enumerate(df.iterrows()):
        seq = student_offset + i + 1          # global sequential label

        anon_prefs: dict[str, str] = {}
        for col in pref_cols:
            cell = row[col]
            if pd.isna(cell) or str(cell).strip() == "":
                anon_prefs[col] = ""
            else:
                anon_name = faculty_map.get(canonical(cell), "")
                anon_prefs[col] = anon_name
                if anon_name:
                    year_faculty.add(anon_name)

        out_row: dict[str, str] = {
            "Name":             f"student{seq:02d}",
            "Roll No.":         str(seq),
            "CPI (as on date)": clean_cpi(row["CPI (as on date)"]),
        }
        out_row.update(anon_prefs)
        rows.append(out_row)

    out_cols = ["Name", "Roll No.", "CPI (as on date)"] + pref_cols
    pd.DataFrame(rows, columns=out_cols).to_csv(
        out_dir / "anonymized_preferences.csv", index=False
    )

    sorted_names = sorted(year_faculty, key=lambda s: int(s[4:]))
    fac_rows = [{"name": name, "max_load": ""} for name in sorted_names]
    pd.DataFrame(fac_rows, columns=["name", "max_load"]).to_csv(
        out_dir / "faculty.csv", index=False
    )

    return len(rows)


def main() -> None:
    frames      = [load_sheet(p) for p in SOURCES]
    faculty_map = build_faculty_map(frames)

    offset = 0
    for source, df in zip(SOURCES, frames):
        out_dir = source.parent
        n = process_year(df, faculty_map, offset, out_dir)
        print(f"{out_dir.name}: {n} students → {out_dir / 'anonymized_preferences.csv'}")
        print(f"{out_dir.name}: faculty   → {out_dir / 'faculty.csv'}")
        offset += n

    print(f"\nTotal students : {offset}")
    print(f"Unique faculty : {len(faculty_map)}")


if __name__ == "__main__":
    main()
