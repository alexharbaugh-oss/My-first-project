"""
Improvement Action KPI Tracker — Joby Aviation Composite Shop
Built for Alex Harbaugh to track improvement actions across
Safety, Quality, Productivity, and 4S+SD categories with
daily KPI measurements showing current vs target condition over time.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from kpi_database import (
    init_db, CATEGORIES, PRIORITIES, STATUSES, STOPPAGE_CODES,
    add_action, get_actions, get_action, update_action, delete_action,
    add_daily_kpi, get_daily_kpis, get_kpi_names_for_action,
    get_all_latest_kpis,
    add_work_stoppage, get_work_stoppages, get_stoppage_pareto,
)

st.set_page_config(
    page_title="Comp Shop Improvement Tracker",
    page_icon="\u2708",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("Comp Shop KPI Tracker")
st.sidebar.caption("Joby Aviation — Composite Shop")

page = st.sidebar.radio(
    "Navigate",
    [
        "Dashboard",
        "Action Tracker",
        "Log Daily KPIs",
        "Effectiveness Trends",
        "Work Stoppages",
    ],
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Filters**")
filter_category = st.sidebar.selectbox("Category", ["All"] + CATEGORIES)
filter_status = st.sidebar.selectbox("Status", ["All"] + STATUSES)
filter_priority = st.sidebar.selectbox("Priority", ["All"] + PRIORITIES)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ═════════════════════════════════════════════════════════════════════════════

if page == "Dashboard":
    st.title("Improvement Action Dashboard")
    st.caption(f"As of {date.today().strftime('%m/%d/%Y')}")

    actions = get_actions(category=filter_category, status=filter_status,
                          priority=filter_priority)

    # ── Summary metrics ──
    col1, col2, col3, col4, col5 = st.columns(5)
    total = len(actions)
    in_progress = sum(1 for a in actions if a["status"] == "In-Progress")
    study_eff = sum(1 for a in actions if a["status"] == "Study Effectiveness")
    completed = sum(1 for a in actions if a["status"] == "Completed")
    not_started = sum(1 for a in actions if a["status"] == "Not Started")

    col1.metric("Total Actions", total)
    col2.metric("In-Progress", in_progress)
    col3.metric("Study Effectiveness", study_eff)
    col4.metric("Completed", completed)
    col5.metric("Not Started", not_started)

    # ── Status breakdown by category ──
    if actions:
        st.markdown("### Actions by Category & Status")
        df = pd.DataFrame(actions)
        fig = px.histogram(df, x="category", color="status",
                           barmode="group",
                           color_discrete_map={
                               "In-Progress": "#f0ad4e",
                               "Study Effectiveness": "#5bc0de",
                               "Completed": "#5cb85c",
                               "Not Started": "#d9534f",
                               "Identified": "#777",
                               "On Hold": "#999",
                           },
                           category_orders={"category": CATEGORIES})
        fig.update_layout(xaxis_title="", yaxis_title="Count", legend_title="Status")
        st.plotly_chart(fig, use_container_width=True)

        # ── Priority breakdown ──
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("### Priority Breakdown")
            fig2 = px.pie(df, names="priority",
                          color="priority",
                          color_discrete_map={
                              "High": "#d9534f",
                              "Med": "#f0ad4e",
                              "Low": "#5bc0de",
                              "No Action": "#999",
                          })
            st.plotly_chart(fig2, use_container_width=True)

        # ── KPI effectiveness snapshot ──
        with col_b:
            st.markdown("### KPI Effectiveness Snapshot")
            latest = get_all_latest_kpis()
            if latest:
                snap_data = []
                for m in latest:
                    if m["baseline_value"] is not None and m["target_value"] is not None and m["baseline_value"] != 0:
                        total_gap = m["target_value"] - m["baseline_value"]
                        if total_gap != 0:
                            progress = (m["value"] - m["baseline_value"]) / total_gap * 100
                            snap_data.append({
                                "Action": m["title"],
                                "KPI": m["kpi_name"],
                                "Progress %": min(max(progress, 0), 100),
                            })
                if snap_data:
                    snap_df = pd.DataFrame(snap_data)
                    fig3 = px.bar(snap_df, x="Progress %", y="Action", orientation="h",
                                  color="Progress %",
                                  color_continuous_scale=["#d9534f", "#f0ad4e", "#5cb85c"],
                                  range_color=[0, 100])
                    fig3.update_layout(yaxis_title="", showlegend=False)
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("Log daily KPIs with baseline & target values to see effectiveness progress.")
            else:
                st.info("No KPI measurements yet. Go to 'Log Daily KPIs' to start tracking.")

        # ── Actions table ──
        st.markdown("### All Actions")
        display_cols = ["id", "title", "category", "priority", "status", "owner", "start_date", "due_date"]
        display_df = pd.DataFrame(actions)[display_cols] if actions else pd.DataFrame()
        if not display_df.empty:
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No actions found. Go to 'Action Tracker' to add your first improvement action.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Action Tracker
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Action Tracker":
    st.title("Action Tracker")
    st.caption("Add and manage improvement actions — mirrors your Google Sheet")

    tab_add, tab_edit = st.tabs(["Add New Action", "Edit / View Actions"])

    # ── Add new action ──
    with tab_add:
        with st.form("add_action_form", clear_on_submit=True):
            st.subheader("New Improvement Action")
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Task / Project Details *", placeholder="e.g. Visual control for tape dispensers")
                category = st.selectbox("Category *", CATEGORIES)
                priority = st.selectbox("Priority *", PRIORITIES, index=1)
                status = st.selectbox("Status", STATUSES, index=1)
            with col2:
                owner = st.text_input("Owner *", value="Alex H.")
                support_team = st.text_input("Support Team", placeholder="e.g. Joel K., Harold")
                start_date = st.date_input("Start Date", value=date.today())
                due_date = st.date_input("Due Date", value=date.today() + timedelta(days=30))

            management_tool = st.text_input(
                "Management Tool",
                placeholder="e.g. Audit, KPI tracker, Implementation tracker"
            )
            current_condition = st.text_area(
                "Current Condition",
                placeholder="Describe the current state / problem...",
                height=80,
            )
            target_condition = st.text_area(
                "Target Condition",
                placeholder="Describe the desired future state...",
                height=80,
            )
            detailed_actions = st.text_area(
                "Detailed Actions / Steps",
                placeholder="1) First step\n2) Second step\n3) ...",
                height=120,
            )
            notes = st.text_area("Notes", height=60)

            submitted = st.form_submit_button("Add Action", type="primary")
            if submitted:
                if not title or not owner:
                    st.error("Title and Owner are required.")
                else:
                    add_action({
                        "title": title, "category": category,
                        "priority": priority, "status": status,
                        "owner": owner, "support_team": support_team,
                        "management_tool": management_tool,
                        "current_condition": current_condition,
                        "target_condition": target_condition,
                        "detailed_actions": detailed_actions,
                        "notes": notes,
                        "start_date": start_date.isoformat(),
                        "due_date": due_date.isoformat(),
                    })
                    st.success(f"Added: {title}")
                    st.rerun()

    # ── Edit / view existing actions ──
    with tab_edit:
        actions = get_actions(category=filter_category, status=filter_status,
                              priority=filter_priority)
        if not actions:
            st.info("No actions to display.")
        else:
            for action in actions:
                with st.expander(
                    f"[{action['priority']}]  {action['title']}  \u2014 {action['status']}  ({action['category']})",
                    expanded=False,
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_status = st.selectbox(
                            "Status", STATUSES,
                            index=STATUSES.index(action["status"]) if action["status"] in STATUSES else 0,
                            key=f"status_{action['id']}",
                        )
                    with col2:
                        new_priority = st.selectbox(
                            "Priority", PRIORITIES,
                            index=PRIORITIES.index(action["priority"]) if action["priority"] in PRIORITIES else 1,
                            key=f"pri_{action['id']}",
                        )
                    with col3:
                        new_owner = st.text_input("Owner", value=action["owner"],
                                                   key=f"owner_{action['id']}")

                    st.markdown("**Current Condition:**")
                    st.text(action.get("current_condition", "") or "\u2014")
                    st.markdown("**Target Condition:**")
                    st.text(action.get("target_condition", "") or "\u2014")
                    st.markdown("**Detailed Actions:**")
                    st.text(action.get("detailed_actions", "") or "\u2014")

                    if action.get("notes"):
                        st.markdown("**Notes:**")
                        st.text(action["notes"])

                    col_save, col_del = st.columns([3, 1])
                    with col_save:
                        if st.button("Save Changes", key=f"save_{action['id']}"):
                            update_data = {
                                "status": new_status,
                                "priority": new_priority,
                                "owner": new_owner,
                            }
                            if new_status == "Completed" and action["status"] != "Completed":
                                update_data["completed_date"] = date.today().isoformat()
                            update_action(action["id"], update_data)
                            st.success("Updated!")
                            st.rerun()
                    with col_del:
                        if st.button("Delete", key=f"del_{action['id']}", type="secondary"):
                            delete_action(action["id"])
                            st.warning(f"Deleted: {action['title']}")
                            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Log Daily KPIs
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Log Daily KPIs":
    st.title("Log Daily KPIs")
    st.caption("Record daily measurements for your improvement actions \u2014 current condition vs target over time")

    actions = get_actions()
    if not actions:
        st.info("Add actions first in the Action Tracker, then come back to log KPIs.")
    else:
        action_options = {f"{a['title']} [{a['category']}]": a["id"] for a in actions}
        selected_label = st.selectbox("Select Action", list(action_options.keys()))
        action_id = action_options[selected_label]
        action = get_action(action_id)

        if action:
            st.markdown(f"**Current Condition:** {action.get('current_condition') or '\u2014'}")
            st.markdown(f"**Target Condition:** {action.get('target_condition') or '\u2014'}")

        st.markdown("---")

        with st.form("log_kpi_form", clear_on_submit=True):
            st.subheader("Record a Measurement")
            col1, col2 = st.columns(2)
            with col1:
                measure_date = st.date_input("Date", value=date.today())
                kpi_name = st.text_input(
                    "KPI Name *",
                    placeholder="e.g. Turn-over sheets missed, Recuts per shift, 5S audit score"
                )
                kpi_unit = st.text_input("Unit", placeholder="e.g. count, %, hours, score")
            with col2:
                value = st.number_input("Today's Value *", step=0.1, format="%.2f")
                baseline_value = st.number_input(
                    "Baseline (current condition value)",
                    step=0.1, format="%.2f",
                    help="What was the metric before your improvement? Only needed on first entry."
                )
                target_value = st.number_input(
                    "Target Value (new condition goal)",
                    step=0.1, format="%.2f",
                    help="What are you trying to achieve?"
                )

            notes = st.text_input("Notes", placeholder="Any context for today's reading")
            recorded_by = st.text_input("Recorded By", value="Alex H.")

            submitted = st.form_submit_button("Log KPI", type="primary")
            if submitted:
                if not kpi_name:
                    st.error("KPI Name is required.")
                else:
                    add_daily_kpi(
                        action_id=action_id,
                        measure_date=measure_date.isoformat(),
                        kpi_name=kpi_name,
                        value=value,
                        target_value=target_value if target_value != 0 else None,
                        baseline_value=baseline_value if baseline_value != 0 else None,
                        kpi_unit=kpi_unit,
                        notes=notes,
                        recorded_by=recorded_by,
                    )
                    st.success(f"Logged {kpi_name} = {value} {kpi_unit} for {measure_date}")
                    st.rerun()

        # ── Show recent entries for this action ──
        st.markdown("---")
        st.subheader("Recent Entries for This Action")
        kpi_names = get_kpi_names_for_action(action_id)
        if kpi_names:
            for kpi in kpi_names:
                measurements = get_daily_kpis(action_id, kpi)
                if measurements:
                    df = pd.DataFrame(measurements)
                    st.markdown(f"**{kpi}** ({measurements[0].get('kpi_unit', '')})")
                    st.dataframe(
                        df[["measure_date", "value", "target_value", "baseline_value", "notes"]],
                        use_container_width=True, hide_index=True,
                    )
        else:
            st.info("No KPI data logged for this action yet.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Effectiveness Trends
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Effectiveness Trends":
    st.title("Effectiveness Trends")
    st.caption("Current condition vs target condition improvement over time \u2014 the charts your boss wants to see")

    actions = get_actions()
    if not actions:
        st.info("No actions yet.")
    else:
        action_options = {f"{a['title']} [{a['category']}]": a["id"] for a in actions}
        selected_label = st.selectbox("Select Action", list(action_options.keys()))
        action_id = action_options[selected_label]
        action = get_action(action_id)

        if action:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Current Condition:** {action.get('current_condition') or '\u2014'}")
            with col2:
                st.markdown(f"**Target Condition:** {action.get('target_condition') or '\u2014'}")

        kpi_names = get_kpi_names_for_action(action_id)

        if not kpi_names:
            st.info("No KPI data logged for this action. Go to 'Log Daily KPIs' to start tracking.")
        else:
            for kpi_name in kpi_names:
                measurements = get_daily_kpis(action_id, kpi_name)
                if not measurements:
                    continue

                df = pd.DataFrame(measurements)
                df["measure_date"] = pd.to_datetime(df["measure_date"])
                unit = measurements[0].get("kpi_unit", "")

                st.markdown(f"### {kpi_name}" + (f" ({unit})" if unit else ""))

                fig = go.Figure()

                # Actual values
                fig.add_trace(go.Scatter(
                    x=df["measure_date"], y=df["value"],
                    mode="lines+markers",
                    name="Actual",
                    line=dict(color="#0275d8", width=3),
                    marker=dict(size=8),
                ))

                # Target line
                targets = df["target_value"].dropna()
                if not targets.empty:
                    target_val = targets.iloc[-1]
                    fig.add_hline(
                        y=target_val, line_dash="dash",
                        line_color="#5cb85c", line_width=2,
                        annotation_text=f"Target: {target_val}",
                        annotation_position="top right",
                    )

                # Baseline line
                baselines = df["baseline_value"].dropna()
                if not baselines.empty:
                    baseline_val = baselines.iloc[0]
                    fig.add_hline(
                        y=baseline_val, line_dash="dot",
                        line_color="#d9534f", line_width=2,
                        annotation_text=f"Baseline: {baseline_val}",
                        annotation_position="bottom right",
                    )

                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title=unit or kpi_name,
                    hovermode="x unified",
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True)

                # ── Effectiveness summary box ──
                if not baselines.empty and not targets.empty:
                    latest_val = df["value"].iloc[-1]
                    baseline_val = baselines.iloc[0]
                    target_val = targets.iloc[-1]
                    total_gap = target_val - baseline_val
                    if total_gap != 0:
                        progress_pct = (latest_val - baseline_val) / total_gap * 100
                        progress_pct = min(max(progress_pct, 0), 100)
                    else:
                        progress_pct = 100 if latest_val == target_val else 0

                    delta = latest_val - baseline_val
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    col_m1.metric("Baseline", f"{baseline_val:.1f}")
                    col_m2.metric("Current", f"{latest_val:.1f}",
                                  delta=f"{delta:+.1f} from baseline")
                    col_m3.metric("Target", f"{target_val:.1f}")
                    col_m4.metric("Progress", f"{progress_pct:.0f}%")

                    # Progress bar
                    st.progress(progress_pct / 100)

                st.markdown("---")

        # ── Multi-action comparison ──
        st.markdown("### Compare Across Actions")
        all_latest = get_all_latest_kpis()
        if all_latest:
            compare_data = []
            for m in all_latest:
                if m["baseline_value"] is not None and m["target_value"] is not None:
                    total_gap = m["target_value"] - m["baseline_value"]
                    if total_gap != 0:
                        prog = (m["value"] - m["baseline_value"]) / total_gap * 100
                        prog = min(max(prog, 0), 100)
                    else:
                        prog = 100 if m["value"] == m["target_value"] else 0
                    compare_data.append({
                        "Action": m["title"][:40],
                        "KPI": m["kpi_name"],
                        "Category": m["category"],
                        "Baseline": m["baseline_value"],
                        "Current": m["value"],
                        "Target": m["target_value"],
                        "Progress %": prog,
                    })
            if compare_data:
                comp_df = pd.DataFrame(compare_data)
                fig = px.bar(comp_df, x="Progress %", y="Action", orientation="h",
                             color="Category",
                             color_discrete_map={
                                 "Safety": "#d9534f",
                                 "Quality": "#0275d8",
                                 "Productivity": "#f0ad4e",
                                 "4S+SD": "#5cb85c",
                             },
                             hover_data=["KPI", "Baseline", "Current", "Target"])
                fig.update_layout(
                    xaxis_title="Progress to Target (%)",
                    yaxis_title="",
                    xaxis_range=[0, 100],
                    height=max(300, len(compare_data) * 40),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Log KPIs with baseline and target values to see the comparison chart.")
        else:
            st.info("No KPI data across actions yet.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Work Stoppages
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Work Stoppages":
    st.title("Work Stoppages")
    st.caption("Track and analyze production cause codes from the FMDS board")

    tab_log, tab_pareto, tab_list = st.tabs(["Log Stoppage", "Pareto Analysis", "All Stoppages"])

    with tab_log:
        with st.form("log_stoppage", clear_on_submit=True):
            st.subheader("Log a Work Stoppage")
            col1, col2 = st.columns(2)
            with col1:
                stoppage_date = st.date_input("Date", value=date.today())
                cause_code = st.selectbox("Cause Code", STOPPAGE_CODES)
                hours_lost = st.number_input("Hours Lost", min_value=0.0, step=0.25, format="%.2f")
            with col2:
                owner = st.text_input("Owner / Responsible")
                status = st.selectbox("Status", ["Open", "Corrective Action Taken", "Closed"])

            description = st.text_area("Description", height=80)
            corrective_action = st.text_area("Corrective Action", height=80)
            notes = st.text_input("Notes")

            if st.form_submit_button("Log Stoppage", type="primary"):
                add_work_stoppage({
                    "stoppage_date": stoppage_date.isoformat(),
                    "cause_code": cause_code,
                    "hours_lost": hours_lost,
                    "description": description,
                    "corrective_action": corrective_action,
                    "owner": owner,
                    "status": status,
                    "notes": notes,
                })
                st.success(f"Logged: {cause_code} \u2014 {hours_lost}h lost")
                st.rerun()

    with tab_pareto:
        pareto = get_stoppage_pareto()
        if pareto:
            df = pd.DataFrame(pareto)
            df = df.sort_values("total_hours", ascending=False)

            # Cumulative % for Pareto line
            total_hrs = df["total_hours"].sum()
            df["cumulative_pct"] = df["total_hours"].cumsum() / total_hrs * 100

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df["cause_code"], y=df["total_hours"],
                name="Hours Lost",
                marker_color="#0275d8",
            ))
            fig.add_trace(go.Scatter(
                x=df["cause_code"], y=df["cumulative_pct"],
                name="Cumulative %",
                yaxis="y2",
                line=dict(color="#d9534f", width=2),
                marker=dict(size=6),
            ))
            fig.update_layout(
                title="Work Stoppage Pareto \u2014 Hours Lost by Cause Code",
                yaxis=dict(title="Hours Lost"),
                yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 105]),
                xaxis_tickangle=-45,
                height=500,
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Summary table
            st.dataframe(df[["cause_code", "total_hours", "count"]], use_container_width=True, hide_index=True)
        else:
            st.info("No work stoppages logged yet.")

    with tab_list:
        stoppages = get_work_stoppages()
        if stoppages:
            df = pd.DataFrame(stoppages)
            st.dataframe(
                df[["id", "stoppage_date", "cause_code", "hours_lost", "owner", "status", "corrective_action"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No work stoppages logged yet.")
