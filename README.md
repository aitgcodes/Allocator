# MS Thesis Advisor Allocation

An interactive web app for assigning MS thesis advisors to students following a structured, CPI-based protocol.

---

## What it does

1. **Phase 0** — Classifies students into tiers (A / B / C) based on CPI percentiles and sets each faculty's maximum student load.
2. **Round 1** — Each faculty picks one student from those who listed them as their first choice.
3. **Main allocation** — Remaining students are assigned interactively, class-by-class in decreasing CPI order. The app recommends the least-loaded highest-preferred advisor for each student; manual overrides require confirmation.

---

## Setup

```bash
conda env create -f environment.yml
conda activate allocator
```

## Run

```bash
PYTHONPATH=src python -m allocator.app
```

Then open **http://localhost:8050** in your browser.

---

## Input files

### Students (`students.csv`)
| Column | Description |
|--------|-------------|
| `student_id` | Unique ID |
| `name` | Full name |
| `cpi` | Cumulative Performance Index (numeric) |
| `pref_1`, `pref_2`, … | Faculty IDs in preference order |

### Faculty (`faculty.csv`)
| Column | Description |
|--------|-------------|
| `faculty_id` | Unique ID (must match student preference values) |
| `name` | Full name |
| `max_load` | *(optional)* Max students; leave blank to use the formula value |

Sample files are in `data/`.

---

## Output

- **Interactive summary** — assignment table + advisor popularity breakdown in the browser
- **CSV report** — download via the "Save report" button after allocation completes
- **Replay slider** — step through every allocation decision in the visualisation panel

---

## Project structure

```
src/allocator/
  app.py          – Dash application and callbacks
  allocation.py   – Phase 0 / Round 1 / main allocation logic
  data_loader.py  – CSV/Excel ingestion and Phase-0 report I/O
  state.py        – Data classes (Student, Faculty, AllocationSnapshot)
  visualizer.py   – Plotly figure builders
data/             – Sample student and faculty CSV files
reports/          – Phase-0 reports written here
```
