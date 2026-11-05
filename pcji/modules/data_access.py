"""Shared data-access layer: SQLite connection + cached query helpers."""
import sqlite3
import os
import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pcji.db")

# SQLite has no native boolean type - these columns come back as 0/1 ints
# and must be cast to real bools so pandas boolean indexing (df[df.col]) works.
BOOL_COLUMNS = {
    "is_activated", "onboarding_abandoned", "is_activation", "success",
    "sla_breach", "repeat_complaint",
}


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data(show_spinner=False)
def load_table(name: str) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(f"SELECT * FROM {name}", conn)
    conn.close()
    for col in df.columns:
        if col.endswith(("_date", "timestamp", "_at")) or col in ("acquisition_date", "open_date"):
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                pass
    for col in df.columns:
        if col in BOOL_COLUMNS:
            df[col] = df[col].astype(bool)
    return df


@st.cache_data(show_spinner=False)
def load_all():
    return {
        "customers": load_table("customers"),
        "accounts": load_table("accounts"),
        "onboarding_events": load_table("onboarding_events"),
        "transactions": load_table("transactions"),
        "digital_interactions": load_table("digital_interactions"),
        "complaints": load_table("complaints"),
        "feedback": load_table("feedback"),
        "retention_events": load_table("retention_events"),
        "journey_events": load_table("journey_events"),
    }
