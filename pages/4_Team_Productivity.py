"""Team and sprint productivity using governed delivery metrics."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pulseiq.duckdb"
TEAL = "#087E8B"
AMBER = "#D98E32"
INK = "#172B4D"


@st.cache_data(ttl=600, show_spinner=False)
def load_productivity_data(database_path: str) -> tuple[pd.DataFrame, ...]:
    connection = duckdb.connect(database_path, read_only=True)
    try:
        productivity = connection.execute("""
            SELECT team_id, team_name, active_members, planning_cadence, task_types,
                   sprint_id, sprint_name, period_start,
                   sprint_end, working_days, planned_tasks, cancelled_tasks,
                   blocked_tasks, reopened_tasks, reopen_events, completion_rate,
                   on_time_rate, velocity_points, average_cycle_days
            FROM metrics.dashboard_team_sprint_productivity
            ORDER BY period_start, team_id
        """).fetchdf()
        teams = connection.execute("""
            SELECT team_id, team_name, active_members, planning_cadence
            FROM warehouse.dim_team
            ORDER BY team_name
        """).fetchdf()
        metric_rules = connection.execute("""
            SELECT metric_id, metric_name, formula, unit, caveat,
                   minimum_group_size_numeric
            FROM metrics.metric_catalog
            WHERE metric_id IN ('M22', 'M23', 'M24', 'M25')
            ORDER BY metric_id
        """).fetchdf()
    finally:
        connection.close()

    productivity["period_start"] = pd.to_datetime(productivity["period_start"])
    productivity["sprint_end"] = pd.to_datetime(productivity["sprint_end"])
    return productivity, teams, metric_rules


def render_productivity_page() -> None:
    st.set_page_config(
        page_title="PulseIQ | Team productivity",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown("""
        <style>
        :root { --ink: #172B4D; --muted: #667085; --teal: #087E8B; --paper: #F4F7FB; --line: #E4EAF1; }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stHeader"] { background: rgba(244,247,251,.88); }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--line); }
        .block-container { max-width: 1500px; padding: 2rem 2.4rem 3rem; }
        h1, h2, h3 { color: var(--ink); font-family: Inter, 'Segoe UI', sans-serif !important; letter-spacing: -0.025em !important; }
        html, body, [class*="st-"], p, label { font-family: Inter, 'Segoe UI', sans-serif; letter-spacing: 0 !important; }
        .hero-title { font: 750 36px Inter, 'Segoe UI', sans-serif; letter-spacing: -0.04em; color: var(--ink); margin: 8px 0 5px; }
        .hero-copy { color: var(--muted); font-size: 15px; margin-bottom: 24px; }
        [data-testid="stMetric"] { background: #FFFFFF; border: 1px solid var(--line); border-top: 3px solid var(--teal); padding: 16px 15px; border-radius: 12px; min-height: 115px; }
        [data-testid="stPlotlyChart"] { background: #FFFFFF; border: 1px solid var(--line); border-radius: 12px; padding: 10px; }
        .finding { border: 1px solid #E4EAF1; border-left: 4px solid var(--teal); padding: 12px 15px; margin: 3px 0 12px; color: #475467; background: #FFFFFF; font-size: 13px; border-radius: 0 10px 10px 0; }
        @media (max-width: 720px) { .block-container { padding: 1.25rem 1rem 2rem; } .hero-title { font-size: 29px; } }
        </style>
    """, unsafe_allow_html=True)

    try:
        productivity, teams, metric_rules = load_productivity_data(str(DATABASE))
    except (duckdb.Error, OSError) as exc:
        st.error(
            "Team productivity views are not ready. Run `python etl.py`, "
            "`python warehouse.py`, and `python metrics.py` after resolving "
            "any critical data-quality gate failures."
        )
        st.exception(exc)
        return

    if productivity.empty:
        st.error("No team/sprint groups meet the minimum task-group threshold.")
        return

    sprints = (
        productivity[["sprint_id", "sprint_name", "period_start", "sprint_end", "working_days"]]
        .drop_duplicates()
        .sort_values("period_start")
        .reset_index(drop=True)
    )
    sprint_labels = {
        row.sprint_id: (
            f"{row.sprint_name} · {row.sprint_id} "
            f"({row.period_start:%d %b}–{row.sprint_end:%d %b %Y})"
        )
        for row in sprints.itertuples(index=False)
    }
    all_teams = "All teams"
    team_ids = teams["team_id"].tolist()
    team_labels = teams.set_index("team_id")["team_name"].to_dict()
    selected_sprint = st.sidebar.selectbox(
        "Sprint",
        sprints["sprint_id"].tolist(),
        index=len(sprints) - 1,
        format_func=lambda value: sprint_labels[value],
        key="productivity_sprint",
    )
    selected_team = st.sidebar.selectbox(
        "Team",
        [all_teams, *team_ids],
        format_func=lambda value: all_teams if value == all_teams else f"{team_labels[value]} · {value}",
        key="productivity_team",
    )
    selected_sprint_data = productivity.loc[
        productivity["sprint_id"] == selected_sprint
    ].copy()
    displayed = selected_sprint_data
    if selected_team != all_teams:
        displayed = displayed.loc[displayed["team_id"] == selected_team]
    if displayed.empty:
        st.info("No reportable team/sprint group matches these filters.")
        return

    sprint = sprints.loc[sprints["sprint_id"] == selected_sprint].iloc[0]
    st.markdown('<div class="hero-title">Team productivity</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-copy">Compare delivery within each team over time. '
        'Use team size, work type and sprint length as context—not as a leaderboard.</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Selected sprint: {sprint['sprint_name']} · {selected_sprint} · "
        f"{sprint['working_days']} working days"
    )

    total_points = float(displayed["velocity_points"].fillna(0).sum())
    total_blocked = int(displayed["blocked_tasks"].sum())
    total_reopened = int(displayed["reopened_tasks"].sum())
    total_cancelled = int(displayed["cancelled_tasks"].sum())
    metric_columns = st.columns(4)
    metric_columns[0].metric("Completed story points", f"{total_points:,.0f}")
    metric_columns[1].metric("Currently blocked", f"{total_blocked:,}")
    metric_columns[2].metric("Tasks reopened", f"{total_reopened:,}")
    metric_columns[3].metric("Cancelled (excluded)", f"{total_cancelled:,}")

    rules = metric_rules.set_index("metric_id")
    cancelled_rule = (
        "Cancelled tasks are excluded from planned-task denominators, velocity, "
        "on-time rate and cycle time; their count is shown separately. Blocked "
        "tasks remain planned work but are highlighted. Reopened tasks remain "
        "in the completion metrics when their current status is Done and are "
        "reported separately as rework."
    )
    st.subheader("Metric rules")
    st.markdown(
        "- **Velocity (M24):** sum of story points for tasks whose current status is "
        "Done in the sprint; cancelled tasks contribute no points. It is not a "
        "productivity ranking across teams.\n"
        "- **Cycle time (M25):** average calendar days from started_date to "
        "completed_date for Done tasks with both dates; cancelled tasks are excluded.\n"
        "- **On-time rate (M23):** Done tasks marked completed_on_time = Y divided "
        "by all Done tasks in the sprint; cancelled tasks are excluded.\n"
        "- **Completion rate (M22):** Done tasks divided by non-cancelled tasks "
        "in the sprint.\n"
        f"- **Cancelled / blocked / reopened:** {cancelled_rule}\n"
        f"- **Small groups:** team/sprint groups with fewer than "
        f"{int(rules.loc['M22', 'minimum_group_size_numeric'])} non-cancelled tasks "
        "are suppressed from this report."
    )

    st.subheader("Team comparison · selected sprint")
    st.caption(
        "Velocity is context-dependent; team active-member counts, sprint lengths "
        "and work mix differ. Cycle time is lower-is-better; on-time rate is higher-is-better."
    )
    chart_data = displayed.copy()
    chart_data["team"] = chart_data["team_name"] + " · " + chart_data["team_id"]
    velocity_chart = px.bar(
        chart_data.sort_values("velocity_points"),
        x="velocity_points", y="team", orientation="h",
        labels={"velocity_points": "Completed story points", "team": "Team"},
        hover_data=["active_members", "planned_tasks", "task_types", "working_days"],
    )
    velocity_chart.update_traces(marker_color=TEAL)
    velocity_chart.update_layout(
        height=max(320, 38 * len(chart_data)),
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Story points (context-dependent)", yaxis_title=None,
    )
    completion_chart = px.bar(
        chart_data.sort_values("on_time_rate"),
        x="on_time_rate", y="team", orientation="h",
        labels={"on_time_rate": "On-time delivery (%)", "team": "Team"},
        hover_data=["active_members", "planned_tasks", "task_types", "working_days"],
    )
    completion_chart.update_traces(marker_color=AMBER)
    completion_chart.update_layout(
        height=max(320, 38 * len(chart_data)),
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="On-time delivery (%)", xaxis_ticksuffix="%", yaxis_title=None,
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(velocity_chart, width="stretch", config={"displayModeBar": False})
    with right:
        st.plotly_chart(completion_chart, width="stretch", config={"displayModeBar": False})

    if selected_team == all_teams:
        st.subheader("Cycle time · selected sprint")
        cycle_chart = px.bar(
            chart_data.sort_values("average_cycle_days"),
            x="average_cycle_days", y="team", orientation="h",
            labels={"average_cycle_days": "Average cycle time (days)", "team": "Team"},
            hover_data=["active_members", "planned_tasks", "task_types", "working_days"],
        )
        cycle_chart.update_traces(marker_color=TEAL)
        cycle_chart.update_layout(
            height=max(320, 38 * len(chart_data)),
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Calendar days (lower is better)", yaxis_title=None,
        )
        st.plotly_chart(cycle_chart, width="stretch", config={"displayModeBar": False})
    else:
        trend_data = productivity.loc[productivity["team_id"] == selected_team].copy()
        st.subheader(f"{team_labels[selected_team]} · sprint trend")
        velocity_trend = px.line(
            trend_data, x="period_start", y="velocity_points", markers=True,
            labels={"period_start": "Sprint", "velocity_points": "Story points"},
        )
        velocity_trend.update_traces(line_color=TEAL)
        velocity_trend.update_layout(
            height=290, margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=None, yaxis_title="Completed story points",
        )
        cycle_trend = px.line(
            trend_data, x="period_start", y="average_cycle_days", markers=True,
            labels={"period_start": "Sprint", "average_cycle_days": "Cycle time (days)"},
        )
        cycle_trend.update_traces(line_color=AMBER)
        cycle_trend.update_layout(
            height=290, margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=None, yaxis_title="Calendar days",
        )
        trend_left, trend_right = st.columns(2)
        with trend_left:
            st.plotly_chart(velocity_trend, width="stretch", config={"displayModeBar": False})
        with trend_right:
            st.plotly_chart(cycle_trend, width="stretch", config={"displayModeBar": False})

    st.subheader("Blocked and reopened work · selected sprint")
    work_chart_data = displayed.copy()
    work_chart_data["team"] = work_chart_data["team_name"] + " · " + work_chart_data["team_id"]
    work_chart_data = work_chart_data.melt(
        id_vars=["team"],
        value_vars=["blocked_tasks", "reopened_tasks"],
        var_name="work_signal",
        value_name="tasks",
    )
    work_chart_data["work_signal"] = work_chart_data["work_signal"].map(
        {"blocked_tasks": "Blocked now", "reopened_tasks": "Reopened at least once"}
    )
    work_chart = px.bar(
        work_chart_data, x="tasks", y="team", color="work_signal",
        orientation="h", barmode="group",
        color_discrete_map={"Blocked now": AMBER, "Reopened at least once": TEAL},
        labels={"tasks": "Tasks", "team": "Team", "work_signal": "Signal"},
    )
    work_chart.update_layout(
        height=max(320, 38 * len(displayed)),
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Tasks (categories can overlap)", yaxis_title=None,
    )
    st.plotly_chart(work_chart, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Blocked is current status; reopened means reopened_count > 0. "
        "These groups may overlap and are not additive."
    )
    st.dataframe(
        displayed[[
            "team_name", "team_id", "active_members", "planning_cadence",
            "task_types", "planned_tasks", "cancelled_tasks",
            "blocked_tasks", "reopened_tasks", "reopen_events",
            "velocity_points", "average_cycle_days", "on_time_rate",
        ]].rename(columns={
            "team_name": "Team", "team_id": "ID",
            "active_members": "Active members",
            "planning_cadence": "Planning cadence",
            "task_types": "Task types in sprint",
            "planned_tasks": "Planned (excl. cancelled)",
            "cancelled_tasks": "Cancelled",
            "blocked_tasks": "Blocked now",
            "reopened_tasks": "Reopened tasks",
            "reopen_events": "Reopen events",
            "velocity_points": "Velocity (points)",
            "average_cycle_days": "Cycle time (days)",
            "on_time_rate": "On-time (%)",
        }),
        hide_index=True,
        width="stretch",
    )

    st.header("Three findings")
    highest_velocity = displayed.loc[displayed["velocity_points"].idxmax()]
    highest_reopened = displayed.loc[displayed["reopened_tasks"].idxmax()]
    highest_blocked = displayed.loc[displayed["blocked_tasks"].idxmax()]
    if selected_team == all_teams:
        velocity_finding = (
            f'Highest selected-sprint velocity: <b>{highest_velocity["team_name"]}</b> '
            f'delivered {highest_velocity["velocity_points"]:.0f} story points; '
            "velocity is not a cross-team productivity ranking."
        )
        reopened_finding = (
            f'Most reopened work: <b>{highest_reopened["team_name"]}</b> had '
            f'{int(highest_reopened["reopened_tasks"])} reopened tasks and '
            f'{int(highest_reopened["reopen_events"])} reopen events.'
        )
        blocked_finding = (
            f'Most currently blocked work: <b>{highest_blocked["team_name"]}</b> '
            f'had {int(highest_blocked["blocked_tasks"])} blocked tasks; check this '
            f'alongside its {highest_blocked["on_time_rate"]:.1f}% on-time delivery '
            f'rate and {highest_blocked["average_cycle_days"]:.1f}-day average cycle time.'
        )
    else:
        selected = displayed.iloc[0]
        velocity_finding = (
            f'Selected team <b>{selected["team_name"]}</b> delivered '
            f'{selected["velocity_points"]:.0f} story points in this sprint.'
        )
        reopened_finding = (
            f'Selected team <b>{selected["team_name"]}</b> had '
            f'{int(selected["reopened_tasks"])} reopened tasks and '
            f'{int(selected["reopen_events"])} reopen events.'
        )
        blocked_finding = (
            f'Selected team <b>{selected["team_name"]}</b> had '
            f'{int(selected["blocked_tasks"])} currently blocked tasks, '
            f'{selected["on_time_rate"]:.1f}% on-time delivery and '
            f'{selected["average_cycle_days"]:.1f}-day average cycle time.'
        )
    st.markdown(
        f'<div class="finding">{velocity_finding}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="finding">{reopened_finding}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="finding">{blocked_finding}</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Team health is not determined by one metric. A team with higher velocity "
        "but more reopened work needs its quality, workload and work mix reviewed "
        "before calling it healthier."
    )


render_productivity_page()
