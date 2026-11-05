import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from . import style
from .engine import value_at_risk, TODAY
from datetime import timedelta


def render(data, metrics, alerts):
    style.page_header(
        "Executive Intelligence Overview",
        "Proactive Customer Journey Intelligence",
        "A single view of journey performance, friction and customer value at risk across Meridian Trust Bank.",
    )

    customers = data["customers"]
    txns = data["transactions"]
    total_customers = len(customers)
    activated = customers[customers.is_activated]
    friction_customers = metrics[metrics.risk_category.isin(["At Risk", "Critical"])]
    open_alerts = alerts[alerts.status.isin(["Open", "In Progress", "Escalated"])] if len(alerts) else alerts
    completion_rate = activated.shape[0] / total_customers * 100
    abandonment_rate = customers.onboarding_abandoned.mean() * 100
    txn_success = 1 - (txns.status.isin(["Failed", "Reversed (Delayed)"]).mean())
    var = value_at_risk(metrics)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        style.kpi("Customers Monitored", f"{total_customers:,}")
    with c2:
        style.kpi("Customers at Risk", f"{len(friction_customers):,}", delta=-abs(len(friction_customers)), delta_good_if_up=True)
    with c3:
        style.kpi("Active Friction Alerts", f"{len(open_alerts):,}")
    with c4:
        style.kpi("Journey Completion Rate", f"{completion_rate:.1f}%")
    with c5:
        style.kpi("Transaction Success Rate", f"{txn_success*100:.1f}%")

    c6, c7, c8 = st.columns(3)
    with c6:
        style.kpi("Onboarding Abandonment Rate", f"{abandonment_rate:.1f}%")
    with c7:
        style.kpi("Value at Risk (illustrative)", f"₦{var['value_at_risk']/1e6:,.1f}M")
    with c8:
        style.kpi("Value Protected (illustrative)", f"₦{var['value_protected']/1e6:,.1f}M")

    st.write("")
    left, right = st.columns([1.1, 1])

    with left:
        st.markdown("**Customer Health Distribution**")
        dist = metrics.risk_category.value_counts().reindex(["Healthy", "Watchlist", "At Risk", "Critical"]).fillna(0)
        fig = go.Figure(go.Bar(
            x=dist.values, y=dist.index, orientation="h",
            marker_color=[style.RISK_COLOR[c] for c in dist.index],
            text=[f"{v:,.0f}" for v in dist.values], textposition="outside",
        ))
        fig.update_layout(**style.merged_layout(height=280, xaxis_title="Customers", yaxis=dict(autorange="reversed")))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("**Health Score by Segment**")
        seg = metrics.groupby("segment")["journey_health_score"].mean().sort_values()
        fig2 = go.Figure(go.Bar(x=seg.values, y=seg.index, orientation="h", marker_color=style.NAVY,
                                  text=[f"{v:.0f}" for v in seg.values], textposition="outside"))
        fig2.update_layout(**style.merged_layout(height=280, xaxis_title="Avg Health Score", xaxis_range=[0, 100]))
        st.plotly_chart(fig2, use_container_width=True)

    st.write("")
    st.markdown("**Transaction Success Rate — Last 12 Weeks**")
    t = txns.copy()
    t["week"] = t.timestamp.dt.to_period("W").apply(lambda p: p.start_time)
    weekly = t[t.timestamp >= TODAY - timedelta(weeks=12)].groupby("week").apply(
        lambda g: 1 - g.status.isin(["Failed", "Reversed (Delayed)"]).mean()
    ).reset_index(name="success_rate")
    fig3 = px.line(weekly, x="week", y="success_rate", markers=True)
    fig3.update_traces(line_color=style.TEAL)
    fig3.update_layout(**style.merged_layout(height=260, yaxis_tickformat=".0%", yaxis_title="Success rate", xaxis_title=""))
    st.plotly_chart(fig3, use_container_width=True)

    st.write("")
    st.markdown("**Most Problematic Journeys (by alert volume)**")
    if len(alerts):
        top = alerts.groupby(["journey_stage", "friction_category"]).size().reset_index(name="alerts").sort_values("alerts", ascending=False).head(8)
        st.dataframe(top, use_container_width=True, hide_index=True)
    else:
        st.info("No active alerts detected.")

    st.caption("Figures are computed live from the synthetic dataset. Journey Health Scores and Value at Risk are illustrative until validated against real historical outcomes.")
