import streamlit as st
import pandas as pd
from . import style


def render(data, metrics, alerts_key="alerts"):
    style.page_header(
        "Proactive Friction Detection",
        "Alert Centre",
        "Individual and systemic friction detected across customer journeys — before it becomes a complaint.",
    )

    alerts = st.session_state[alerts_key]
    if not len(alerts):
        st.info("No friction detected in the current dataset.")
        return

    f1, f2, f3, f4 = st.columns(4)
    cat_filter = f1.multiselect("Friction Category", sorted(alerts.friction_category.unique()))
    sev_filter = f2.multiselect("Severity", ["Critical", "High", "Medium", "Low"])
    stage_filter = f3.multiselect("Journey Stage", sorted(alerts.journey_stage.unique()))
    status_filter = f4.multiselect("Status", sorted(alerts.status.unique()))

    view = alerts.copy()
    if cat_filter:
        view = view[view.friction_category.isin(cat_filter)]
    if sev_filter:
        view = view[view.severity.isin(sev_filter)]
    if stage_filter:
        view = view[view.journey_stage.isin(stage_filter)]
    if status_filter:
        view = view[view.status.isin(status_filter)]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        style.kpi("Total Alerts", f"{len(alerts):,}")
    with c2:
        style.kpi("Open / In Progress", f"{alerts.status.isin(['Open','In Progress']).sum():,}")
    with c3:
        style.kpi("Critical Severity", f"{(alerts.severity=='Critical').sum():,}")
    with c4:
        style.kpi("Escalated", f"{(alerts.status=='Escalated').sum():,}")

    st.write("")
    severity_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    view = view.assign(_rank=view.severity.map(severity_rank)).sort_values(["_rank", "detection_time"], ascending=[True, False]).drop(columns="_rank")

    display = view.copy()
    display["severity"] = display["severity"].apply(lambda s: style.severity_badge(s))
    display["detection_time"] = pd.to_datetime(display["detection_time"]).dt.strftime("%d %b %Y %H:%M")
    show_cols = ["alert_id", "customer_id", "segment", "journey_stage", "friction_category",
                 "severity", "triggering_event", "detection_time", "business_impact",
                 "recommended_action", "assigned_team", "status"]
    st.markdown(
        display[show_cols].rename(columns={
            "alert_id": "Alert ID", "customer_id": "Customer", "segment": "Segment",
            "journey_stage": "Journey Stage", "friction_category": "Category",
            "severity": "Severity", "triggering_event": "Triggering Event",
            "detection_time": "Detected", "business_impact": "Business Impact",
            "recommended_action": "Recommended Action", "assigned_team": "Assigned Team", "status": "Status",
        }).to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown("**Act on an alert**")
    sel = st.selectbox("Select Alert ID", view.alert_id.tolist() if len(view) else [])
    if sel:
        row = alerts[alerts.alert_id == sel].iloc[0]
        st.markdown(
            f"**{row.friction_category}** · {row.customer_id} · {style.severity_badge(row.severity)}  \n"
            f"_{row.triggering_event}_",
            unsafe_allow_html=True,
        )
        b1, b2, b3, b4 = st.columns(4)
        idx = alerts[alerts.alert_id == sel].index
        if b1.button("Approve Intervention", use_container_width=True):
            st.session_state[alerts_key].loc[idx, "status"] = "In Progress"
            _log(sel, row.customer_id, "Approved", row.assigned_team)
            st.rerun()
        if b2.button("Escalate", use_container_width=True):
            st.session_state[alerts_key].loc[idx, "status"] = "Escalated"
            _log(sel, row.customer_id, "Escalated", row.assigned_team)
            st.rerun()
        if b3.button("Mark Resolved", use_container_width=True):
            st.session_state[alerts_key].loc[idx, "status"] = "Resolved"
            st.session_state.health_overrides[row.customer_id] = st.session_state.health_overrides.get(row.customer_id, 0) + 22
            _log(sel, row.customer_id, "Resolved", row.assigned_team)
            st.rerun()
        if b4.button("Reassign Team", use_container_width=True):
            st.session_state[alerts_key].loc[idx, "assigned_team"] = "Service Recovery Unit"
            _log(sel, row.customer_id, "Reassigned", "Service Recovery Unit")
            st.rerun()

    st.caption("Approving, escalating or resolving here updates the case in real time — see Module 6 for the full intervention log and outcome tracking.")


def _log(alert_id, customer_id, action, team):
    st.session_state.intervention_log.append({
        "alert_id": alert_id, "customer_id": customer_id, "action": action,
        "team": team, "timestamp": pd.Timestamp.now(),
    })
