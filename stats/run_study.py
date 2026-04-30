# stats/run_study.py — thin wrapper; logic moved to allocator.analyze
import subprocess
import sys

REPO_ROOT = __import__("pathlib").Path(__file__).parent.parent

sys.exit(subprocess.run(
    [
        sys.executable, "-m", "allocator.analyze", "study",
        "--students", str(REPO_ROOT / "test" / "preference_sheet.csv"),
        "--faculty",  str(REPO_ROOT / "test" / "faculty_list.csv"),
        "--out",      str(REPO_ROOT / "stats/"),
    ],
    check=False,
    env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT / "src")},
).returncode)
