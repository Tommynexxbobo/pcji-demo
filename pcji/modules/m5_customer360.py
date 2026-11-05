import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from . import style

STAGE_COLOR = {
    "Onboarding": style.NAVY, "Transactions": style.SLATE, "Digital Banking": "#C9A227",
    "Complaints & Dispute Resolution": style.CRIMSON, "Retention & Renewal": style.TEAL,
}


def render(data, metrics, default_id="CUS-000001"):
    style.page_header(
        "Customer 360 & Journey Reconstruction",
        "One Customer, Fully Reconstructed",
        "Select any customer to rebuild their journey from acquisition to today.",
    )

    all_ids = metrics.customer_id.tolist()
    default_idx = all_ids.index(default_id) if default_id in all_ids else 0
    cid = st.selectbox("Customer ID", all_ids, index=default_idx)

    cust_row = data["customers"][data["customers"].customer_id == cid].iloc[0]
    m_row = metrics[metrics.customer_id == cid].iloc[0]
    override = st.session_state.get("health_overrides", {}).get(cid, 0)
    health = min(100, m_row.journey_health_score + override)

    c1, c2, c3 = st.columns([1, 1, 1.4])
    with c1:
        st.markdown(f"**{cid}**")
        st.write(f"Segment: {cust_row.segment}")
        st.write(f"Region / Branch: {cust_row.region} — {cust_row.branch}")
        st.write(f"Primary Channel: {cust_row.primary_channel}")
        st.write(f"Acquired: {pd.Timestamp(cust_row.acquisition_date).strftime('%d %b %Y')} via {cust_row.acquisition_channel}")
    with c2:
        accts = data["accounts"][data["accounts"].customer_id == cid]
        st.markdown("**Products Held**")
        if len(accts):
            for p in accts["product"]:
                st.write(f"• {p}")
        else:
            st.write("_No active accounts (onboarding not completed)_")
    with c3:
        risk_cat = m_row.risk_category if override == 0 else ("Healthy" if health >= 75 else m_row.risk_category)
        st.markdown(f"**Journey Health Score**  \n<span style='font-size:2.2rem;font-weight:800;color:{style.NAVY}'>{health:.0f}</span> / 100 &nbsp; {style.risk_badge(risk_cat)}", unsafe_allow_html=True)
        sub1, sub2 = st.columns(2)
        with sub1:
            st.caption(f"Disengagement risk: **{m_row.disengagement_risk:.0f}**")
            st.caption(f"Onboarding abandonment risk: **{m_row.onboarding_abandonment_risk:.0f}**")
        with sub2:
            st.caption(f"Repeat complaint risk: **{m_row.repeat_complaint_risk:.0f}**")
            st.caption(f"SLA breach risk: **{m_row.sla_breach_risk:.0f}**")

    st.write("")
    st.markdown("**Journey Timeline**")
    je = data["journey_events"][data["journey_events"].customer_id == cid].sort_values("timestamp")
    for ev in st.session_state.get("sim_events", []):
        if ev["customer_id"] == cid:
            je = pd.concat([je, pd.DataFrame([ev])], ignore_index=True)
    je = je.sort_values("timestamp")

    if len(je):
        fig = go.Figure()
        for stage, grp in je.groupby("journey_stage"):
            colors = [style.CRIMSON if o == "Friction" else STAGE_COLOR.get(stage, style.SLATE) for o in grp.outcome]
            fig.add_trace(go.Scatter(
                x=grp.timestamp, y=[stage] * len(grp), mode="markers",
                marker=dict(size=11, color=colors, line=dict(width=1, color="white")),
                text=grp.event_type, hovertemplate="%{text}<br>%{x}<extra></extra>",
                showlegend=False,
            ))
        fig.update_layout(**style.merged_layout(height=320, xaxis_title="", yaxis_title=""))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Red markers indicate a friction event at that stage.")
    else:
        st.info("No journey events recorded yet for this customer.")

    st.write("")
    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Recent Complaints**")
        c = data["complaints"][data["complaints"].customer_id == cid].sort_values("opened_at", ascending=False).head(5)
        if len(c):
            st.dataframe(c[["complaint_id", "category", "channel", "opened_at", "status", "sla_breach"]], use_container_width=True, hide_index=True)
        else:
            st.write("_No complaints on record._")
    with colB:
        st.markdown("**Recommended Actions**")
        recs = []
        if m_row.disengagement_risk >= 45:
            recs.append("Trigger relationship manager engagement — declining activity.")
        if m_row.repeat_complaint_risk >= 36:
            recs.append("Assign a dedicated service recovery officer.")
        if m_row.onboarding_abandonment_risk >= 100:
            recs.append("Initiate assisted onboarding outreach.")
        if m_row.sla_breach_risk >= 40:
            recs.append("Escalate open case ahead of SLA breach.")
        if not recs:
            recs.append("No proactive intervention currently required — customer journey is healthy.")
        for r in recs:
            st.write(f"▸ {r}")
