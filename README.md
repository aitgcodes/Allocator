# MS Thesis Advisor Allocation

An interactive web app for assigning MS thesis advisors to students following a structured, CPI-based protocol.

---

## What it does

1. **Phase 0** — Classifies students into tiers (A / B / C) based on CPI percentiles and sets each faculty's maximum student load.
2. **Round 1** — Each faculty picks one student from those who listed them as their first choice.
3. **Main allocation** — Remaining students are assigned interactively, class-by-class in decreasing CPI order. The app recommends the least-loaded highest-preferred advisor for each student; manual overrides require confirmation.

---

## Demo

A short walkthrough of a full allocation run is available in [`AllocationRun.mp4`](AllocationRun.mp4).

---

## Installation

### Prerequisites

| Tool | Mac | Linux | Windows |
|------|-----|-------|---------|
| Git | [git-scm.com](https://git-scm.com) or `brew install git` | `sudo apt install git` / `sudo dnf install git` | [git-scm.com](https://git-scm.com) — install with default options |
| Conda | [Miniconda](https://docs.conda.io/en/latest/miniconda.html) (recommended) or Anaconda | Same | Same — use the **Anaconda Prompt** for all commands below |

---

### Step 1 — Clone the repository

**Mac / Linux** — open Terminal:
```bash
git clone https://github.com/aitgcodes/Allocator.git
cd Allocator
```

**Windows** — open **Anaconda Prompt** (search for it in the Start menu):
```bat
git clone https://github.com/aitgcodes/Allocator.git
cd Allocator
```

---

### Step 2 — Create the Conda environment

This installs Python 3.11 and all required packages into an isolated environment called `allocator`.

**Mac / Linux:**
```bash
conda env create -f environment.yml
```

**Windows:**
```bat
conda env create -f environment.yml
```

> This only needs to be done **once**. It may take a few minutes the first time.

---

### Step 3 — Activate the environment

**Mac / Linux:**
```bash
conda activate allocator
```

**Windows:**
```bat
conda activate allocator
```

Your prompt will change to show `(allocator)` on the left, confirming the environment is active.

---

### Step 4 — Launch the app

**Mac / Linux:**
```bash
PYTHONPATH=src python -m allocator.app
```

**Windows:**
```bat
set PYTHONPATH=src && python -m allocator.app
```

You should see output like:
```
Dash is running on http://127.0.0.1:8050/
```

---

### Step 5 — Open in your browser

Open **[http://localhost:8050](http://localhost:8050)** in Chrome, Firefox, or Edge.

> Keep the terminal window open while you use the app. Close it (or press `Ctrl+C`) to stop the server.

---

### Stopping and restarting

To stop the app, press **`Ctrl+C`** in the terminal.

To restart it later, you only need steps 3 and 4 — the environment is already installed:

**Mac / Linux:**
```bash
cd Allocator
conda activate allocator
PYTHONPATH=src python -m allocator.app
```

**Windows:**
```bat
cd Allocator
conda activate allocator
set PYTHONPATH=src && python -m allocator.app
```

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

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `conda: command not found` | Miniconda/Anaconda is not installed or not on PATH — reinstall and restart your terminal |
| `ModuleNotFoundError: No module named 'allocator'` | `PYTHONPATH=src` was not set — re-run the launch command exactly as shown |
| Browser shows "This site can't be reached" | The app is not running — check the terminal for errors and make sure Step 4 completed successfully |
| Port 8050 already in use | Another instance is running. Stop it with `Ctrl+C`, or run `lsof -i :8050` (Mac/Linux) to find and kill it |
| `CondaEnvException: prefix already exists` | Environment already created — skip Step 2 and go straight to Step 3 |

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
docs/             – User manual (PDF)
reports/          – Phase-0 reports written here
```
