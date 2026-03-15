import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("kpi_tracker.db")

# FMDS categories matching the board
CATEGORIES = ["Safety", "Quality", "Productivity", "4S+SD"]

# Priority levels from the action tracker
PRIORITIES = ["High", "Med", "Low", "No Action"]

# Status values from the action tracker
STATUSES = ["Not Started", "In-Progress", "Study Effectiveness", "Identified",
            "Support Needed", "Completed", "On Hold"]

# Work stoppage cause codes from FMDS Pareto
STOPPAGE_CODES = [
    "RECUT - Tech Error",
    "STEP Incomplete",
    "RECUT - Missing Ply",
    "TECHNICIAN ERROR",
    "RECUT - Material Defect",
    "RECUT - Missing Ply From Kit",
    "RECUT - Expired Material",
    "RECUT / REWORK - Workmanship",
    "WORKCELL ADJUSTMENT",
    "MWI - Production Request",
    "TOOLING - Not Available",
    "BATTERY SLEEVES",
    "REWORK - Bagging",
    "REWORK - Ply Adjustment",
    "Clarification",
    "NOT A MFG ENG STOPPAGE",
    "Other",
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        -- Improvement actions (mirrors Alex Harbaugh Action Tracker)
        CREATE TABLE IF NOT EXISTS actions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            title               TEXT NOT NULL,
            category            TEXT NOT NULL,
            priority            TEXT NOT NULL DEFAULT 'Med',
            status              TEXT NOT NULL DEFAULT 'Not Started',
            owner               TEXT NOT NULL,
            support_team        TEXT,
            management_tool     TEXT,
            current_condition   TEXT,
            target_condition    TEXT,
            detailed_actions    TEXT,
            notes               TEXT,
            start_date          TEXT,
            due_date            TEXT,
            completed           INTEGER NOT NULL DEFAULT 0,
            completed_date      TEXT,
            created_at          TEXT NOT NULL
        );

        -- Daily KPI measurements tied to actions
        -- This is the core: current condition vs target, tracked daily
        CREATE TABLE IF NOT EXISTS daily_kpis (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id       INTEGER NOT NULL,
            measure_date    TEXT NOT NULL,
            kpi_name        TEXT NOT NULL,
            kpi_unit        TEXT NOT NULL DEFAULT '',
            value           REAL NOT NULL,
            target_value    REAL,
            baseline_value  REAL,
            notes           TEXT,
            recorded_by     TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (action_id) REFERENCES actions(id),
            UNIQUE(action_id, measure_date, kpi_name)
        );

        -- Work stoppage events (from FMDS board)
        CREATE TABLE IF NOT EXISTS work_stoppages (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            stoppage_date       TEXT NOT NULL,
            cause_code          TEXT NOT NULL,
            hours_lost          REAL DEFAULT 0,
            description         TEXT,
            corrective_action   TEXT,
            owner               TEXT,
            status              TEXT DEFAULT 'Open',
            notes               TEXT
        );
        """)


# ── Actions ──────────────────────────────────────────────────────────────────

def add_action(data: dict):
    ts = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO actions
               (title, category, priority, status, owner, support_team,
                management_tool, current_condition, target_condition,
                detailed_actions, notes, completed, start_date, due_date, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["title"], data["category"], data.get("priority", "Med"),
             data.get("status", "Not Started"), data["owner"],
             data.get("support_team", ""), data.get("management_tool", ""),
             data.get("current_condition", ""), data.get("target_condition", ""),
             data.get("detailed_actions", ""), data.get("notes", ""),
             1 if data.get("completed") else 0,
             data.get("start_date", ""), data.get("due_date", ""), ts)
        )
        return cur.lastrowid


def get_actions(category=None, status=None, priority=None):
    q, params = "SELECT * FROM actions WHERE 1=1", []
    if category and category != "All":
        q += " AND category=?"; params.append(category)
    if status and status != "All":
        q += " AND status=?"; params.append(status)
    if priority and priority != "All":
        q += " AND priority=?"; params.append(priority)
    q += " ORDER BY created_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_action(action_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        return dict(row) if row else None


def update_action(action_id: int, data: dict):
    fields = []
    params = []
    for key in ["title", "category", "priority", "status", "owner",
                "support_team", "management_tool", "current_condition",
                "target_condition", "detailed_actions", "notes",
                "completed", "start_date", "due_date", "completed_date"]:
        if key in data:
            fields.append(f"{key}=?")
            params.append(data[key])
    if not fields:
        return
    params.append(action_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE actions SET {', '.join(fields)} WHERE id=?", params
        )


def delete_action(action_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM daily_kpis WHERE action_id=?", (action_id,))
        conn.execute("DELETE FROM actions WHERE id=?", (action_id,))


# ── Daily KPI Measurements ──────────────────────────────────────────────────

def add_daily_kpi(action_id: int, measure_date: str, kpi_name: str,
                  value: float, target_value: float = None,
                  baseline_value: float = None, kpi_unit: str = "",
                  notes: str = "", recorded_by: str = ""):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO daily_kpis
               (action_id, measure_date, kpi_name, kpi_unit, value,
                target_value, baseline_value, notes, recorded_by)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(action_id, measure_date, kpi_name) DO UPDATE SET
                   value=excluded.value,
                   target_value=excluded.target_value,
                   baseline_value=excluded.baseline_value,
                   kpi_unit=excluded.kpi_unit,
                   notes=excluded.notes,
                   recorded_by=excluded.recorded_by""",
            (action_id, measure_date, kpi_name, kpi_unit, value,
             target_value, baseline_value, notes, recorded_by)
        )


def get_daily_kpis(action_id: int, kpi_name: str = None):
    q = "SELECT * FROM daily_kpis WHERE action_id=?"
    params = [action_id]
    if kpi_name:
        q += " AND kpi_name=?"; params.append(kpi_name)
    q += " ORDER BY measure_date"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_kpi_names_for_action(action_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT kpi_name FROM daily_kpis WHERE action_id=? ORDER BY kpi_name",
            (action_id,)
        ).fetchall()
        return [r["kpi_name"] for r in rows]


def get_latest_kpi(action_id: int, kpi_name: str):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM daily_kpis
               WHERE action_id=? AND kpi_name=?
               ORDER BY measure_date DESC LIMIT 1""",
            (action_id, kpi_name)
        ).fetchone()
        return dict(row) if row else None


def get_all_latest_kpis():
    """Get the latest KPI reading for every action that has measurements."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT d.*, a.title, a.category, a.priority, a.status as action_status,
                   a.owner, a.current_condition, a.target_condition
            FROM daily_kpis d
            JOIN actions a ON d.action_id = a.id
            WHERE d.measure_date = (
                SELECT MAX(d2.measure_date) FROM daily_kpis d2
                WHERE d2.action_id = d.action_id AND d2.kpi_name = d.kpi_name
            )
            ORDER BY a.category, a.title
        """).fetchall()
        return [dict(r) for r in rows]


# ── Work Stoppages ───────────────────────────────────────────────────────────

def add_work_stoppage(data: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO work_stoppages
               (stoppage_date, cause_code, hours_lost, description,
                corrective_action, owner, status, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (data["stoppage_date"], data["cause_code"],
             data.get("hours_lost", 0), data.get("description", ""),
             data.get("corrective_action", ""), data.get("owner", ""),
             data.get("status", "Open"), data.get("notes", ""))
        )


def get_work_stoppages(status=None):
    q, params = "SELECT * FROM work_stoppages WHERE 1=1", []
    if status and status != "All":
        q += " AND status=?"; params.append(status)
    q += " ORDER BY stoppage_date DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_stoppage_pareto():
    """Get hours lost by cause code for Pareto chart."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT cause_code, SUM(hours_lost) as total_hours, COUNT(*) as count
            FROM work_stoppages
            GROUP BY cause_code
            ORDER BY total_hours DESC
        """).fetchall()
        return [dict(r) for r in rows]


def seed_initial_data():
    """Pre-populate with Alex Harbaugh's real improvement action items."""
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        if count > 0:
            return  # Already seeded

    actions = [
        {
            "title": "Standardized Audit for Hand Layup SOPs",
            "category": "Quality",
            "priority": "Med",
            "status": "Identified",
            "owner": "Alex H.",
            "support_team": "Elias C. / Joel K.",
            "management_tool": "Audit, KPI, Implementation Tracker",
            "detailed_actions": (
                "1) Audit 1 SOP x Week and submit notes to Joel Kotila for review\n"
                "2) Identify part build to be identified and audit through entire process\n"
                "3) Print out SOP and highlight key actions / deviations from process\n"
                "4) Identify retraining opportunities and review SOPs required to be updated\n"
                "5) Retrain group"
            ),
            "notes": "Think: How do I track effectivity of project to prevent reoccurrence",
            "completed": False,
        },
        {
            "title": "Composi track updated - fix SOP",
            "category": "Quality",
            "priority": "Med",
            "status": "In-Progress",
            "owner": "Alex H.",
            "support_team": "Harold",
            "detailed_actions": (
                "1) Pull current SOP and review with Harold\n"
                "2) Needed changes/updates\n"
                "3) Submit revision for review and approval\n"
                "4) Incorporate feedback"
            ),
            "completed": False,
        },
        {
            "title": "Visual control for tape dispensers - standardize shop visual standard 4S",
            "category": "4S+SD",
            "priority": "High",
            "status": "In-Progress",
            "owner": "Alex H.",
            "support_team": "Hirvin / TLS",
            "management_tool": "Dojo examples",
            "detailed_actions": (
                "1) Audit current tape dispenser locations across all cells\n"
                "2) Define standard placement per workstation\n"
                "3) Create visual standard (photo/diagram) 3/31\n"
                "4) Install trays and labels at each station 3/31\n"
                "5) Train team on standard 3/31\n"
                "6) Verify compliance with daily checks 4/1"
            ),
            "notes": "TICKET SUBMITTED 3/12. Create list of items for visual standards. Capture that change, audit to it. Take the list of fixtures to standard / visual list of fixture per cell, create standards.",
            "completed": False,
        },
        {
            "title": "Turn overs",
            "category": "Productivity",
            "priority": "High",
            "status": "In-Progress",
            "owner": "Alex H.",
            "management_tool": "Review sheets at day - how many were missed each day - KPI current vs now. Act and results tracker sheet FMDS",
            "detailed_actions": (
                "1) Rev C released 2/18/26 - verify rollout to all shifts\n"
                "2) Establish workflow for dayshift\n"
                "3) Establish holders / placement of paper\n"
                "4) Standardize turnover process between shifts\n"
                "5) Train all TLs on new workflow\n"
                "6) Audit compliance across shifts\n"
                "7) Document standard"
            ),
            "notes": "Rev C released 2/18/26. Standardize between shifts - recuts",
            "completed": False,
        },
        {
            "title": "Start of shift checklist",
            "category": "Productivity",
            "priority": "Med",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Draft checklist content with key start-of-shift items\n"
                "2) Review draft with TLs for feedback\n"
                "3) Format and print checklist\n"
                "4) Trial run for 1 week and gather input\n"
                "5) Finalize checklist and implement across all shifts"
            ),
            "completed": False,
        },
        {
            "title": "TL end of shift check list",
            "category": "Productivity",
            "priority": "Low",
            "status": "Study Effectiveness",
            "owner": "Alex H.",
            "management_tool": "Study / follow up",
            "detailed_actions": (
                "1) Study current end-of-shift checklist effectiveness\n"
                "2) Follow up with TLs on usage and gaps\n"
                "3) Revise checklist based on feedback\n"
                "4) Reissue updated checklist\n"
                "5) Monitor adoption over 2 weeks"
            ),
            "completed": True,
        },
        {
            "title": "Update S-lvls",
            "category": "Quality",
            "priority": "High",
            "status": "In-Progress",
            "owner": "Alex H.",
            "completed": False,
        },
        {
            "title": "Visual control sealed kits",
            "category": "4S+SD",
            "priority": "High",
            "status": "Study Effectiveness",
            "owner": "Alex H.",
            "support_team": "Mag on prod.",
            "management_tool": "Study / follow up",
            "detailed_actions": (
                "1) Define visual standard for sealed kits (labels, color coding)\n"
                "2) Create visual indicators for Mag on prod.\n"
                "3) Gather feedback and adjust\n"
                "4) Verify with team and audit weekly"
            ),
            "completed": True,
        },
        {
            "title": "Kit handling procedures",
            "category": "Quality",
            "priority": "Med",
            "status": "Study Effectiveness",
            "owner": "Alex / Irie",
            "management_tool": "Stand up shout out - study / follow up",
            "detailed_actions": (
                "1) Document current kit handling steps with Alex/Irie\n"
                "2) Identify pain points and inconsistencies\n"
                "3) Draft standardized handling procedure\n"
                "4) Review and finalize with team\n"
                "5) Stand up shout out to communicate new procedure\n"
                "6) Monitor compliance"
            ),
            "completed": False,
        },
        {
            "title": "Laser target return process",
            "category": "Quality",
            "priority": "Med",
            "status": "Study Effectiveness",
            "owner": "Alex H.",
            "management_tool": "Stand up shout out",
            "detailed_actions": (
                "1) Map current laser target return process\n"
                "2) Define standard return procedure and verification method\n"
                "3) Stand up shout out to communicate process\n"
                "4) Create how-to-verify checklist\n"
                "5) Audit return compliance weekly"
            ),
            "notes": "How to verify",
            "completed": False,
        },
        {
            "title": "4S+SD the admin area",
            "category": "4S+SD",
            "priority": "Low",
            "status": "In-Progress",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Sort - remove unnecessary items from admin area\n"
                "2) Set in order - organize remaining items logically\n"
                "3) Shine - deep clean the area\n"
                "4) Standardize - create layout standard and labels\n"
                "5) Sustain - implement weekly 5S audit checks"
            ),
            "completed": False,
        },
        {
            "title": "Standardize HL GL quality RCAs / investigation focus time",
            "category": "Quality",
            "priority": "Med",
            "status": "In-Progress",
            "owner": "Joel",
            "management_tool": "Change KPIs",
            "detailed_actions": (
                "1) Review current RCA process with Joel\n"
                "2) Define standard investigation template and timeline"
            ),
            "completed": False,
        },
        {
            "title": "Conduct motion studies: tape, seal tape, bagging supplies, and materials",
            "category": "Productivity",
            "priority": "Med",
            "status": "In-Progress",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Select target workstations for study\n"
                "2) Record current motions and cycle times\n"
                "3) Analyze for waste and unnecessary movement\n"
                "4) Propose optimized placement and layout\n"
                "5) Trial new layout for 1 week\n"
                "6) Measure improvement and finalize"
            ),
            "notes": "Optimize placement and reduce operator movement",
            "completed": False,
        },
        {
            "title": "Visual control of parts on track / team members getting support",
            "category": "Productivity",
            "priority": "Med",
            "status": "In-Progress",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Map current part flow on track and identify gaps\n"
                "2) Design visual board/system for part tracking\n"
                "3) Define visual indicator for team members needing support\n"
                "4) Install visual controls\n"
                "5) Train all team members\n"
                "6) Monitor effectiveness and adjust"
            ),
            "completed": False,
        },
        {
            "title": "HL TM 'Hardest Part of Job'",
            "category": "Productivity",
            "priority": "Low",
            "status": "In-Progress",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Survey team members on their hardest tasks\n"
                "2) Compile and rank responses by frequency\n"
                "3) Identify top 3 actionable improvement areas\n"
                "4) Develop solutions for each\n"
                "5) Implement improvements and follow up"
            ),
            "completed": False,
        },
        {
            "title": "Standardize support needed call times - 5 mins of struggle rule",
            "category": "Productivity",
            "priority": "No Action",
            "status": "In-Progress",
            "owner": "Alex H.",
            "management_tool": "Stand up shout out",
            "detailed_actions": (
                "1) Define standard call-for-support time threshold (5 min rule)\n"
                "2) Stand up shout out to communicate standard\n"
                "3) Create visual reminder at workstations\n"
                "4) Monitor response times and compliance\n"
                "5) Reward timely support-seeking behavior"
            ),
            "notes": "Reward stopping and getting help",
            "completed": False,
        },
        {
            "title": "Simple check sheets - to-do/completed rows - update audits",
            "category": "Quality",
            "priority": "Med",
            "status": "In-Progress",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Design simple check sheet template with to-do/completed rows\n"
                "2) Pilot with one audit type\n"
                "3) Get TL feedback on usability\n"
                "4) Revise and standardize format\n"
                "5) Roll out to all audit types\n"
                "6) Due: Friday 2/27 for initial draft\n"
                "7) Need start of shift!"
            ),
            "notes": (
                "START OF SHIFT: Attendance, Tools, Material, Resources placed properly, People, Molds\n"
                "END OF SHIFT: Cleaning 4S, Production board, Turnovers, Audits, Kits sealed, "
                "Lasers off, Equipment off, Pressure of molds upkeep\n"
                "MID-DAY: Safety, Quality of teams work, Productivity of teams work, "
                "Work stoppages, Behind conditions, Feedback to team members and MEs"
            ),
            "completed": False,
        },
        {
            "title": "Work cell change overs",
            "category": "Productivity",
            "priority": "Med",
            "status": "In-Progress",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Time current changeover process for each cell\n"
                "2) Identify internal vs. external changeover tasks\n"
                "3) Develop standard changeover procedure (SMED approach)\n"
                "4) Train team on new procedure\n"
                "5) Time new process and compare improvement"
            ),
            "notes": "Due Friday 2/27",
            "completed": False,
        },
        {
            "title": "SOP for redlines",
            "category": "Quality",
            "priority": "Med",
            "status": "Support Needed",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Collect all pending SOP redlines\n"
                "2) Prioritize by impact and urgency\n"
                "3) Draft SOP updates for each redline\n"
                "4) Route for support/approval (SUPPORT NEEDED)\n"
                "5) Publish and distribute updated SOPs\n"
                "6) Communicate changes to team"
            ),
            "completed": False,
        },
        {
            "title": "Weekend work bot fix",
            "category": "Productivity",
            "priority": "Low",
            "status": "Completed",
            "owner": "Alex H.",
            "management_tool": "Study / follow up",
            "detailed_actions": "COMPLETED - No further actions needed",
            "completed": True,
        },
        {
            "title": "Team meeting",
            "category": "Productivity",
            "priority": "Med",
            "status": "In-Progress",
            "owner": "Alex H.",
            "notes": (
                "MWI feedback, Goals / productivity, Safety highlight safety glasses, "
                "Pass down logs, MWI detailed instructions"
            ),
            "completed": False,
        },
        {
            "title": "New hire prep",
            "category": "Productivity",
            "priority": "High",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Create new hire onboarding checklist\n"
                "2) Prepare training materials and schedule\n"
                "3) Follow up after 30 days for feedback"
            ),
            "completed": False,
        },
        {
            "title": "Rework - Workmanship RCA, interview team members",
            "category": "Quality",
            "priority": "High",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Floor interviews with team members about workmanship issues\n"
                "2) Document top rework causes and biggest technique pain points\n"
                "3) Root cause analysis on top 3 issues\n"
                "4) Develop corrective actions for each\n"
                "5) Implement corrective actions\n"
                "6) Verify effectiveness after 2 weeks"
            ),
            "notes": "Interview team members about workmanship recuts and biggest technique pain points",
            "completed": False,
        },
        {
            "title": "Documenting tool layup area and cell #, bagging station trials",
            "category": "Productivity",
            "priority": "Med",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Map current tool layup areas by cell number\n"
                "2) Group tools by ergonomic part families (Small, Med, Lrg)\n"
                "3) Document bagging station trial sheet\n"
                "4) Run trials and collect data\n"
                "5) Summarize findings and recommend standard layout"
            ),
            "notes": "Grouped with ergonomic part families",
            "completed": False,
        },
        {
            "title": "New work stoppage dash",
            "category": "Quality",
            "priority": "Low",
            "status": "Not Started",
            "owner": "Alex H.",
            "completed": False,
        },
        {
            "title": "Create document for TLs to track plies missing from kits & kit swaps",
            "category": "Quality",
            "priority": "High",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Define data fields needed (part number, ply count, kit ID, details)\n"
                "2) Draft tracking document/spreadsheet\n"
                "3) Review with Team Leads for input\n"
                "4) Pilot for 2 weeks\n"
                "5) Finalize and deploy to all TLs"
            ),
            "completed": False,
        },
        {
            "title": "Conduct process study / Gemba walk on leg fairing bagging",
            "category": "Quality",
            "priority": "Med",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Schedule Gemba walk on leg fairing bagging process\n"
                "2) Observe and document current state (cycle time, steps, waste)\n"
                "3) Identify bottlenecks and improvement opportunities\n"
                "4) Develop improvement recommendations\n"
                "5) Present findings to leadership"
            ),
            "completed": False,
        },
        {
            "title": "Establish reliable verification method for instructions compliance",
            "category": "Quality",
            "priority": "Med",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Audit current instruction compliance across all cells\n"
                "2) Define verification checkpoints for critical steps\n"
                "3) Develop conforming steps checklist\n"
                "4) Train team on verification process\n"
                "5) Update Work Instructions to enforce conforming steps\n"
                "6) Audit weekly for compliance"
            ),
            "completed": False,
        },
        {
            "title": "Real time quality tracking",
            "category": "Quality",
            "priority": "Med",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Define key quality metrics to track in real time\n"
                "2) Research tracking tool/dashboard options\n"
                "3) Set up real-time tracking system\n"
                "4) Train TLs on data entry and monitoring\n"
                "5) Review data weekly and adjust as needed"
            ),
            "completed": False,
        },
        {
            "title": "Common Defect Visual Posted at Table",
            "category": "Quality",
            "priority": "No Action",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Compile top common defects with photos/examples\n"
                "2) Design visual aid poster for each defect type\n"
                "3) Review with quality team for accuracy\n"
                "4) Print and post at each work table\n"
                "5) Brief team during stand up on defect visuals"
            ),
            "completed": False,
        },
        {
            "title": "Rotating/lifting table for spinners - ergonomic part families",
            "category": "Safety",
            "priority": "Med",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Research rotating/lifting table options for spinners\n"
                "2) Research electric lift tables to replace green lifts\n"
                "3) Get vendor quotes for equipment\n"
                "4) Evaluate ergonomic part families (Small, Med, Lrg)\n"
                "5) Submit capital request\n"
                "6) Plan installation timeline"
            ),
            "completed": False,
        },
        {
            "title": "Trial lifting table in small parts to standardize cell",
            "category": "Safety",
            "priority": "Med",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Set up trial lifting table in small parts cell\n"
                "2) Collect operator feedback over 2-week trial\n"
                "3) Measure ergonomic and productivity impact\n"
                "4) Document results and present to leadership\n"
                "5) Decide on full rollout based on trial data"
            ),
            "completed": False,
        },
        {
            "title": "Daisy-chain prevention!!!",
            "category": "Safety",
            "priority": "High",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Identify all current daisy-chain risks in work areas\n"
                "2) Develop daisy-chain prevention standard/policy\n"
                "3) Communicate standard to all teams\n"
                "4) Install preventive measures (power strips, outlet management)\n"
                "5) Audit and enforce compliance monthly"
            ),
            "completed": False,
        },
        {
            "title": "Critical step second party check offs",
            "category": "Quality",
            "priority": "High",
            "status": "Not Started",
            "owner": "Alex H.",
            "detailed_actions": (
                "1) Identify all critical steps requiring second-party verification\n"
                "2) Design check-off form/document\n"
                "3) Train team on second-party check process\n"
                "4) Implement check-offs on production floor\n"
                "5) Audit compliance and adjust as needed"
            ),
            "completed": False,
        },
    ]

    for a in actions:
        add_action(a)


def update_work_stoppage(stoppage_id: int, data: dict):
    fields, params = [], []
    for key in ["status", "corrective_action", "owner", "notes"]:
        if key in data:
            fields.append(f"{key}=?")
            params.append(data[key])
    if not fields:
        return
    params.append(stoppage_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE work_stoppages SET {', '.join(fields)} WHERE id=?", params
        )
