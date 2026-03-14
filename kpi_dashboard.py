import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
from datetime import date, datetime, timezone
from io import BytesIO

from kpi_database import (
    init_db, CATEGORIES, CELLS,
    add_improvement_action, get_improvement_actions, update_improvement_action,
    add_daily_measurement, get_daily_measurements, get_latest_measurement,
    get_measurements_with_actions,
)

# -- Init ----------------------------------------------------------------------
init_db()
st.set_page_config(
    page_title="KPI Improvement Tracker — Joby Composites",
    page_icon="📈",
    layout="wide",
)
st.title("📈 KPI Improvement Tracker — Composites Shop")
st.caption("Track current condition vs. target condition for every improvement action across Safety, Quality, Productivity, and 4S+SD.")

tabs = st.tabs([
    "📊 Dashboard Overview",
    "➕ New Improvement Action",
    "📏 Log Daily Measurement",
    "📋 Action Details",
    "⬇️ Export",
])

# -- Helpers -------------------------------------------------------------------

def pct_to_target(baseline, target, current, direction):
    """Calculate percentage progress toward target."""
    span = target - baseline
    if span == 0:
        return 100.0 if current == target else 0.0
    raw = (current - baseline) / span * 100
    return max(0.0, min(round(raw, 1), 100.0))


def effectiveness_label(pct):
    if pct >= 100:
        return "Target Met", "green"
    elif pct >= 75:
        return "On Track", "blue"
    elif pct >= 50:
        return "Progressing", "orange"
    elif pct > 0:
        return "Early Stage", "gray"
    else:
        return "No Change", "red"


# ==============================================================================
# TAB 1 — Dashboard Overview
# ==============================================================================
with tabs[0]:
    st.subheader("Improvement Overview")

    fc1, fc2, fc3 = st.columns(3)
    d_cat    = fc1.selectbox("Category", ["All"] + CATEGORIES, key="d_cat")
    d_cell   = fc2.selectbox("Cell", ["All"] + CELLS, key="d_cell")
    d_status = fc3.selectbox("Status", ["All", "Active", "Completed", "On Hold"], key="d_status")

    actions = get_improvement_actions(
        category=d_cat if d_cat != "All" else None,
        cell=d_cell if d_cell != "All" else None,
        status=d_status if d_status != "All" else None,
    )

    # ── Summary metrics ──────────────────────────────────────────────────────
    all_actions = get_improvement_actions()
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Total Actions", len(all_actions))
    mc2.metric("Active", sum(1 for a in all_actions if a["status"] == "Active"))
    mc3.metric("Completed", sum(1 for a in all_actions if a["status"] == "Completed"))
    mc4.metric("On Hold", sum(1 for a in all_actions if a["status"] == "On Hold"))

    # ── Category breakdown ───────────────────────────────────────────────────
    if all_actions:
        st.divider()
        cat_cols = st.columns(len(CATEGORIES))
        for i, cat in enumerate(CATEGORIES):
            cat_actions = [a for a in all_actions if a["category"] == cat]
            cat_cols[i].metric(cat, len(cat_actions))

    # ── Actions with current progress ────────────────────────────────────────
    st.divider()
    st.subheader("Action Status — Current vs. Target")

    if not actions:
        st.info("No improvement actions found. Add one in the 'New Improvement Action' tab.")
    else:
        for action in actions:
            latest = get_latest_measurement(action["id"])
            current_val = latest["value"] if latest else action["baseline_value"]
            pct = pct_to_target(
                action["baseline_value"], action["target_value"],
                current_val, action["improvement_direction"]
            )
            eff_label, eff_color = effectiveness_label(pct)

            with st.expander(
                f"{'🟢' if pct >= 100 else '🟡' if pct >= 50 else '🔴'} "
                f"[{action['category']}] {action['title']} — {action['cell']} — "
                f"{pct}% to target"
            ):
                # Condition comparison
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.markdown("**Current Condition (Before)**")
                    st.warning(action["current_condition"])
                    st.metric("Baseline", f"{action['baseline_value']} {action['kpi_unit']}")
                with cc2:
                    st.markdown("**Target Condition (After)**")
                    st.success(action["target_condition"])
                    st.metric("Target", f"{action['target_value']} {action['kpi_unit']}")

                # Progress bar
                st.progress(
                    min(int(pct), 100),
                    text=f"Progress: {pct}% — {eff_label} | "
                         f"Latest: {current_val} {action['kpi_unit']}"
                )

                # Trend chart
                measurements = get_daily_measurements(action["id"])
                if measurements:
                    mdf = pd.DataFrame(measurements)
                    mdf["measure_date"] = pd.to_datetime(mdf["measure_date"])

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=mdf["measure_date"], y=mdf["value"],
                        mode="lines+markers", name="Daily Value",
                        line=dict(color="#1f77b4", width=2),
                    ))
                    fig.add_hline(
                        y=action["baseline_value"], line_dash="dot",
                        line_color="red",
                        annotation_text=f"Baseline ({action['baseline_value']})",
                    )
                    fig.add_hline(
                        y=action["target_value"], line_dash="dash",
                        line_color="green",
                        annotation_text=f"Target ({action['target_value']})",
                    )
                    fig.update_layout(
                        title=f"{action['kpi_name']} — Daily Trend",
                        xaxis_title="Date",
                        yaxis_title=f"{action['kpi_name']} ({action['kpi_unit']})",
                        height=300,
                        margin=dict(t=40, b=30),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.caption("No daily measurements yet. Log data in the 'Log Daily Measurement' tab.")

                st.write(f"**Owner:** {action['owner']}  |  **Started:** {action['start_date']}"
                         + (f"  |  **Target Date:** {action['target_date']}" if action.get("target_date") else ""))
                if action.get("notes"):
                    st.write(f"**Notes:** {action['notes']}")

    # ── Effectiveness summary chart ──────────────────────────────────────────
    if actions:
        st.divider()
        st.subheader("Effectiveness Summary")

        eff_data = []
        for action in actions:
            latest = get_latest_measurement(action["id"])
            current_val = latest["value"] if latest else action["baseline_value"]
            pct = pct_to_target(
                action["baseline_value"], action["target_value"],
                current_val, action["improvement_direction"]
            )
            eff_data.append({
                "Action": action["title"][:40],
                "Category": action["category"],
                "Cell": action["cell"],
                "% to Target": pct,
                "Baseline": action["baseline_value"],
                "Current": current_val,
                "Target": action["target_value"],
                "Unit": action["kpi_unit"],
            })

        eff_df = pd.DataFrame(eff_data)
        fig_eff = px.bar(
            eff_df, x="Action", y="% to Target", color="Category",
            color_discrete_map={
                "Safety": "#e74c3c", "Quality": "#3498db",
                "Productivity": "#2ecc71", "4S+SD": "#f39c12",
            },
            title="Improvement Effectiveness — % Progress to Target",
            text_auto=".0f",
        )
        fig_eff.add_hline(y=100, line_dash="dash", line_color="green",
                          annotation_text="Target (100%)")
        fig_eff.update_layout(yaxis_range=[0, max(110, eff_df["% to Target"].max() + 10)])
        st.plotly_chart(fig_eff, use_container_width=True)

        # Category average effectiveness
        cat_avg = eff_df.groupby("Category")["% to Target"].mean().reset_index()
        fig_cat = px.bar(
            cat_avg, x="Category", y="% to Target",
            color="Category",
            color_discrete_map={
                "Safety": "#e74c3c", "Quality": "#3498db",
                "Productivity": "#2ecc71", "4S+SD": "#f39c12",
            },
            title="Average Effectiveness by Category",
            text_auto=".1f",
        )
        fig_cat.add_hline(y=100, line_dash="dash", line_color="green")
        st.plotly_chart(fig_cat, use_container_width=True)


# ==============================================================================
# TAB 2 — New Improvement Action
# ==============================================================================
with tabs[1]:
    st.subheader("Log New Improvement Action")
    st.caption("Define the current condition, target condition, and the KPI you'll measure daily.")

    with st.form("new_action_form"):
        st.markdown("### Action Details")
        a_title = st.text_input("Action Title", placeholder="e.g., Reduce FOD incidents in Large cell")
        ac1, ac2, ac3 = st.columns(3)
        a_category = ac1.selectbox("Category", CATEGORIES, key="a_cat")
        a_cell     = ac2.selectbox("Cell", CELLS, key="a_cell")
        a_owner    = ac3.text_input("Owner", placeholder="Your name")

        st.divider()
        st.markdown("### Condition Comparison")
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**Current Condition (Before)**")
            a_current = st.text_area(
                "Describe the current state",
                placeholder="e.g., Tools left on layup table after shifts, averaging 3 FOD findings per week",
                height=100,
            )
        with cc2:
            st.markdown("**Target Condition (After)**")
            a_target = st.text_area(
                "Describe the desired state",
                placeholder="e.g., All tools returned to shadow board, zero FOD findings per week",
                height=100,
            )

        st.divider()
        st.markdown("### KPI Definition")
        st.caption("Define a measurable KPI to track daily. This is how you'll prove the improvement.")

        kc1, kc2, kc3 = st.columns(3)
        a_kpi_name = kc1.text_input("KPI Name", placeholder="e.g., FOD incidents per week")
        a_kpi_unit = kc2.text_input("Unit of Measure", placeholder="e.g., incidents, %, minutes, count")
        a_direction = kc3.selectbox(
            "Improvement Direction",
            ["Lower is Better", "Higher is Better"],
            help="Is a lower number better (e.g., defects) or higher (e.g., on-time %)?",
        )

        vc1, vc2 = st.columns(2)
        a_baseline = vc1.number_input("Baseline Value (Current)", value=0.0, step=0.1,
                                       help="The starting measurement before your action")
        a_target_val = vc2.number_input("Target Value (Goal)", value=0.0, step=0.1,
                                         help="The measurement you're trying to reach")

        st.divider()
        dc1, dc2 = st.columns(2)
        a_start = dc1.date_input("Start Date", value=date.today())
        a_target_date = dc2.date_input("Target Completion Date", value=None)
        a_notes = st.text_area("Notes", height=60, placeholder="Any additional context...")

        submitted = st.form_submit_button("Save Improvement Action", type="primary",
                                           use_container_width=True)
        if submitted:
            if not a_title.strip() or not a_owner.strip():
                st.error("Title and Owner are required.")
            elif not a_kpi_name.strip() or not a_kpi_unit.strip():
                st.error("KPI Name and Unit are required.")
            elif not a_current.strip() or not a_target.strip():
                st.error("Both Current Condition and Target Condition are required.")
            else:
                direction = "lower_is_better" if a_direction == "Lower is Better" else "higher_is_better"
                add_improvement_action({
                    "title": a_title.strip(),
                    "category": a_category,
                    "cell": a_cell,
                    "kpi_name": a_kpi_name.strip(),
                    "kpi_unit": a_kpi_unit.strip(),
                    "current_condition": a_current.strip(),
                    "target_condition": a_target.strip(),
                    "baseline_value": a_baseline,
                    "target_value": a_target_val,
                    "improvement_direction": direction,
                    "owner": a_owner.strip(),
                    "start_date": a_start.isoformat(),
                    "target_date": a_target_date.isoformat() if a_target_date else None,
                    "notes": a_notes.strip(),
                })
                st.success("Improvement action saved!")
                st.balloons()


# ==============================================================================
# TAB 3 — Log Daily Measurement
# ==============================================================================
with tabs[2]:
    st.subheader("Log Daily Measurement")
    st.caption("Record today's KPI value for an active improvement action.")

    active_actions = get_improvement_actions(status="Active")

    if not active_actions:
        st.info("No active improvement actions. Create one first.")
    else:
        # Build labels for the selector
        action_labels = {
            f"[{a['category']}] {a['title']} — {a['cell']} ({a['kpi_name']}, {a['kpi_unit']})": a
            for a in active_actions
        }
        selected_label = st.selectbox("Select Action", list(action_labels.keys()))
        selected_action = action_labels[selected_label]

        # Show context
        st.divider()
        ctx1, ctx2, ctx3 = st.columns(3)
        ctx1.metric("Baseline", f"{selected_action['baseline_value']} {selected_action['kpi_unit']}")
        ctx2.metric("Target", f"{selected_action['target_value']} {selected_action['kpi_unit']}")

        latest = get_latest_measurement(selected_action["id"])
        if latest:
            ctx3.metric("Last Reading",
                        f"{latest['value']} {selected_action['kpi_unit']}",
                        delta=f"{latest['value'] - selected_action['baseline_value']:.1f} from baseline")

        # Show existing measurements
        measurements = get_daily_measurements(selected_action["id"])
        if measurements:
            mdf = pd.DataFrame(measurements)
            mdf["measure_date"] = pd.to_datetime(mdf["measure_date"])

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=mdf["measure_date"], y=mdf["value"],
                mode="lines+markers", name="Daily Value",
            ))
            fig.add_hline(y=selected_action["baseline_value"], line_dash="dot",
                          line_color="red", annotation_text="Baseline")
            fig.add_hline(y=selected_action["target_value"], line_dash="dash",
                          line_color="green", annotation_text="Target")
            fig.update_layout(height=250, margin=dict(t=30, b=20),
                              yaxis_title=selected_action["kpi_unit"])
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        with st.form("log_measurement"):
            mc1, mc2, mc3 = st.columns(3)
            m_date = mc1.date_input("Date", value=date.today())
            m_value = mc2.number_input(
                f"Value ({selected_action['kpi_unit']})",
                value=latest["value"] if latest else selected_action["baseline_value"],
                step=0.1,
            )
            m_by = mc3.text_input("Recorded By", placeholder="Your name")
            m_notes = st.text_input("Notes (optional)", placeholder="Any context for today's reading...")

            if st.form_submit_button("Log Measurement", type="primary", use_container_width=True):
                if not m_by.strip():
                    st.error("Recorded By is required.")
                else:
                    add_daily_measurement(
                        selected_action["id"], m_date.isoformat(),
                        m_value, m_by.strip(), m_notes.strip(),
                    )
                    st.success(f"Logged {m_value} {selected_action['kpi_unit']} for {m_date}")
                    st.rerun()

        # Show measurement history table
        if measurements:
            st.divider()
            st.markdown("### Measurement History")
            hist_df = pd.DataFrame(measurements)[["measure_date", "value", "recorded_by", "notes"]]
            hist_df.columns = ["Date", "Value", "Recorded By", "Notes"]
            st.dataframe(hist_df.sort_values("Date", ascending=False),
                         use_container_width=True, hide_index=True)


# ==============================================================================
# TAB 4 — Action Details / Management
# ==============================================================================
with tabs[3]:
    st.subheader("Manage Improvement Actions")

    fc1, fc2, fc3 = st.columns(3)
    m_cat    = fc1.selectbox("Category", ["All"] + CATEGORIES, key="m_cat")
    m_cell   = fc2.selectbox("Cell", ["All"] + CELLS, key="m_cell")
    m_status = fc3.selectbox("Status", ["All", "Active", "Completed", "On Hold"], key="m_status")

    filtered = get_improvement_actions(
        category=m_cat if m_cat != "All" else None,
        cell=m_cell if m_cell != "All" else None,
        status=m_status if m_status != "All" else None,
    )

    if not filtered:
        st.info("No actions match the filters.")
    else:
        STATUS_ICONS = {"Active": "🟢", "Completed": "✅", "On Hold": "⏸️"}
        for action in filtered:
            icon = STATUS_ICONS.get(action["status"], "⚪")
            latest = get_latest_measurement(action["id"])
            current_val = latest["value"] if latest else action["baseline_value"]
            pct = pct_to_target(
                action["baseline_value"], action["target_value"],
                current_val, action["improvement_direction"]
            )
            measurements = get_daily_measurements(action["id"])

            with st.expander(
                f"{icon} [{action['category']}] {action['title']} — {action['cell']} "
                f"({action['status']}, {pct}% to target)"
            ):
                # Full details
                st.markdown("**KPI:** " + action["kpi_name"] + " (" + action["kpi_unit"] + ")")
                st.markdown(f"**Direction:** {'Lower is Better' if action['improvement_direction'] == 'lower_is_better' else 'Higher is Better'}")

                dc1, dc2 = st.columns(2)
                with dc1:
                    st.markdown("**Current Condition (Before)**")
                    st.warning(action["current_condition"])
                with dc2:
                    st.markdown("**Target Condition (After)**")
                    st.success(action["target_condition"])

                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Baseline", f"{action['baseline_value']} {action['kpi_unit']}")
                mc2.metric("Current", f"{current_val} {action['kpi_unit']}")
                mc3.metric("Target", f"{action['target_value']} {action['kpi_unit']}")
                mc4.metric("Progress", f"{pct}%")

                if measurements:
                    st.markdown(f"**{len(measurements)} measurements recorded** "
                                f"(first: {measurements[0]['measure_date']}, "
                                f"latest: {measurements[-1]['measure_date']})")

                st.divider()
                new_status = st.selectbox(
                    "Update Status", ["Active", "Completed", "On Hold"],
                    index=["Active", "Completed", "On Hold"].index(action["status"]),
                    key=f"st_{action['id']}",
                )
                new_notes = st.text_input("Update Notes", value=action.get("notes", ""),
                                          key=f"notes_{action['id']}")
                if st.button("Save Changes", key=f"save_{action['id']}"):
                    update_improvement_action(action["id"], new_status, new_notes)
                    st.success("Updated!")
                    st.rerun()


# ==============================================================================
# TAB 5 — Export
# ==============================================================================
with tabs[4]:
    st.subheader("Export Data")

    all_actions = get_improvement_actions()

    # JSON export
    st.markdown("### All Improvement Actions (JSON)")
    export_data = []
    for action in all_actions:
        measurements = get_daily_measurements(action["id"])
        action_copy = dict(action)
        action_copy["measurements"] = measurements
        latest = get_latest_measurement(action["id"])
        current_val = latest["value"] if latest else action["baseline_value"]
        action_copy["current_value"] = current_val
        action_copy["pct_to_target"] = pct_to_target(
            action["baseline_value"], action["target_value"],
            current_val, action["improvement_direction"]
        )
        export_data.append(action_copy)

    st.download_button(
        "Download JSON", data=json.dumps(export_data, indent=2),
        file_name="kpi_improvement_actions.json", mime="application/json",
        use_container_width=True,
    )

    # CSV summary
    st.divider()
    st.markdown("### Summary CSV")
    if all_actions:
        csv_rows = []
        for action in all_actions:
            latest = get_latest_measurement(action["id"])
            current_val = latest["value"] if latest else action["baseline_value"]
            pct = pct_to_target(
                action["baseline_value"], action["target_value"],
                current_val, action["improvement_direction"]
            )
            csv_rows.append({
                "Title": action["title"],
                "Category": action["category"],
                "Cell": action["cell"],
                "KPI": action["kpi_name"],
                "Unit": action["kpi_unit"],
                "Baseline": action["baseline_value"],
                "Current": current_val,
                "Target": action["target_value"],
                "% to Target": pct,
                "Status": action["status"],
                "Owner": action["owner"],
                "Start Date": action["start_date"],
                "Target Date": action.get("target_date", ""),
            })
        csv_df = pd.DataFrame(csv_rows)
        st.download_button(
            "Download CSV", data=csv_df.to_csv(index=False),
            file_name="kpi_summary.csv", mime="text/csv",
            use_container_width=True,
        )
        st.dataframe(csv_df, use_container_width=True, hide_index=True)
    else:
        st.info("No data to export yet.")
