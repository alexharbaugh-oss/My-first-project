import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("kpi_tracker.db")

# FMDS categories matching the board
CATEGORIES = ["Safety", "Quality", "Productivity", "4S+SD"]

# Priority levels from the action tracker
PRIORITIES = ["High", "Med", "Low", "No Action"]

# Status values from the action tracker
STATUSES = ["Not Started", "In-Progress", "Study Effectiveness", "Identified", "Completed", "On Hold"]

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
                detailed_actions, notes, start_date, due_date, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["title"], data["category"], data.get("priority", "Med"),
             data.get("status", "Not Started"), data["owner"],
             data.get("support_team", ""), data.get("management_tool", ""),
             data.get("current_condition", ""), data.get("target_condition", ""),
             data.get("detailed_actions", ""), data.get("notes", ""),
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
                "start_date", "due_date", "completed_date"]:
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
