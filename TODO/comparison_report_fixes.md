# Comparison Report Fixes

## Summary of Issues Found

### Issue 1 — 2020 Anonymized CSV Has Duplicate Preferences (Bug)

The raw 2020 Excel had students listing the same faculty in multiple preference slots.
`anonymize_test_data.py` passed these through without deduplication.

**Affected rows in `test/2020/anonymized_preferences.csv`:**

| Student   | Duplicated faculty IDs |
|-----------|------------------------|
| student32 | F08 at pref_12 and pref_26 |
| student43 | F19 at pref_5 and pref_13 |
| student45 | F31 ×2, F05 ×2, F24 ×2 |
| student64 | F02 ×2, F26 ×2, F08 ×2 |
| student65 | F20 ×2, F03 ×3, F17 ×2, F09 ×2 |
| student69 | F27 ×2, F03 ×2 |
| student70 | F04 ×2 |

**Consequence A (comparison report):** `load_anonymized_students()` in
`generate_comparison_report.py` (lines 85–94) iterates all 31 pref columns without
deduplication. The `explicit` list retains both copies of the duplicated ID. Because
`pref_index = {fid: i for i, fid in enumerate(preferences)}` is built with a dict
comprehension, the **last** occurrence of a duplicated faculty ID wins, artificially
inflating its rank (e.g. for student43, F19 is treated as rank 13 instead of rank 5).
Also, one faculty that should be explicitly ranked ends up pushed to the `remaining`
backfill at the very end of the preference list.

**Consequence B (UI):** `load_students()` in `data_loader.py` (lines 205–208) raises
`ValueError: duplicate faculty` for any affected student, so loading the 2020 anonymized
CSV via the UI fails entirely.

---

### Issue 2 — Column Name Mismatch Prevents UI Loading (Bug)

The anonymized CSV outputs `student_name` and `roll_no` as column names. The UI loading
paths require `student_id` and `name`.

- `_normalise_raw_form_columns` maps `roll_no` → `student_id` via "roll" substring match.
- But `student_name` is NOT mapped to `name` — no candidate list covers it.
- Both `load_students` and `preprocess_students` then raise `ValueError: missing columns: {'name'}`.

---

### Issue 3 — 2019 Empty Labs (F24, F25): NOT a conversion bug

The 2 empty labs under Least Loaded for the 2019 cohort are **correct algorithm output**.
See discussion notes at the bottom of this file.

---

## Fixes

> **Status:** All four fixes are complete (verified 2026-04-30).
> Fix A applied in this session; Fixes B, C, D were already in the codebase.

### Fix A — `scripts/anonymize_test_data.py`, `process_year()` (~lines 87–97) ✓

Deduplicate preferences while building the `prefs` list. Treat any duplicate label as an
empty slot so the column structure is preserved.

**Current code:**
```python
for col in pref_cols:
    cell = row[col]
    if pd.isna(cell) or str(cell).strip() == "":
        prefs.append("")
    else:
        prefs.append(faculty_map.get(canonical(cell), ""))
```

**Replacement:**
```python
seen_prefs: set[str] = set()
for col in pref_cols:
    cell = row[col]
    if pd.isna(cell) or str(cell).strip() == "":
        prefs.append("")
    else:
        label = faculty_map.get(canonical(cell), "")
        if label and label not in seen_prefs:
            seen_prefs.add(label)
            prefs.append(label)
        else:
            prefs.append("")  # duplicate or unknown → treat as blank
```

This fixes the source CSVs so they are free of duplicates.

---

### Fix B — `scripts/generate_comparison_report.py`, `load_anonymized_students()` (lines 85–94)

Deduplicate while building `explicit`, preserving first-occurrence order. Defensive fix
even after Fix A regenerates clean CSVs.

**Current code:**
```python
explicit = [
    str(row[p]).strip()
    for p in pref_cols
    if pd.notna(row[p]) and str(row[p]).strip() in fac_set
]
```

**Replacement:**
```python
seen: set[str] = set()
explicit = []
for p in pref_cols:
    val = str(row[p]).strip()
    if pd.notna(row[p]) and val in fac_set and val not in seen:
        seen.add(val)
        explicit.append(val)
```

---

### Fix C — `scripts/anonymize_test_data.py`, output column names (~lines 94–109)

Rename the output columns so the anonymized CSV loads cleanly via the UI.

**Current output columns:**
```
student_name, roll_no, cpi, pref_1, …
```

**Change to:**
```
student_id, name, cpi, pref_1, …
```

In `process_year()`, change:
```python
{"student_name": label, "roll_no": row["roll_no"], "cpi": row["cpi"]}
```
to:
```python
{"student_id": label, "name": row["roll_no"], "cpi": row["cpi"]}
```

And in `out_cols`:
```python
out_cols = ["student_id", "name", "cpi"] + [f"pref_{j+1}" for j in range(max_prefs)]
```

> Note: using the roll number as the `name` field is a reasonable anonymization choice
> since actual names are not meaningful after anonymization.

---

### Fix D (Optional) — Backfill order alignment

The comparison report script backfills using `sorted(faculty_ids)` (ID sort: F01, F02, …).
The UI's `preprocess_students` backfills using sorted faculty **names** (string sort:
Prof1, Prof10, Prof11, …, Prof2, …, Prof9), which yields a completely different ID order.
This means NPSS ranks differ between the two paths even for clean data.

Two options:
1. Change the backfill in `load_anonymized_students` to use name-sort (matching the UI).
2. Change the anonymized faculty names to zero-padded form (Prof01, Prof02, …) so
   string sort matches numeric sort, aligning both paths.

Option 2 is simpler. In `process_year()` line 107:
```python
# current
"name": f"Prof{int(lbl[1:])}"

# change to
"name": f"Prof{int(lbl[1:]):02d}"
```

---

## Discussion Notes — 2019 Empty Labs

The 2 empty labs (F24, F25) for 2019 Least Loaded are **not fixable via code changes**
without altering the policy. Here is the chain of events:

1. 2019 students submitted exactly 8 explicit preferences out of 25 faculty
2. F24 and F25 each appear in only ONE student's explicit list (student2 rank 4, student15
   rank 8 respectively), and both students were assigned to their rank-1 choice in Round 1
3. For every other student, F24 and F25 appear only as alphabetical backfill at ranks 24
   and 25 — the very last positions
4. After Round 1 + Tier A + B1 + B2 processing: 5 empty labs remain (F21–F25) but only
   3 students go through the Tier C (full list) pool. They fill F21, F22, F23 (earliest
   backfill ranks). F24 and F25 stay empty.

The Least Loaded policy has no "fill empty labs" Phase 2 (unlike CPI-Fill). Empty labs
are possible when: (a) a faculty is rarely preferred explicitly, (b) those who preferred
it got their earlier choices, and (c) fewer unassigned Class C students remain than there
are empty labs at the time Class C runs.

**To prevent this in future,** either:
- Add a Phase 2 to Least Loaded that explicitly assigns remaining students to empty labs
  (policy change)
- Require the 2019 preference protocol to collect more than 8 preferences (data change)
