import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(“audit_tracker.db”)

def get_conn():
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
return conn

def init_db():
with get_conn() as conn:
conn.executescript(”””
CREATE TABLE IF NOT EXISTS audits (
audit_id            TEXT PRIMARY KEY,
timestamp           TEXT NOT NULL,
auditor             TEXT NOT NULL,
cell                TEXT NOT NULL,
week                INTEGER NOT NULL,
phase_label         TEXT NOT NULL,
notes               TEXT,
answered_yes        INTEGER,
answered_no         INTEGER,
skipped_na          INTEGER,
total_questions     INTEGER,
standardization_score REAL,
passed              INTEGER
);

```
    CREATE TABLE IF NOT EXISTS audit_answers (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_id        TEXT NOT NULL,
        section         TEXT NOT NULL,
        question_id     TEXT NOT NULL,
        question_text   TEXT NOT NULL,
        answer          INTEGER,          -- 1=Yes, 0=No, NULL=N/A
        FOREIGN KEY (audit_id) REFERENCES audits(audit_id)
    );

    CREATE TABLE IF NOT EXISTS action_items (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_id        TEXT,             -- nullable: can be standalone
        cell            TEXT NOT NULL,
        section         TEXT,
        description     TEXT NOT NULL,
        raised_by       TEXT NOT NULL,
        raised_date     TEXT NOT NULL,
        due_date        TEXT,
        status          TEXT DEFAULT 'Open',  -- Open | In Progress | Closed
        closed_date     TEXT,
        closed_by       TEXT,
        notes           TEXT
    );
    """)
```

# ── Audits ────────────────────────────────────────────────────────────────────

def save_audit(result: dict):
s = result[“summary”]
with get_conn() as conn:
conn.execute(
“INSERT INTO audits VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)”,
(result[“audit_id”], result[“timestamp”], result[“auditor”],
result[“cell”], result[“week”], result[“phase_label”],
result.get(“notes”, “”), s[“answered_yes”], s[“answered_no”],
s[“skipped_na”], s[“total_questions”],
s[“standardization_score”], 1 if s[“passed”] else 0)
)
for section, data in result[“sections”].items():
for qid, (qtext, ans) in data[“qa”].items():
db_ans = 1 if ans is True else (0 if ans is False else None)
conn.execute(
“INSERT INTO audit_answers (audit_id,section,question_id,question_text,answer) VALUES (?,?,?,?,?)”,
(result[“audit_id”], section, qid, qtext, db_ans)
)

def get_audits(cell=None, week=None):
q, params = “SELECT * FROM audits WHERE 1=1”, []
if cell:  q += “ AND cell=?”;  params.append(cell)
if week:  q += “ AND week=?”;  params.append(week)
q += “ ORDER BY timestamp DESC”
with get_conn() as conn:
return [dict(r) for r in conn.execute(q, params).fetchall()]

def get_audit_answers(audit_id: str):
with get_conn() as conn:
return [dict(r) for r in conn.execute(
“SELECT * FROM audit_answers WHERE audit_id=? ORDER BY section, question_id”,
(audit_id,)
).fetchall()]

# ── Action Items ──────────────────────────────────────────────────────────────

def get_action_items(cell=None, status=None):
q, params = “SELECT * FROM action_items WHERE 1=1”, []
if cell and cell != “All”:   q += “ AND cell=?”;   params.append(cell)
if status and status != “All”: q += “ AND status=?”; params.append(status)
q += “ ORDER BY raised_date DESC”
with get_conn() as conn:
return [dict(r) for r in conn.execute(q, params).fetchall()]

def add_action_item(item: dict):
with get_conn() as conn:
conn.execute(
“INSERT INTO action_items (audit_id,cell,section,description,raised_by,raised_date,due_date,status,notes) VALUES (?,?,?,?,?,?,?,?,?)”,
(item.get(“audit_id”), item[“cell”], item.get(“section”),
item[“description”], item[“raised_by”], item[“raised_date”],
item.get(“due_date”), item.get(“status”, “Open”), item.get(“notes”, “”))
)

def update_action_item(item_id: int, status: str, closed_by: str = “”, notes: str = “”):
closed_date = datetime.now(timezone.utc).isoformat()[:10] if status == “Closed” else None
with get_conn() as conn:
conn.execute(
“UPDATE action_items SET status=?, closed_date=?, closed_by=?, notes=? WHERE id=?”,
(status, closed_date, closed_by, notes, item_id)
)
