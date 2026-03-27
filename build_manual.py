"""
build_manual.py — Generate the user manual PDF for the Allocator app.
Run from the project root:  python build_manual.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUT = "docs/Allocator_User_Manual.pdf"

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
base = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, parent=base["Normal"], **kw)

Title    = S("MyTitle",   fontSize=26, leading=32, textColor=colors.HexColor("#1a237e"),
             spaceAfter=6,  fontName="Helvetica-Bold", alignment=TA_CENTER)
Subtitle = S("MySub",     fontSize=13, leading=18, textColor=colors.HexColor("#455a64"),
             spaceAfter=20, alignment=TA_CENTER)
H1       = S("MyH1",      fontSize=16, leading=22, textColor=colors.HexColor("#1a237e"),
             spaceBefore=18, spaceAfter=6, fontName="Helvetica-Bold")
H2       = S("MyH2",      fontSize=13, leading=18, textColor=colors.HexColor("#37474f"),
             spaceBefore=12, spaceAfter=4, fontName="Helvetica-Bold")
Body     = S("MyBody",    fontSize=10.5, leading=16, spaceAfter=6)
Bullet   = S("MyBullet",  fontSize=10.5, leading=16, spaceAfter=4,
             leftIndent=16, bulletIndent=0)
Note     = S("MyNote",    fontSize=9.5,  leading=14, spaceAfter=4,
             textColor=colors.HexColor("#546e7a"), leftIndent=12)
Bold     = S("MyBold",    fontSize=10.5, leading=16, fontName="Helvetica-Bold")
Code     = S("MyCode",    fontSize=9,    leading=14, fontName="Courier",
             backColor=colors.HexColor("#f5f5f5"), leftIndent=12, spaceAfter=6)

def h1(text):  return Paragraph(text, H1)
def h2(text):  return Paragraph(text, H2)
def p(text):   return Paragraph(text, Body)
def b(text):   return Paragraph(f"• &nbsp; {text}", Bullet)
def note(text): return Paragraph(f"<i>💡 {text}</i>", Note)
def hr():      return HRFlowable(width="100%", thickness=0.5,
                                 color=colors.HexColor("#b0bec5"), spaceAfter=6)

def step_box(num, title, body_items):
    """Numbered step with a light-blue left bar effect via a 2-col table."""
    num_para  = Paragraph(str(num), ParagraphStyle("SN", fontSize=18,
                           fontName="Helvetica-Bold", textColor=colors.white,
                           alignment=TA_CENTER, leading=22))
    title_para = Paragraph(title, ParagraphStyle("ST", fontSize=12,
                            fontName="Helvetica-Bold",
                            textColor=colors.HexColor("#1a237e"), leading=16))
    body_paras = [title_para] + [Paragraph(f"• {item}", Body) for item in body_items]
    body_cell  = body_paras

    t = Table([[num_para, body_cell]], colWidths=[1.2*cm, 14.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, 0), colors.HexColor("#1565c0")),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.HexColor("#e8eaf6")]),
        ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#9fa8da")),
    ]))
    return KeepTogether([t, Spacer(1, 10)])

def col_table(headers, rows, col_widths=None):
    data = [[Paragraph(f"<b>{h}</b>", Body) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), Body) for c in row])
    if col_widths is None:
        col_widths = [15.7 * cm / len(headers)] * len(headers)
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1),
         [colors.HexColor("#f5f5f5"), colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#b0bec5")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    return t

# ---------------------------------------------------------------------------
# Build story
# ---------------------------------------------------------------------------
story = []

# Cover
story += [
    Spacer(1, 2*cm),
    Paragraph("MS Thesis Advisor Allocation", Title),
    Paragraph("User Manual", Subtitle),
    Spacer(1, 0.5*cm),
    hr(),
    Spacer(1, 0.5*cm),
    p("This manual explains how to use the <b>Allocator</b> web app to assign "
      "MS thesis advisors to students. No technical knowledge is required — "
      "all you need is a web browser and two data files."),
    Spacer(1, 1*cm),
]

# ── 1. What the app does ────────────────────────────────────────────────────
story += [
    h1("1.  What the App Does"),
    p("The Allocator assigns each student an MS thesis advisor following a "
      "three-phase protocol designed to respect student preferences while "
      "balancing faculty workloads."),
    Spacer(1, 6),
    col_table(
        ["Phase", "What happens"],
        [
            ["Phase 0", "Students are grouped into Tiers A, B, or C based on their CPI. "
                        "Each faculty's maximum student load is also calculated."],
            ["Round 1", "Each faculty member picks one student from among those who listed "
                        "that faculty as their first choice (highest CPI wins if there is a tie)."],
            ["Main allocation", "All remaining students are assigned interactively, "
                                "starting with the highest-CPI students. "
                                "The app recommends the best advisor for each student; "
                                "you can accept or override."],
        ],
        col_widths=[3.5*cm, 12.2*cm],
    ),
    Spacer(1, 10),
]

# ── 2. What you need ────────────────────────────────────────────────────────
story += [
    h1("2.  What You Need"),
    h2("2.1  Student file  (CSV or Excel)"),
    p("One row per student. Required columns:"),
    col_table(
        ["Column name", "Example", "Notes"],
        [
            ["student_id", "S01", "Any unique label"],
            ["name",       "Aditya Verma", ""],
            ["cpi",        "9.40", "Numeric, e.g. on a 10-point scale"],
            ["pref_1",     "F03", "Faculty ID of first choice"],
            ["pref_2",     "F01", "Second choice (add as many columns as needed)"],
        ],
        col_widths=[3.5*cm, 4*cm, 8.2*cm],
    ),
    Spacer(1, 10),
    h2("2.2  Faculty file  (CSV or Excel)"),
    p("One row per faculty member. Required columns:"),
    col_table(
        ["Column name", "Example", "Notes"],
        [
            ["faculty_id", "F03", "Must match the IDs used in the student preferences"],
            ["name",       "Dr. Priya Nair", ""],
            ["max_load",   "4", "Optional — leave blank to let the app calculate automatically"],
        ],
        col_widths=[3.5*cm, 4*cm, 8.2*cm],
    ),
    Spacer(1, 10),
    note("Both files can be .csv or .xlsx. Column names are not case-sensitive "
         "and extra spaces are ignored."),
    Spacer(1, 6),
]

# ── 3. Opening the app ──────────────────────────────────────────────────────
story += [
    h1("3.  Starting and Opening the App"),
    p("You need to start the app server once before opening it in your browser. "
      "This is a one-time step each session — the server keeps running in the "
      "background while you use the app."),
    Spacer(1, 6),
    h2("3.1  One-time setup  (first time only)"),
    p("Open a Terminal (Mac / Linux) or Command Prompt (Windows) and run:"),
    Paragraph("conda activate allocator", Code),
    note("If the <i>allocator</i> environment has not been created yet, run "
         "<b>conda env create -f environment.yml</b> first, then activate it."),
    Spacer(1, 6),
    h2("3.2  Start the server"),
    p("In the same terminal, navigate to the project folder and run:"),
    Paragraph("PYTHONPATH=src python -m allocator.app", Code),
    p("You will see a message like:"),
    Paragraph("Dash is running on http://127.0.0.1:8050/", Code),
    p("Leave this terminal window open. The server runs in the foreground — "
      "closing the terminal will stop the app."),
    Spacer(1, 6),
    h2("3.3  Open in your browser"),
    p("Open any modern web browser (Chrome, Firefox, Safari, Edge) and go to:"),
    Paragraph("http://localhost:8050", Code),
    p("The Allocator app will load. You can now upload your files and begin."),
    note("To stop the server when you are done, go back to the terminal and "
         "press Ctrl + C."),
    Spacer(1, 6),
]

# ── 4. Step-by-step walkthrough ─────────────────────────────────────────────
story += [h1("4.  Step-by-Step Walkthrough"), Spacer(1, 6)]

story.append(step_box(1, "Load your data files",
    ["In the <b>Section 1 — Data</b> panel, click the <b>Students file</b> upload area "
     "and select your student CSV/Excel file.",
     "Click the <b>Faculty file</b> upload area and select your faculty CSV/Excel file.",
     "You will see a green confirmation message when each file loads successfully.",
     "If there are any errors (e.g. a student preference refers to an unknown faculty ID), "
     "an error message will appear — fix the file and re-upload."]))

story.append(step_box(2, "Run the allocation",
    ["In <b>Section 2 — Run</b>, click <b>Run full allocation</b>.",
     "The app will immediately run Phase 0 and then pause at Round 1 for your input.",
     "Alternatively, click <b>Run Phase 0 only</b> if you just want to see the tier "
     "classification without proceeding to advisor assignment."]))

story.append(step_box(3, "Confirm Round-1 picks  (Section 3)",
    ["Each faculty member who received at least one first-choice applicant is listed.",
     "The app pre-selects the highest-CPI student for each faculty. "
     "You can change this using the dropdown next to each faculty name.",
     "When you are happy with all selections, click "
     "<b>Confirm Round-1 picks &amp; continue</b>.",
     "A summary of Round-1 assignments will appear below the button."]))

story.append(step_box(4, "Main allocation  (Section 4)",
    ["Click <b>Proceed to Main Allocation</b>.",
     "Students appear one at a time, ordered by tier (A → B → C) and then by "
     "CPI (highest first).",
     "For each student, their eligible advisors are shown as buttons. "
     "The advisor outlined in <b>orange</b> with a ★ star is the protocol recommendation "
     "— the least-loaded advisor who is also the student's highest preference.",
     "Click any advisor button to assign that student.",
     "If you pick a <b>different</b> advisor than the recommendation, a confirmation "
     "dialog will appear showing both options. Click <b>Confirm override</b> to proceed "
     "or <b>Cancel</b> to go back and pick again.",
     "Repeat until all students are assigned."]))

story.append(step_box(5, "Review the results",
    ["After the last student is assigned, a <b>completion summary</b> appears showing: "
     "number assigned, unassigned, and empty labs.",
     "A full assignment table lists every student with their advisor.",
     "The <b>Advisor popularity</b> table shows how many students ranked each advisor "
     "as their 1st, 2nd, or 3rd choice, broken down by tier.",
     "Click <b>Save report (CSV)</b> to download the final assignments as a spreadsheet."]))

# ── 5. Understanding the recommendation ─────────────────────────────────────
story += [
    PageBreak(),
    h1("5.  Understanding the Recommendation"),
    p("When you reach a student during the main allocation, the app computes the "
      "<b>protocol recommendation</b> — the single advisor that best satisfies two "
      "criteria at once:"),
    b("<b>Least loaded</b> — the advisor with the fewest students assigned so far "
      "(among those who still have capacity)."),
    b("<b>Highest preferred</b> — if two advisors have the same load, the one "
      "ranked higher in the student's preference list is chosen."),
    Spacer(1, 6),
    p("Advisors who have already reached their maximum student load are shown "
      "<b>greyed out</b> and cannot be selected."),
    Spacer(1, 6),
    note("You are never forced to follow the recommendation. The confirmation dialog "
         "is just a safety check so that overrides are always intentional."),
    Spacer(1, 10),
]

# ── 6. Tier classification ──────────────────────────────────────────────────
story += [
    h1("6.  Tier Classification (Phase 0)"),
    p("Phase 0 divides students into three tiers based on CPI:"),
    col_table(
        ["Tier", "Who qualifies", "Preference cap (N)"],
        [
            ["A (top)",    "CPI at or above the 90th percentile", "Top 3 preferences considered"],
            ["B (middle)", "CPI between the 70th and 90th percentile", "Top 5 preferences considered"],
            ["C (others)", "CPI below the 70th percentile", "All preferences considered"],
        ],
        col_widths=[2.5*cm, 7.5*cm, 5.7*cm],
    ),
    Spacer(1, 8),
    p("The preference cap means that during the main allocation, a Tier A student's "
      "eligible advisors are taken only from their top 3 choices (unless all three are "
      "full, in which case the cap expands automatically)."),
    Spacer(1, 6),
    note("Click <b>View Phase 0 data</b> in Section 2 at any time to see each "
         "student's tier, CPI, and N value."),
    Spacer(1, 10),
]

# ── 7. Resetting ─────────────────────────────────────────────────────────────
story += [
    h1("7.  Starting Over"),
    p("At any point after the allocation has started, you can click "
      "<b>↺ Reset to Round 1</b> in Section 2 to clear all assignments and go back "
      "to the Round-1 picks panel. Your uploaded data files are kept."),
    Spacer(1, 6),
    note("To use completely different data files, simply upload new files — "
         "the app will reload automatically."),
    Spacer(1, 10),
]

# ── 8. Replay slider ─────────────────────────────────────────────────────────
story += [
    h1("8.  Replay Slider  (Section 5)"),
    p("The <b>Allocation replay</b> panel at the bottom of the page contains a slider "
      "that lets you step through every decision made during the allocation:"),
    b("Drag the slider left to go back to an earlier step."),
    b("Drag it right to move forward."),
    b("Click <b>▶ Play</b> to animate through all steps automatically."),
    Spacer(1, 6),
    p("Four tabs show different views of the selected step:"),
    col_table(
        ["Tab", "What it shows"],
        [
            ["Assignment Graph", "A diagram connecting students (left) to advisors (right). "
                                 "The most recent assignment is highlighted in purple."],
            ["Advisor Loads",    "A bar chart of how many students each advisor has at that step."],
            ["Statistics",       "A summary table of assignment rates by tier."],
            ["Step Log",         "A list of all events up to the selected step."],
        ],
        col_widths=[4*cm, 11.7*cm],
    ),
    Spacer(1, 10),
]

# ── 9. Troubleshooting ───────────────────────────────────────────────────────
story += [
    h1("9.  Troubleshooting"),
    col_table(
        ["Problem", "What to do"],
        [
            ["File upload shows an error",
             "Check that the required column names are present (student_id, name, cpi, pref_1 "
             "for students; faculty_id, name for faculty). Column names are not case-sensitive."],
            ["A student preference ID is not recognised",
             "The faculty_id values in the student file must exactly match those in the faculty "
             "file. Check for typos or extra spaces."],
            ["All advisors appear greyed out for a student",
             "All eligible advisors for this student have reached their maximum load. "
             "The cap is automatically extended to include more advisors."],
            ["The app is slow or unresponsive",
             "Refresh the browser page. If the problem persists, restart the app server "
             "and reload the page."],
        ],
        col_widths=[5*cm, 10.7*cm],
    ),
    Spacer(1, 10),
]

# Footer note
story += [
    hr(),
    Paragraph("For technical support or to report a bug, contact your system administrator.",
              Note),
]

# ---------------------------------------------------------------------------
# Build PDF
# ---------------------------------------------------------------------------
import os
os.makedirs("docs", exist_ok=True)

doc = SimpleDocTemplate(
    OUT,
    pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=2.2*cm, bottomMargin=2*cm,
    title="Allocator User Manual",
    author="Allocator",
)
doc.build(story)
print(f"Written: {OUT}")
