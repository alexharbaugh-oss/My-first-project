    import streamlit as st
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("audit_tracker.db")

CELLS = ["Small Parts", "Medium", "Large", "Propeller", "Battery"]

# ── Phase guidance content ─────────────────────────────────────────────────────

PHASE_GUIDE = {
    "Sort": {
        "objective": "Remove everything that does not belong in the layup cell. If in doubt, red-tag it.",
        "steps": [
            "Gather your team and walk the entire cell together.",
            "Identify every item in the cell: tools, consumables, materials, personal items, fixtures.",
            "Ask for each item: Is it needed here? Is it needed now? Is it in the right quantity?",
            "Place a red tag on anything that cannot be justified. Record it on the red tag log.",
            "Move red-tagged items to the quarantine zone within 24 hours.",
            "Photograph the cell before and after. Attach photos to this record.",
            "Conduct a final walkthrough with your supervisor to confirm the Sort is complete.",
        ],
        "checklist": [
            "Full team briefing completed",
            "All items in cell identified and evaluated",
            "Red tags applied to all non-essential items",
            "Red tag log completed and submitted",
            "Quarantine zone populated and labelled",
            "Before photo taken",
            "After photo taken",
            "Supervisor sign-off obtained",
        ],
        "board_element": "Post the red tag log and quarantine zone location map on the management board.",
        "photo_prompts": [
            "Full cell overview - before Sort",
            "Full cell overview - after Sort",
            "Quarantine zone with red-tagged items",
            "Red tag log document",
        ],
    },
    "Set": {
        "objective": "A place for everything and everything in its place. Every item that belongs in the cell must have a clearly marked, permanent home.",
        "steps": [
            "List every tool, consumable and fixture that belongs in the cell post-Sort.",
            "Determine the best location for each item based on frequency of use and ergonomics.",
            "Create shadow boards or labelled storage for all tools.",
            "Label shelves, drawers and floor zones using the facility label standard.",
            "Mark floor locations for mobile equipment (carts, trolleys) with tape or paint.",
            "Create a visual map of the cell showing where everything lives.",
            "Train all operators on the new layout before sign-off.",
        ],
        "checklist": [
            "Inventory of cell items completed",
            "Optimal locations decided for all items",
            "Shadow boards or labelled storage created",
            "All shelves and zones labelled",
            "Floor markings applied",
            "Visual cell map created and posted",
            "Operator training completed",
            "Supervisor sign-off obtained",
        ],
        "board_element": "Post the visual cell map and tool inventory list on the management board.",
        "photo_prompts": [
            "Shadow board or tool storage - completed",
            "Floor markings and zone labels",
            "Labelled shelves and consumable storage",
            "Visual cell map posted on board",
        ],
    },
    "Shine": {
        "objective": "Clean the cell to a standard that makes defects and abnormalities immediately visible.",
        "steps": [
            "Deep clean all surfaces: layup table, floor, walls, fixtures and equipment.",
            "Remove all resin residue, debris and dust from every surface.",
            "Inspect equipment and tooling for damage or wear during cleaning.",
            "Log any defects found during the clean for follow-up.",
            "Create a daily cleaning schedule specifying who cleans what and when.",
            "Post the cleaning schedule in the cell and on the management board.",
            "Establish a cleaning standard with before/after reference photos.",
        ],
        "checklist": [
            "Deep clean of all surfaces completed",
            "Resin residue and debris removed",
            "Equipment and tooling inspected during clean",
            "Defects found during clean logged",
            "Daily cleaning schedule created",
            "Cleaning schedule posted in cell",
            "Cleaning standard photos taken and posted",
            "Supervisor sign-off obtained",
        ],
        "board_element": "Post the cleaning schedule and standard photos on the management board.",
        "photo_prompts": [
            "Layup table - cleaned to standard",
            "Floor - cleaned and free of debris",
            "Cleaning schedule posted in cell",
            "Cleaning standard reference photos",
        ],
    },
    "Standardize": {
        "objective": "Document and communicate the Sort, Set and Shine standards so anyone can maintain them without instruction.",
        "steps": [
            "Create visual work standards for the layup sequence specific to this cell.",
            "Photograph the correctly set-up cell and post the reference images at each station.",
            "Write and post the material traceability process at the relevant workstation.",
            "Confirm the audit checklist is accessible to all operators in the cell.",
            "Create and post the non-conformance reporting process.",
            "Review all posted standards with the full team.",
            "Obtain team lead and supervisor confirmation that standards are understood.",
        ],
        "checklist": [
            "Visual work standards created for layup sequence",
            "Reference photos posted at each station",
            "Material traceability process posted",
            "Audit checklist accessible to all operators",
            "NCR process posted in cell",
            "Standards review completed with full team",
            "Team lead confirmation obtained",
            "Supervisor sign-off obtained",
        ],
        "board_element": "Post the visual work standards index and NCR process on the management board.",
        "photo_prompts": [
            "Visual work standards posted at station",
            "Reference photos at each workstation",
            "Material traceability label example",
            "NCR process posted in cell",
        ],
    },
    "Self Discipline": {
        "objective": "Make 4S+SD a daily habit. The cell should maintain its standard without supervisor prompting.",
        "steps": [
            "Introduce the daily 5-minute tidy routine at shift start or end.",
            "Confirm all operators understand their responsibility to maintain the cell standard.",
            "Review previous audit findings with the team and confirm all actions are closed.",
            "Update the 4S+SD management board with the latest audit score.",
            "Identify any new team members and brief them on 4S+SD expectations.",
            "Conduct a team self-assessment against the audit checklist.",
            "Celebrate improvements and recognise consistent performers.",
        ],
        "checklist": [
            "Daily 5-minute tidy routine introduced",
            "All operators briefed on individual responsibilities",
            "Previous audit actions reviewed and closed",
            "Management board updated with latest score",
            "New team members briefed on 4S+SD",
            "Team self-assessment completed",
            "Team recognition completed",
            "Supervisor sign-off obtained",
        ],
        "board_element": "Post the latest audit score trend chart and open action item list on the management board.",
        "photo_prompts": [
            "Team during daily tidy routine",
            "Management board fully updated",
            "Audit score trend chart posted",
            "Team recognition posted on board",
        ],
    },
}

BOARD_ELEMENTS = [
    ("Cell Identity Header", "Cell name, responsible team lead, current week and phase."),
    ("Audit Score Chart", "Line chart showing score per week. Updated after each audit."),
    ("Current Phase Focus Card", "One-page summary of what the team is working on this week."),
    ("Open Action Items", "Visible list of all open findings with owner and due date."),
    ("Cleaning Schedule", "Who cleans what and when. Initialled daily by the responsible operator."),
    ("Visual Cell Map", "Diagram showing where everything in the cell belongs."),
    ("Standard Reference Photos", "Before/after photos showing the correct standard for this cell."),
    ("Red Tag Log", "Active during Sort week. Shows all red-tagged items and their status."),
    ("NCR Process Card", "How to raise a non-conformance in this cell."),
    ("Team Recognition", "Space to celebrate improvements and acknowledge contributors."),
]

# ── Database helpers ───────────────────────────────────────────────────────────

def init_guide_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS guide_checklists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cell        TEXT NOT NULL,
            phase       TEXT NOT NULL,
            item        TEXT NOT NULL,
            checked     INTEGER DEFAULT 0,
            checked_by  TEXT,
            checked_at  TEXT,
            UNIQUE(cell, phase, item)
        );

        CREATE TABLE IF NOT EXISTS board_tracker (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cell        TEXT NOT NULL,
            element     TEXT NOT NULL,
            complete    INTEGER DEFAULT 0,
            completed_by TEXT,
            completed_at TEXT,
            notes       TEXT,
            UNIQUE(cell, element)
        );

        CREATE TABLE IF NOT EXISTS guide_signoffs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cell        TEXT NOT NULL,
            phase       TEXT NOT NULL,
            signed_by   TEXT NOT NULL,
            signed_at   TEXT NOT NULL,
            notes       TEXT
        );
        """)

def get_checklist_state(cell, phase):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT item, checked, checked_by FROM guide_checklists WHERE cell=? AND phase=?",
            (cell, phase)
        ).fetchall()
        return {r[0]: {"checked": bool(r[1]), "by": r[2]} for r in rows}

def save_checklist_item(cell, phase, item, checked, checked_by):
    ts = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO guide_checklists (cell, phase, item, checked, checked_by, checked_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(cell, phase, item) DO UPDATE SET
                checked=excluded.checked,
                checked_by=excluded.checked_by,
                checked_at=excluded.checked_at
        """, (cell, phase, item, 1 if checked else 0, checked_by, ts))

def get_board_state(cell):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT element, complete, completed_by, notes FROM board_tracker WHERE cell=?",
            (cell,)
        ).fetchall()
        return {r[0]: {"complete": bool(r[1]), "by": r[2], "notes": r[3]} for r in rows}

def save_board_item(cell, element, complete, completed_by, notes):
    ts = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO board_tracker (cell, element, complete, completed_by, completed_at, notes)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(cell, element) DO UPDATE SET
                complete=excluded.complete,
                completed_by=excluded.completed_by,
                completed_at=excluded.completed_at,
                notes=excluded.notes
        """, (cell, element, 1 if complete else 0, completed_by, ts, notes))

def save_signoff(cell, phase, signed_by, notes):
    ts = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO guide_signoffs (cell, phase, signed_by, signed_at, notes) VALUES (?,?,?,?,?)",
            (cell, phase, signed_by, ts, notes)
        )

def get_signoffs(cell, phase):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT signed_by, signed_at, notes FROM guide_signoffs WHERE cell=? AND phase=? ORDER BY signed_at DESC",
            (cell, phase)
        ).fetchall()

def get_cell_progress(cell):
    phases = list(PHASE_GUIDE.keys())
    result = {}
    for phase in phases:
        items = PHASE_GUIDE[phase]["checklist"]
        state = get_checklist_state(cell, phase)
        done = sum(1 for i in items if state.get(i, {}).get("checked", False))
        result[phase] = {"done": done, "total": len(items), "pct": round(done / len(items) * 100)}
    board = get_board_state(cell)
    board_done = sum(1 for e, _ in BOARD_ELEMENTS if board.get(e, {}).get("complete", False))
    result["Management Board"] = {"done": board_done, "total": len(BOARD_ELEMENTS), "pct": round(board_done / len(BOARD_ELEMENTS) * 100)}
    return result

# ── Render function ────────────────────────────────────────────────────────────

def render_guide_tab():
    init_guide_db()

    wizard_tab, reference_tab, board_tab, progress_tab = st.tabs([
        "🧭 Implementation Wizard",
        "📖 Reference Library",
        "📋 Management Board Tracker",
        "📊 Cell Progress Overview",
    ])

    # ── WIZARD ────────────────────────────────────────────────────────────────
    with wizard_tab:
        st.subheader("Implementation Wizard")
        st.caption("Work through each phase for your cell. Check off items as you complete them and obtain a sign-off when the phase is done.")

        wc1, wc2, wc3 = st.columns(3)
        w_cell  = wc1.selectbox("Cell", CELLS, key="w_cell")
        w_phase = wc2.selectbox("Phase", list(PHASE_GUIDE.keys()), key="w_phase")
        w_user  = wc3.text_input("Your Name", placeholder="Team lead name", key="w_user")

        guide = PHASE_GUIDE[w_phase]

        st.divider()
        st.markdown("### Objective")
        st.info(guide["objective"])

        st.markdown("### Implementation Steps")
        for i, step in enumerate(guide["steps"], 1):
            st.write(str(i) + ". " + step)

        st.divider()
        st.markdown("### Phase Checklist")
        st.caption("Check each item off as your team completes it. Your name will be recorded.")

        state = get_checklist_state(w_cell, w_phase)
        all_checked = True
        for item in guide["checklist"]:
            item_state = state.get(item, {})
            current = item_state.get("checked", False)
            label = item
            if item_state.get("by"):
                label = item + "  (" + item_state["by"] + ")"
            checked = st.checkbox(label, value=current, key="chk_" + w_cell + w_phase + item)
            if checked != current:
                if not w_user.strip():
                    st.warning("Please enter your name before checking items.")
                else:
                    save_checklist_item(w_cell, w_phase, item, checked, w_user.strip())
                    st.rerun()
            if not checked:
                all_checked = False

        st.divider()
        st.markdown("### What to Photograph")
        st.caption("Take photos at each prompt and attach them to the cell folder or SharePoint.")
        for prompt in guide["photo_prompts"]:
            st.write("📷  " + prompt)

        st.divider()
        st.markdown("### Management Board Requirement")
        st.info("📌  " + guide["board_element"])

        st.divider()
        st.markdown("### Phase Sign-Off")
        if all_checked:
            st.success("All checklist items complete. Ready for sign-off.")
        else:
            remaining = sum(1 for i in guide["checklist"] if not state.get(i, {}).get("checked", False))
            st.warning(str(remaining) + " checklist items still outstanding.")

        signoff_notes = st.text_area("Sign-off Notes (optional)", height=60, key="so_notes")
        if st.button("Submit Phase Sign-Off", type="primary", disabled=not w_user.strip()):
            if not all_checked:
                st.error("Complete all checklist items before signing off.")
            else:
                save_signoff(w_cell, w_phase, w_user.strip(), signoff_notes)
                st.success(w_phase + " sign-off recorded for " + w_cell + " by " + w_user.strip())
                st.balloons()

        signoffs = get_signoffs(w_cell, w_phase)
        if signoffs:
            st.markdown("#### Previous Sign-Offs")
            for sb, sa, sn in signoffs:
                st.write("✅ " + sb + " — " + sa[:10] + ("  |  " + sn if sn else ""))

    # ── REFERENCE LIBRARY ─────────────────────────────────────────────────────
    with reference_tab:
        st.subheader("Reference Library")
        selected = st.selectbox("Select Topic", ["What is 4S+SD?"] + list(PHASE_GUIDE.keys()) + ["Management Board"], key="ref_topic")

        st.divider()

        if selected == "What is 4S+SD?":
            st.markdown("### What is 4S+SD?")
            st.write("4S+SD is a workplace organisation methodology adapted from the Japanese 5S system, tailored for aerospace composite manufacturing environments.")
            st.write("The five elements are:")
            for phase, data in PHASE_GUIDE.items():
                st.write("**" + phase + "** — " + data["objective"])
            st.write("When implemented correctly, 4S+SD reduces defects, improves safety, shortens cycle times and creates a culture of continuous improvement.")
            st.write("In a layup environment specifically, a well-organised cell reduces the risk of FOD (Foreign Object Debris), material mix-ups and bagging errors — all of which directly impact product quality.")

        elif selected == "Management Board":
            st.markdown("### The 4S+SD Management Board")
            st.write("The management board is the visual heartbeat of your cell. It makes the health of your 4S+SD implementation visible to everyone — operators, team leads, supervisors and visitors — at a glance.")
            st.write("A well-maintained board is not a compliance exercise. It is a live communication tool that your team owns and updates themselves.")
            st.divider()
            for name, desc in BOARD_ELEMENTS:
                st.markdown("**" + name + "**")
                st.write(desc)
                st.write("")

        else:
            guide = PHASE_GUIDE[selected]
            st.markdown("### " + selected)
            st.info("**Objective:** " + guide["objective"])
            st.markdown("#### Steps")
            for i, step in enumerate(guide["steps"], 1):
                st.write(str(i) + ". " + step)
            st.markdown("#### Checklist")
            for item in guide["checklist"]:
                st.write("☐  " + item)
            st.markdown("#### Photos to Take")
            for prompt in guide["photo_prompts"]:
                st.write("📷  " + prompt)
            st.markdown("#### Management Board")
            st.info("📌  " + guide["board_element"])

    # ── BOARD TRACKER ─────────────────────────────────────────────────────────
    with board_tab:
        st.subheader("Management Board Setup Tracker")
        st.caption("Track which elements of the management board are in place for each cell.")

        bc1, bc2 = st.columns(2)
        b_cell = bc1.selectbox("Cell", CELLS, key="b_cell")
        b_user = bc2.text_input("Your Name", placeholder="Team lead name", key="b_user")

        board_state = get_board_state(b_cell)
        done_count = sum(1 for e, _ in BOARD_ELEMENTS if board_state.get(e, {}).get("complete", False))
        pct = round(done_count / len(BOARD_ELEMENTS) * 100)

        st.progress(pct, text="Board completion: " + str(pct) + "% (" + str(done_count) + " of " + str(len(BOARD_ELEMENTS)) + " elements)")
        st.divider()

        for element, desc in BOARD_ELEMENTS:
            el_state = board_state.get(element, {})
            current = el_state.get("complete", False)
            col1, col2 = st.columns([3, 1])
            with col1:
                label = element
                if el_state.get("by"):
                    label = element + "  (" + el_state["by"] + ")"
                checked = st.checkbox(label, value=current, key="board_" + b_cell + element, help=desc)
            with col2:
                notes = st.text_input("Notes", value=el_state.get("notes") or "", key="bnotes_" + b_cell + element, label_visibility="collapsed", placeholder="Notes")

            if checked != current:
                if not b_user.strip():
                    st.warning("Please enter your name first.")
                else:
                    save_board_item(b_cell, element, checked, b_user.strip(), notes)
                    st.rerun()
            elif notes != (el_state.get("notes") or ""):
                if b_user.strip():
                    save_board_item(b_cell, element, current, b_user.strip(), notes)

    # ── PROGRESS OVERVIEW ─────────────────────────────────────────────────────
    with progress_tab:
        st.subheader("Cell Progress Overview")
        st.caption("Implementation and management board completion across all cells.")

        for cell in CELLS:
            progress = get_cell_progress(cell)
            total_items = sum(p["total"] for p in progress.values())
            total_done  = sum(p["done"]  for p in progress.values())
            overall_pct = round(total_done / total_items * 100) if total_items else 0

            with st.expander(cell + "  —  Overall: " + str(overall_pct) + "%"):
                for phase, data in progress.items():
                    icon = "✅" if data["pct"] == 100 else ("🟡" if data["pct"] > 0 else "⬜")
                    st.write(icon + "  **" + phase + "**  " + str(data["done"]) + "/" + str(data["total"]) + " (" + str(data["pct"]) + "%)")
