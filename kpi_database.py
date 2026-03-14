import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("kpi_tracker.db")

CATEGORIES = ["Safety", "Quality", "Productivity", "4S+SD"]
CELLS = ["Small Parts", "Medium", "Large", "Propeller", "Battery"]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS improvement_actions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            title               TEXT NOT NULL,
            category            TEXT NOT NULL,
            cell                TEXT NOT NULL,
            kpi_name            TEXT NOT NULL,
            kpi_unit            TEXT NOT NULL,
            current_condition   TEXT NOT NULL,
            target_condition    TEXT NOT NULL,
            baseline_value      REAL NOT NULL,
            target_value        REAL NOT NULL,
            improvement_direction TEXT DEFAULT 'higher_is_better',
            owner               TEXT NOT NULL,
            start_date          TEXT NOT NULL,
            target_date         TEXT,
            status              TEXT DEFAULT 'Active',
            notes               TEXT,
            created_at          TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_measurements (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id           INTEGER NOT NULL,
            measure_date        TEXT NOT NULL,
            value               REAL NOT NULL,
            recorded_by         TEXT NOT NULL,
            notes               TEXT,
            FOREIGN KEY (action_id) REFERENCES improvement_actions(id),
            UNIQUE(action_id, measure_date)
        );
        """)


# ── Improvement Actions ──────────────────────────────────────────────────────

def add_improvement_action(action: dict):
    ts = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO improvement_actions
               (title, category, cell, kpi_name, kpi_unit,
                current_condition, target_condition,
                baseline_value, target_value, improvement_direction,
                owner, start_date, target_date, status, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (action["title"], action["category"], action["cell"],
             action["kpi_name"], action["kpi_unit"],
             action["current_condition"], action["target_condition"],
             action["baseline_value"], action["target_value"],
             action.get("improvement_direction", "higher_is_better"),
             action["owner"], action["start_date"],
             action.get("target_date"), action.get("status", "Active"),
             action.get("notes", ""), ts)
        )


def get_improvement_actions(category=None, cell=None, status=None):
    q, params = "SELECT * FROM improvement_actions WHERE 1=1", []
    if category and category != "All":
        q += " AND category=?"; params.append(category)
    if cell and cell != "All":
        q += " AND cell=?"; params.append(cell)
    if status and status != "All":
        q += " AND status=?"; params.append(status)
    q += " ORDER BY created_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def update_improvement_action(action_id: int, status: str, notes: str = ""):
    with get_conn() as conn:
        conn.execute(
            "UPDATE improvement_actions SET status=?, notes=? WHERE id=?",
            (status, notes, action_id)
        )


# ── Daily Measurements ───────────────────────────────────────────────────────

def add_daily_measurement(action_id: int, measure_date: str, value: float,
                          recorded_by: str, notes: str = ""):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO daily_measurements
               (action_id, measure_date, value, recorded_by, notes)
               VALUES (?,?,?,?,?)
               ON CONFLICT(action_id, measure_date) DO UPDATE SET
                   value=excluded.value,
                   recorded_by=excluded.recorded_by,
                   notes=excluded.notes""",
            (action_id, measure_date, value, recorded_by, notes)
        )


def get_daily_measurements(action_id: int):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM daily_measurements WHERE action_id=? ORDER BY measure_date",
            (action_id,)
        ).fetchall()]


def get_measurements_with_actions(category=None, cell=None):
    q = """SELECT m.*, a.title, a.kpi_name, a.kpi_unit, a.baseline_value,
                  a.target_value, a.cell, a.category, a.improvement_direction,
                  a.current_condition, a.target_condition
           FROM daily_measurements m
           JOIN improvement_actions a ON m.action_id = a.id
           WHERE 1=1"""
    params = []
    if category and category != "All":
        q += " AND a.category=?"; params.append(category)
    if cell and cell != "All":
        q += " AND a.cell=?"; params.append(cell)
    q += " ORDER BY m.measure_date"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_latest_measurement(action_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM daily_measurements WHERE action_id=? ORDER BY measure_date DESC LIMIT 1",
            (action_id,)
        ).fetchone()
        return dict(row) if row else None
