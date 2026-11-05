import streamlit as st
import pandas as pd
import numpy as np
from . import style
from .engine import INTERVENTION_MAP, _severity

CUS_001 = "CUS-000001"


def render(data, metrics):
    style.page_header(
        "Intervention & Service Recovery",
        "From Detection to Resolution",
        "Operational case management, outcome tracking, and the live demonstration scenario.",
    )

    tab1, tab2 = st.tabs(["Case Queue & Outcomes", "Demonstration Scenario — Customer CUS-000001"])

    with tab1:
        _case_queue()

    with tab2:
        _demo_scenario(data, metrics)


def _case_queue():
    alerts = st.session_state.alerts
    st.markdown("**Cases by Status**")
    cols = st.columns(4)
    for i, s in enumerate(["Open", "In Progress", "Escalated", "Resolved"]):
        with cols[i]:
            style.kpi(s, f"{(alerts.status == s).sum():,}")

    st.write("")
    st.markdown("**Intervention Log**")
    log = pd.DataFrame(st.session_state.intervention_log)
    if len(log):
        log = log.sort_values("timestamp", ascending=False)
        st.dataframe(log, use_container_width=True, hide_index=True)
    else:
        st.info("No interventions logged yet — act on alerts in Module 3 (Friction Detection) or run the demo scenario below.")

    if st.session_state.health_overrides:
        st.write("")
        st.markdown("**Measured Improvement After Intervention**")
        rows = [{"Customer": cid, "Health Score Uplift": f"+{v}"} for cid, v in st.session_state.health_overrides.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _demo_scenario(data, metrics):
    st.markdown(
        "Follow Customer **CUS-000001** through a realistic friction episode — repeated transfer failures, "
        "a channel switch, a delayed-reversal complaint, and declining activity — and watch PCJI detect it, "
        "explain it, and drive it to resolution."
    )

    m_row = metrics[metrics.customer_id == CUS_001].iloc[0]
    override = st.session_state.health_overrides.get(CUS_001, 0)
    health = min(100, m_row.journey_health_score + override)

    c1, c2, c3 = st.columns(3)
    with c1:
        style.kpi("Current Journey Health", f"{health:.0f}")
    with c2:
        style.kpi("Disengagement Risk", f"{m_row.disengagement_risk:.0f}")
    with c3:
        style.kpi("Risk Category", style.risk_badge("Critical" if health < 40 else m_row.risk_category))

    st.write("")
    steps = [
        "Customer successfully opens a Savings Account via the Mobile App.",
        "Attempts five funds transfers over three weeks — all fail with a Core Banking System Error.",
        "Switches to Internet Banking to retry — transfers continue to fail there too (channel-switching signal).",
        "Contacts the Contact Centre about a ₦45,000 delayed reversal; case is escalated.",
        "Transaction activity declines sharply as frustration grows.",
        "PCJI detects the compound pattern and raises a high-priority, explained alert.",
    ]
    for i, s in enumerate(steps, 1):
        st.write(f"**{i}.** {s}")

    st.write("")
    if st.button("▶ Simulate New Friction Event for CUS-000001", type="primary"):
        new_ts = pd.Timestamp.now()
        st.session_state.sim_events.append({
            "event_id": 999000 + len(st.session_state.sim_events),
            "customer_id": CUS_001, "journey_stage": "Transactions", "event_type": "Funds Transfer",
            "channel": "Mobile App", "timestamp": new_ts, "outcome": "Friction",
        })
        new_alert = {
            "alert_id": f"ALT-SIM-{len(st.session_state.sim_events):03d}", "customer_id": CUS_001,
            "segment": "Mass Retail", "journey_stage": "Transactions", "friction_category": "Transaction Friction",
            "severity": "Critical", "triggering_event": "New failed transfer injected live (demo)",
            "detection_time": new_ts, "business_impact": "Revenue & trust at risk; possible churn trigger",
            "recommended_action": INTERVENTION_MAP["Transaction Friction"][0],
            "assigned_team": INTERVENTION_MAP["Transaction Friction"][1], "status": "Open",
        }
        st.session_state.alerts = pd.concat([pd.DataFrame([new_alert]), st.session_state.alerts], ignore_index=True)
        st.session_state.health_overrides[CUS_001] = st.session_state.health_overrides.get(CUS_001, 0) - 8
        st.success("New friction event injected. A high-priority alert has been raised — see Module 3, Friction Detection.")
        st.rerun()

    st.write("")
    colL, colR = st.columns(2)
    with colL:
        if st.button("✓ Simulate Service Recovery & Resolution"):
            st.session_state.health_overrides[CUS_001] = st.session_state.health_overrides.get(CUS_001, 0) + 30
            st.session_state.intervention_log.append({
                "alert_id": "ALT-DEMO", "customer_id": CUS_001, "action": "Resolved — reversal expedited, customer contacted",
                "team": "Service Recovery Unit", "timestamp": pd.Timestamp.now(),
            })
            idx = st.session_state.alerts[st.session_state.alerts.customer_id == CUS_001].index
            st.session_state.alerts.loc[idx, "status"] = "Resolved"
            st.success("Intervention simulated: reversal expedited, service recovery officer assigned, customer contacted.")
            st.rerun()
    with colR:
        if st.button("↺ Reset Demo Scenario"):
            st.session_state.health_overrides.pop(CUS_001, None)
            st.session_state.sim_events = [e for e in st.session_state.sim_events if e["customer_id"] != CUS_001]
            st.session_state.alerts = st.session_state.alerts[~st.session_state.alerts.alert_id.str.startswith("ALT-SIM")].reset_index(drop=True)
            st.session_state.intervention_log = [l for l in st.session_state.intervention_log if l["customer_id"] != CUS_001]
            st.rerun()

    st.caption("This scenario is scripted for demonstration. All other alerts in the Friction Detection centre are detected live from the synthetic dataset's embedded patterns.")
