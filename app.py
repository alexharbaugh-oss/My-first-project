import streamlit as st
import plotly.express as px
import pandas as pd
import uuid
import json
from datetime import datetime, timezone, date
from io import BytesIO
from fpdf import FPDF

from database import (
init_db, save_audit, get_audits, get_audit_answers,
get_action_items, add_action_item, update_action_item,
)

# – Constants —————————————————————–

PASS_THRESHOLD = 80.0
CELLS = ["Small Parts", "Medium", "Large", "Propeller", "Battery"]
WEEK_PHASE_MAP = {
1: "Sort", 2: "Set", 3: "Shine",
4: "Standardize", 5: "Self Discipline", 6: "Review",
}
SECTIONS = list(WEEK_PHASE_MAP.values())[:5]

QUESTIONS = {
"Sort": [
"Are all non-essential tools removed from the cell?",
"Are red-tagged items identified and moved to the quarantine zone?",
"Are only materials needed for current work orders present?",
"Are scrap and offcut materials disposed of or returned to stores?",
"Are personal items stored away from the work area?",
],
"Set": [
"Do all tools have a clearly marked designated location (shadow board/label)?",
"Are consumables (resin, peel ply, release film) stored in labeled, correct locations?",
"Is the layup table surface clear and ready for use?",
"Are frequently used tools within arm’s reach of the primary work position?",
"Are material carts and trolleys parked in their designated spots?",
],
"Shine": [
"Is the layup table free of resin residue and debris?",
"Are tools cleaned and returned after each use?",
"Are floors in the cell swept and free of trip hazards?",
"Are vacuum lines and bagging equipment stored clean and untangled?",
"Is the cleaning schedule posted and up to date?",
],
"Standardize": [
"Are visual standards (photos, diagrams) posted at each station?",
"Do all operators follow the same layup sequence for this cell?",
"Are material traceability labels applied consistently?",
"Is the audit checklist accessible and in use by all team members?",
"Are non-conformances recorded using the standard process?",
],
"Self Discipline": [
"Are operators completing the daily 5-minute tidy routine without prompting?",
"Are previous audit findings actioned and closed out?",
"Is the 4S+SD board updated by the team (not just supervisors)?",
"Are new team members briefed on 4S+SD expectations?",
"Is the cell consistently maintaining scores above the pass threshold?",
],
}

# – Init –––––––––––––––––––––––––––––––––––

init_db()
st.set_page_config(page_title="4S+SD Audit Tracker", page_icon="✈️", layout="wide")
st.title("✈️ 4S+SD Audit Tracker — Composites Layup")

tabs = st.tabs([
"📋 New Audit",
"📊 Progress Charts",
"🔧 Action Items",
"📜 Audit History",
"⬇️ Export",
])

# – Helpers —————————————————————––

def calc_score(answers):
yes = sum(1 for v in answers.values() if v is True)
no  = sum(1 for v in answers.values() if v is False)
tot = yes + no
score = round(yes / tot * 100, 1) if tot else 0.0
return {
"answered_yes": yes, "answered_no": no,
"skipped_na": sum(1 for v in answers.values() if v is None),
"total_questions": len(answers),
"standardization_score": score,
"passed": score >= PASS_THRESHOLD,
}

def build_pdf(audit, answers, linked_items):
pdf = FPDF()
pdf.add_page()
pdf.set_margins(15, 15, 15)
pdf.set_font("Helvetica", "B", 18)
pdf.cell(0, 12, "4S+SD Audit Report", ln=True, align="C")
pdf.set_draw_color(30, 80, 160)
pdf.set_line_width(0.8)
pdf.line(15, pdf.get_y(), 195, pdf.get_y())
pdf.ln(4)
pdf.set_font("Helvetica", "", 10)
details = [
(“Cell”, audit[“cell”]),
(“Week”, str(audit[“week”]) + “ — “ + audit[“phase_label”]),
(“Auditor”, audit[“auditor”]),
(“Date”, audit[“timestamp”][:10]),
(“Score”, str(audit[“standardization_score”]) + “%  (” + (“PASS” if audit[“passed”] else “FAIL”) + “)”),
]
for label, val in details:
pdf.set_font(“Helvetica”, “B”, 10)
pdf.cell(35, 7, label + “:”, border=0)
pdf.set_font(“Helvetica”, “”, 10)
pdf.cell(0, 7, val, ln=True)
pdf.ln(4)
ans_map = {1: “Yes”, 0: “No”, None: “N/A”}
current_section = None
for row in answers:
if row[“section”] != current_section:
current_section = row[“section”]
pdf.set_font(“Helvetica”, “B”, 11)
pdf.set_fill_color(220, 230, 245)
pdf.cell(0, 8, “  “ + current_section, ln=True, fill=True)
pdf.set_font(“Helvetica”, “”, 9)
ans_txt = ans_map.get(row[“answer”], “N/A”)
marker  = “Y” if row[“answer”] == 1 else (“N” if row[“answer”] == 0 else “-”)
pdf.cell(12, 6, “  [” + marker + “]”, border=0)
pdf.multi_cell(0, 6, ans_txt + “  —  “ + row[“question_text”])
if audit.get(“notes”):
pdf.ln(3)
pdf.set_font(“Helvetica”, “B”, 11)
pdf.set_fill_color(220, 230, 245)
pdf.cell(0, 8, “  Notes”, ln=True, fill=True)
pdf.set_font(“Helvetica”, “”, 9)
pdf.multi_cell(0, 6, audit[“notes”])
if linked_items:
pdf.ln(3)
pdf.set_font(“Helvetica”, “B”, 11)
pdf.set_fill_color(220, 230, 245)
pdf.cell(0, 8, “  Linked Action Items”, ln=True, fill=True)
pdf.set_font(“Helvetica”, “”, 9)
for item in linked_items:
due = item.get(“due_date”) or “N/A”
pdf.multi_cell(0, 6, “  [” + item[“status”] + “] “ + item[“description”] + “  (Due: “ + due + “)”)
buf = BytesIO()
pdf.output(buf)
buf.seek(0)
return buf

# ——————————————————————————

# TAB 1 — New Audit

# ——————————————————————————

with tabs[0]:
st.subheader(“Audit Details”)
c1, c2, c3 = st.columns(3)
auditor = c1.text_input(“Auditor Name”, placeholder=“Your name”)
cell    = c2.selectbox(“Cell”, CELLS)
week    = c3.selectbox(
“Week”, list(WEEK_PHASE_MAP.keys()),
format_func=lambda w: “Week “ + str(w) + “ — “ + WEEK_PHASE_MAP[w]
)
phase = WEEK_PHASE_MAP[week]
st.info(“📍 Phase: “ + phase + “  |  Cell: “ + cell + “  |  Week: “ + str(week) + “ of 6”)
st.divider()

```
all_answers, section_scores, section_qa = {}, {}, {}

for section, questions in QUESTIONS.items():
    with st.expander("**" + section + "**", expanded=(section == phase)):
        sec_ans, sec_qa = {}, {}
        for i, q in enumerate(questions):
            qid = section.lower().replace(" ", "_") + "_q" + str(i + 1)
            ans = st.radio(q, ["Yes", "No", "N/A"], index=2,
                           key="audit_" + qid, horizontal=True)
            val = True if ans == "Yes" else (False if ans == "No" else None)
            sec_ans[qid] = val
            sec_qa[qid]  = (q, val)
        yes = sum(1 for v in sec_ans.values() if v is True)
        no  = sum(1 for v in sec_ans.values() if v is False)
        tot = yes + no
        pct = round(yes / tot * 100, 1) if tot else 0.0
        section_scores[section] = pct
        section_qa[section]     = sec_qa
        all_answers.update(sec_ans)
        st.metric(section + " Score", str(pct) + "%")

st.divider()
notes   = st.text_area("Overall Notes / Follow-up Actions", height=80)
summary = calc_score(all_answers)
score   = summary["standardization_score"]
verdict = "✅ PASS" if summary["passed"] else "❌ NEEDS WORK"

st.subheader("Standardization Score")
st.progress(int(score), text=str(score) + "% — " + verdict)
ca, cb, cc, cd = st.columns(4)
ca.metric("Yes",   summary["answered_yes"])
cb.metric("No",    summary["answered_no"])
cc.metric("N/A",   summary["skipped_na"])
cd.metric("Score", str(score) + "%")
st.divider()

if st.button("💾 Save Audit Result", type="primary", use_container_width=True):
    if not auditor.strip():
        st.error("Please enter auditor name.")
    else:
        result = {
            "audit_id":    str(uuid.uuid4()),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "auditor":     auditor.strip(),
            "cell":        cell,
            "week":        week,
            "phase_label": phase,
            "sections":    {s: {"score": section_scores[s], "qa": section_qa[s]}
                            for s in QUESTIONS},
            "summary":     summary,
            "notes":       notes.strip(),
        }
        save_audit(result)
        st.success("Audit saved! " + str(score) + "% — " + verdict)
        st.balloons()
```

# ——————————————————————————

# TAB 2 — Progress Charts

# ——————————————————————————

with tabs[1]:
st.subheader(“Score Progression”)
audits = get_audits()

```
if not audits:
    st.info("No audit data yet — complete your first audit.")
else:
    df = pd.DataFrame(audits)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.date

    sel_cells = st.multiselect("Show Cells", CELLS, default=CELLS, key="chart_cells")
    df_f = df[df["cell"].isin(sel_cells)]

    fig_line = px.line(
        df_f, x="timestamp", y="standardization_score", color="cell",
        markers=True, title="Standardization Score Over Time",
        labels={"standardization_score": "Score (%)", "timestamp": "Date", "cell": "Cell"},
        range_y=[0, 100],
    )
    fig_line.add_hline(
        y=PASS_THRESHOLD, line_dash="dash", line_color="red",
        annotation_text="Pass Threshold (" + str(PASS_THRESHOLD) + "%)"
    )
    st.plotly_chart(fig_line, use_container_width=True)

    st.subheader("Latest Score per Cell")
    latest = df.sort_values("timestamp").groupby("cell").last().reset_index()
    fig_bar = px.bar(
        latest, x="cell", y="standardization_score",
        color="standardization_score",
        color_continuous_scale=["red", "orange", "green"],
        range_color=[0, 100], title="Most Recent Score by Cell",
        labels={"standardization_score": "Score (%)", "cell": "Cell"},
        text_auto=".1f",
    )
    fig_bar.add_hline(y=PASS_THRESHOLD, line_dash="dash", line_color="red")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Average Score — Cell x Week")
    pivot = df.pivot_table(
        values="standardization_score", index="cell", columns="week", aggfunc="mean"
    )
    fig_heat = px.imshow(
        pivot, text_auto=".1f", color_continuous_scale="RdYlGn",
        range_color=[0, 100], title="Average Score Heatmap",
        labels={"x": "Week", "y": "Cell", "color": "Score (%)"},
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    st.subheader("6-Week Phase Completion per Cell")
    comp_rows = []
    for c in CELLS:
        weeks_done = df[df["cell"] == c]["week"].unique().tolist()
        for w in range(1, 7):
            comp_rows.append({
                "Cell": c,
                "Week": "Wk " + str(w) + " " + WEEK_PHASE_MAP[w],
                "Done": "✅" if w in weeks_done else "⬜"
            })
    comp_df = pd.DataFrame(comp_rows).pivot(index="Cell", columns="Week", values="Done")
    st.dataframe(comp_df, use_container_width=True)
```

# ——————————————————————————

# TAB 3 — Action Items

# ——————————————————————————

with tabs[2]:
st.subheader(“Action Items”)
sub_raise, sub_view = st.tabs([“➕ Raise New Item”, “📋 View & Update Items”])

```
with sub_raise:
    with st.form("new_action_form"):
        ac1, ac2 = st.columns(2)
        ai_cell    = ac1.selectbox("Cell", CELLS, key="ai_cell")
        ai_section = ac2.selectbox("Section", ["General"] + SECTIONS, key="ai_sec")
        ai_desc    = st.text_area("Description of Finding / Action Required", height=80)
        ac3, ac4   = st.columns(2)
        ai_raised  = ac3.text_input("Raised By", placeholder="Name")
        ai_due     = ac4.date_input("Due Date", value=None)
        ai_notes   = st.text_area("Notes", height=50)
        if st.form_submit_button("Raise Action Item", type="primary"):
            if not ai_desc.strip() or not ai_raised.strip():
                st.error("Description and Raised By are required.")
            else:
                add_action_item({
                    "cell":        ai_cell,
                    "section":     ai_section if ai_section != "General" else None,
                    "description": ai_desc.strip(),
                    "raised_by":   ai_raised.strip(),
                    "raised_date": date.today().isoformat(),
                    "due_date":    ai_due.isoformat() if ai_due else None,
                    "notes":       ai_notes.strip(),
                })
                st.success("Action item raised!")

with sub_view:
    fc1, fc2 = st.columns(2)
    f_cell   = fc1.selectbox("Filter Cell",   ["All"] + CELLS, key="ai_fcell")
    f_status = fc2.selectbox("Filter Status", ["All", "Open", "In Progress", "Closed"])
    items    = get_action_items(
        cell=f_cell if f_cell != "All" else None,
        status=f_status if f_status != "All" else None,
    )

    all_items = get_action_items()
    m1, m2, m3 = st.columns(3)
    m1.metric("🔴 Open",        sum(1 for i in all_items if i["status"] == "Open"))
    m2.metric("🟡 In Progress", sum(1 for i in all_items if i["status"] == "In Progress"))
    m3.metric("🟢 Closed",      sum(1 for i in all_items if i["status"] == "Closed"))
    st.divider()

    if not items:
        st.info("No action items found.")
    else:
        ICONS = {"Open": "🔴", "In Progress": "🟡", "Closed": "🟢"}
        for item in items:
            icon  = ICONS.get(item["status"], "⚪")
            label = item["description"][:70] + ("..." if len(item["description"]) > 70 else "")
            with st.expander(icon + " [" + item["cell"] + "] " + label):
                st.write("**Section:** " + str(item.get("section") or "General") +
                         "  |  **Raised by:** " + item["raised_by"] +
                         "  |  **Date:** " + item["raised_date"])
                if item.get("due_date"):
                    st.write("**Due:** " + item["due_date"])
                new_status = st.selectbox(
                    "Status",
                    ["Open", "In Progress", "Closed"],
                    index=["Open", "In Progress", "Closed"].index(item["status"]),
                    key="status_" + str(item["id"])
                )
                closed_by = ""
                if new_status == "Closed":
                    closed_by = st.text_input("Closed By", key="cb_" + str(item["id"]))
                new_notes = st.text_input("Notes", value=item.get("notes", ""),
                                          key="notes_" + str(item["id"]))
                if st.button("Update", key="upd_" + str(item["id"])):
                    update_action_item(item["id"], new_status, closed_by, new_notes)
                    st.success("Updated!")
                    st.rerun()
```

# ——————————————————————————

# TAB 4 — Audit History

# ——————————————————————————

with tabs[3]:
st.subheader(“Audit History”)
hc1, hc2 = st.columns(2)
h_cell = hc1.selectbox(“Filter Cell”, [“All”] + CELLS, key=“h_cell”)
h_week = hc2.selectbox(“Filter Week”, [“All”] + list(range(1, 7)), key=“h_week”)

```
h_audits = get_audits(
    cell=h_cell if h_cell != "All" else None,
    week=int(h_week) if h_week != "All" else None,
)

if not h_audits:
    st.info("No audits found.")
else:
    for a in h_audits:
        ok = "✅" if a["passed"] else "❌"
        ts = a["timestamp"][:10]
        with st.expander(
            ok + " " + ts + " | " + a["cell"] + " | Week " + str(a["week"]) +
            " — " + a["phase_label"] + " | " + str(a["standardization_score"]) + "%"
        ):
            st.write("**Auditor:** " + a["auditor"] + "  |  **Score:** " + str(a["standardization_score"]) + "%")
            answers = get_audit_answers(a["audit_id"])
            ans_df  = pd.DataFrame(answers)[["section", "question_text", "answer"]]
            ans_df["answer"] = ans_df["answer"].map({1: "✅ Yes", 0: "❌ No"}).fillna("— N/A")
            st.dataframe(ans_df, use_container_width=True, hide_index=True)
            if a.get("notes"):
                st.write("**Notes:** " + a["notes"])
```

# ——————————————————————————

# TAB 5 — Export

# ——————————————————————————

with tabs[4]:
st.subheader(“Export Options”)
all_audits = get_audits()

```
st.markdown("### ⬇️ Download All Audit Data (JSON)")
st.download_button(
    "Download JSON", data=json.dumps(all_audits, indent=2),
    file_name="audit_results.json", mime="application/json",
    use_container_width=True,
)
st.divider()

st.markdown("### 📄 Generate PDF Audit Report")
if not all_audits:
    st.info("No audits available yet.")
else:
    audit_labels = {
        a["timestamp"][:10] + " | " + a["cell"] + " | Week " + str(a["week"]) + " | " + str(a["standardization_score"]) + "%": a
        for a in all_audits
    }
    selected = audit_labels[st.selectbox("Select Audit", list(audit_labels.keys()))]

    if st.button("Generate PDF", type="primary", use_container_width=True):
        answers      = get_audit_answers(selected["audit_id"])
        linked_items = [i for i in get_action_items()
                        if i.get("audit_id") == selected["audit_id"]]
        buf   = build_pdf(selected, answers, linked_items)
        fname = "audit_" + selected["cell"].replace(" ", "_") + "_" + selected["timestamp"][:10] + ".pdf"
        st.download_button(
            "⬇️ Download PDF", data=buf,
            file_name=fname, mime="application/pdf",
            use_container_width=True,
        )
```
