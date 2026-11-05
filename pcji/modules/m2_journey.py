import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from . import style

STAGE_ORDER = ["Acquisition", "Onboarding", "Activation", "Transactions", "Digital Banking",
               "Support", "Complaints & Dispute Resolution", "Retention & Renewal"]


def render(data, metrics, alerts):
    style.page_header(
        "Customer Journey Intelligence",
        "The Unified Banking Lifecycle",
        "Acquisition → Onboarding → Activation → Transactions → Support → Retention, reconstructed from every touchpoint.",
    )

    customers = data["customers"]

    with st.expander("Filter by segment, product, branch or channel", expanded=False):
        f1, f2, f3 = st.columns(3)
        segs = f1.multiselect("Segment", sorted(customers.segment.unique()))
        regions = f2.multiselect("Region", sorted(customers.region.unique()))
        channels = f3.multiselect("Primary Channel", sorted(customers.primary_channel.unique()))

    cust = customers.copy()
    if segs:
        cust = cust[cust.segment.isin(segs)]
    if regions:
        cust = cust[cust.region.isin(regions)]
    if channels:
        cust = cust[cust.primary_channel.isin(channels)]

    cids = set(cust.customer_id)
    n_total = len(cust)

    onboarding = data["onboarding_events"][data["onboarding_events"].customer_id.isin(cids)]
    txns = data["transactions"][data["transactions"].customer_id.isin(cids)]
    digi = data["digital_interactions"][data["digital_interactions"].customer_id.isin(cids)]
    comp = data["complaints"][data["complaints"].customer_id.isin(cids)]
    ret = data["retention_events"][data["retention_events"].customer_id.isin(cids)]

    # --- Funnel ---
    stage_counts = [
        ("Acquisition", n_total, 0),
        ("KYC Submitted", onboarding[onboarding.stage == "KYC Submitted"].customer_id.nunique(), 0),
        ("KYC Verified", onboarding[onboarding.stage == "KYC Verified"].customer_id.nunique(), 0),
        ("Account Opened", onboarding[onboarding.stage == "Account Opened"].customer_id.nunique(), 0),
        ("Activated (1st Txn)", onboarding[onboarding.stage == "First Transaction (Activated)"].customer_id.nunique(), 0),
    ]
    labels = [s[0] for s in stage_counts]
    values = [s[1] for s in stage_counts]

    left, right = st.columns([1.3, 1])
    with left:
        st.markdown("**Onboarding → Activation Funnel**")
        fig = go.Figure(go.Funnel(
            y=labels, x=values,
            marker=dict(color=[style.NAVY, style.SLATE, style.TEAL, "#C9A227", style.CRIMSON]),
            textinfo="value+percent initial",
        ))
        fig.update_layout(**style.merged_layout(height=360))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("**Stage Performance**")
        rows = []
        prev = n_total
        for lbl, v, _ in stage_counts:
            comp_rate = (v / n_total * 100) if n_total else 0
            abn_rate = 100 - (v / prev * 100) if prev else 0
            rows.append({"Stage": lbl, "Entered": v, "Completion vs Start": f"{comp_rate:.1f}%",
                         "Drop from Prior": f"{abn_rate:.1f}%"})
            prev = v if v else prev
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.write("")
    st.markdown("**Journey Stage Summary (post-activation)**")
    cols = st.columns(4)
    txn_fail = txns.status.isin(["Failed", "Reversed (Delayed)"]).mean() * 100 if len(txns) else 0
    digi_fail = (1 - digi.success.mean()) * 100 if len(digi) else 0
    comp_rate = len(comp) / max(n_total, 1) * 100
    ret_rate = len(ret) / max(n_total, 1) * 100
    with cols[0]:
        style.kpi("Transaction Failure Rate", f"{txn_fail:.1f}%")
    with cols[1]:
        style.kpi("Digital Channel Failure Rate", f"{digi_fail:.1f}%")
    with cols[2]:
        style.kpi("Customers Who Complained", f"{comp_rate:.1f}%")
    with cols[3]:
        style.kpi("Retention/Renewal Touch Rate", f"{ret_rate:.1f}%")

    st.write("")
    st.markdown("**Friction Volume by Journey Stage**")
    je = data["journey_events"]
    je = je[je.customer_id.isin(cids)] if (segs or regions or channels) else je
    stage_friction = je[je.outcome == "Friction"].groupby("journey_stage").size().sort_values(ascending=False)
    if len(stage_friction):
        fig4 = go.Figure(go.Bar(x=stage_friction.values, y=stage_friction.index, orientation="h",
                                  marker_color=style.CRIMSON))
        fig4.update_layout(**style.merged_layout(height=280, xaxis_title="Friction events", yaxis=dict(autorange="reversed")))
        st.plotly_chart(fig4, use_container_width=True)

    st.caption("Drilldowns apply across all charts on this page. Use Module 5 (Customer 360) to reconstruct one customer's full timeline.")
