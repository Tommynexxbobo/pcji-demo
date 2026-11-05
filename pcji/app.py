import streamlit as st
import pandas as pd
import os
import subprocess
import sys

from modules import data_access, engine, style
from modules import m1_executive, m2_journey, m3_friction, m4_predictive, m5_customer360, m6_intervention

st.set_page_config(page_title="PCJI — Proactive Customer Journey Intelligence", layout="wide", page_icon="🏦")
style.inject_css()

APP_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(APP_DIR, "data", "pcji.db")

if not os.path.exists(DB_PATH):
    # First run on a fresh deployment (e.g. Streamlit Community Cloud) - the
    # repo ships code only, not the ~75MB generated database, so build it now.
    with st.spinner("First run: generating the synthetic 25,000-customer banking dataset (under a minute)..."):
        python_bin = sys.executable or "python3"
        result = subprocess.run(
            [python_bin, os.path.join(APP_DIR, "data_generator.py")],
            cwd=APP_DIR, capture_output=True, text=True,
        )
    if result.returncode != 0 or not os.path.exists(DB_PATH):
        st.error("Dataset generation failed. Details below:")
        st.code(result.stdout + "\n" + result.stderr)
        st.stop()


@st.cache_data(show_spinner="Loading customer journeys and computing intelligence layers...")
def bootstrap():
    data = data_access.load_all()
    metrics = engine.compute_customer_metrics(data)
    metrics = engine.compute_health_scores(metrics)
    alerts = engine.generate_alerts(data, metrics)
    return data, metrics, alerts


data, metrics, base_alerts = bootstrap()

if "alerts" not in st.session_state:
    st.session_state.alerts = base_alerts.copy()
if "intervention_log" not in st.session_state:
    st.session_state.intervention_log = []
if "health_overrides" not in st.session_state:
    st.session_state.health_overrides = {}
if "sim_events" not in st.session_state:
    st.session_state.sim_events = []

with st.sidebar:
    st.markdown("### 🏦 Meridian Trust Bank")
    st.markdown("**PCJI**\nProactive Customer Journey Intelligence")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        [
            "1 · Executive Overview",
            "2 · Journey Intelligence",
            "3 · Friction Detection",
            "4 · Predictive Intelligence",
            "5 · Customer 360",
            "6 · Intervention & Recovery",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption(
        "Prototype status: fully functional on synthetic data. Predictive scores and value-at-risk figures "
        "are illustrative until validated against real historical outcomes. Production would connect live "
        "core banking, CRM, contact-centre and VOC systems in place of the synthetic layer."
    )

if page.startswith("1"):
    m1_executive.render(data, metrics, st.session_state.alerts)
elif page.startswith("2"):
    m2_journey.render(data, metrics, st.session_state.alerts)
elif page.startswith("3"):
    m3_friction.render(data, metrics)
elif page.startswith("4"):
    m4_predictive.render(data, metrics, st.session_state.alerts)
elif page.startswith("5"):
    m5_customer360.render(data, metrics)
elif page.startswith("6"):
    m6_intervention.render(data, metrics)
