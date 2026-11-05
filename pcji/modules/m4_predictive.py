import streamlit as st
import pandas as pd
from . import style


def _factor_text(row):
    parts = []
    if row.get("activity_change_pct", 0) < -20:
        parts.append(f"activity down {abs(row.activity_change_pct):.0f}% MoM")
    if row.get("days_since_last_txn", 0) and row.days_since_last_txn > 30:
        parts.append(f"{int(row.days_since_last_txn)} days since last transaction")
    if row.get("complaint_count", 0) >= 2:
        parts.append(f"{int(row.complaint_count)} complaints logged")
    if row.get("breach_count", 0) >= 1:
        parts.append("SLA breach history")
    if row.get("txn_success_rate", 1) < 0.8:
        parts.append(f"{(1-row.txn_success_rate)*100:.0f}% transaction failure rate")
    if row.get("onboarding_abandoned", False):
        parts.append(f"stalled at '{row.onboarding_furthest_stage}'")
    return "; ".join(parts) if parts else "composite risk signal"


def render(data, metrics, alerts):
    style.page_header(
        "Predictive Intelligence",
        "Early Warning Signals",
        "Illustrative, rule-based predictions highlighting who is likely to disengage next — and why.",
    )
    st.warning(
        "These are simulated, business-rule-driven predictions for demonstration purposes only. "
        "They are **not** validated machine-learning outputs and should not be treated as production risk scores "
        "until tested against real historical outcomes.",
        icon="⚠️",
    )

    tabs = st.tabs([
        "Likely to Go Dormant (30d)", "Onboarding Abandonment Risk",
        "Repeat Complaint Risk", "SLA Breach Risk",
    ])

    with tabs[0]:
        d = metrics[(metrics.disengagement_risk >= 45) & (metrics.is_activated)].sort_values("disengagement_risk", ascending=False).head(25)
        st.markdown(f"**{(metrics.disengagement_risk >= 45).sum():,} customers** show elevated dormancy signals.")
        _table(d, "disengagement_risk", "Disengagement Risk")

    with tabs[1]:
        d = metrics[metrics.onboarding_abandoned].sort_values("journey_health_score").head(25)
        st.markdown(f"**{metrics.onboarding_abandoned.sum():,} customers** abandoned onboarding before activation.")
        _table(d, "onboarding_abandonment_risk", "Abandonment Risk")

    with tabs[2]:
        d = metrics[metrics.repeat_complaint_risk >= 36].sort_values("repeat_complaint_risk", ascending=False).head(25)
        st.markdown(f"**{(metrics.repeat_complaint_risk >= 36).sum():,} customers** are at risk of repeat complaints.")
        _table(d, "repeat_complaint_risk", "Repeat Complaint Risk")

    with tabs[3]:
        d = metrics[metrics.sla_breach_risk >= 40].sort_values("sla_breach_risk", ascending=False).head(25)
        st.markdown(f"**{(metrics.sla_breach_risk >= 40).sum():,} open cases** are trending toward an SLA breach.")
        _table(d, "sla_breach_risk", "SLA Breach Risk")


def _table(d, score_col, score_label):
    if not len(d):
        st.success("No customers currently meet this risk threshold.")
        return
    rows = []
    for _, r in d.iterrows():
        rows.append({
            "Customer": r.customer_id, "Segment": r.segment, "Region": r.region,
            score_label: f"{r[score_col]:.0f}", "Health Score": f"{r.journey_health_score:.0f}",
            "Contributing Factors": _factor_text(r),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
