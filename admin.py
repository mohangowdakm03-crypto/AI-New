from __future__ import annotations

import streamlit as st

from db import (
    delete_student_by_usn,
    fetch_joined_records,
    fetch_leaderboard,
    fetch_student_summary,
    reset_database,
)


def _render_admin_dashboard_content() -> None:
    action_col_1, action_col_2 = st.columns([1, 2])
    with action_col_1:
        if st.button("Refresh Now", use_container_width=True):
            st.rerun()
    with action_col_2:
        live_refresh = st.checkbox(
            "Enable live refresh (every 15 seconds)",
            value=False,
            key="admin_live_refresh",
        )
        st.caption(
            "Manual refresh is smoother. Live refresh can briefly dim the dashboard while data reloads."
        )

    summary = fetch_student_summary()
    attempts = fetch_joined_records()
    leaderboard = fetch_leaderboard()

    if summary.empty:
        st.info("No student records found yet.")
    else:
        filter_col_1, filter_col_2 = st.columns(2)
        with filter_col_1:
            usn_filter = st.text_input("Search by USN", placeholder="Enter USN")
        with filter_col_2:
            name_filter = st.text_input("Search by Name", placeholder="Enter student name")

        filtered_summary = summary.copy()
        filtered_attempts = attempts.copy()

        if usn_filter.strip():
            filtered_summary = filtered_summary[
                filtered_summary["usn"].astype(str).str.contains(usn_filter.strip(), case=False, na=False)
            ]
            filtered_attempts = filtered_attempts[
                filtered_attempts["usn"].astype(str).str.contains(usn_filter.strip(), case=False, na=False)
            ]

        if name_filter.strip():
            filtered_summary = filtered_summary[
                filtered_summary["name"].astype(str).str.contains(name_filter.strip(), case=False, na=False)
            ]
            filtered_attempts = filtered_attempts[
                filtered_attempts["name"].astype(str).str.contains(name_filter.strip(), case=False, na=False)
            ]

        metric_col_1, metric_col_2 = st.columns(2)
        with metric_col_1:
            avg_score = float(filtered_summary["average_score"].fillna(0).mean()) if not filtered_summary.empty else 0.0
            st.metric("Average Score", f"{avg_score:.2f}")
        with metric_col_2:
            total_attempts = int(filtered_attempts["score"].notna().sum()) if not filtered_attempts.empty else 0
            st.metric("Total Attempts", total_attempts)

        st.markdown("### Student Summary")
        st.dataframe(filtered_summary, use_container_width=True, hide_index=True)

        st.markdown("### Attempt Records")
        st.dataframe(filtered_attempts, use_container_width=True, hide_index=True)

        st.markdown("### Leaderboard")
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)

    st.markdown("### Delete Specific Student")
    delete_usn = st.text_input("USN to delete", placeholder="Enter USN")
    confirm_delete = st.checkbox("Are you sure? This cannot be undone", key="confirm_delete_student")
    if st.button("Delete Student", use_container_width=True):
        if not delete_usn.strip():
            st.error("Please enter a USN.")
        elif not confirm_delete:
            st.warning("Please confirm before deleting a student.")
        else:
            deleted = delete_student_by_usn(delete_usn)
            if deleted:
                st.success(f"Deleted student data for {delete_usn.strip().lower()}.")
                st.rerun()
            else:
                st.error("Student not found.")

    st.markdown("### Reset Database")
    st.warning("This will delete all student and score records.")
    confirm_reset = st.checkbox("I understand that this will delete all data", key="confirm_reset_database")
    if st.button("Reset Database", use_container_width=True):
        if not confirm_reset:
            st.warning("Please confirm before resetting the database.")
        else:
            reset_database()
            st.success("All database records have been deleted.")
            st.rerun()


if hasattr(st, "fragment"):

    @st.fragment
    def _render_admin_dashboard_fragment() -> None:
        _render_admin_dashboard_content()

else:

    def _render_admin_dashboard_fragment() -> None:
        _render_admin_dashboard_content()


def render_admin_dashboard() -> None:
    st.markdown("## Admin Dashboard")
    st.caption("Use manual refresh for the cleanest view, or enable slower live refresh if needed.")
    if st.session_state.get("admin_live_refresh") and hasattr(st, "fragment"):
        st.caption("Live refresh is active. The dashboard will update every 15 seconds.")
        _render_live_admin_tick()
    _render_admin_dashboard_fragment()


if hasattr(st, "fragment"):

    @st.fragment(run_every="15s")
    def _render_live_admin_tick() -> None:
        st.caption("")
