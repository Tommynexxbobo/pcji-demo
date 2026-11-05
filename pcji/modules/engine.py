"""
PCJI Intelligence Engine
------------------------
Layer 3 (Friction Detection) + Layer 4 (Health & Risk Scoring) +
Layer 5 (Intervention recommendation rules).

All scores/predictions here are ILLUSTRATIVE business-rule heuristics
built for demonstration purposes -- they are explicitly not validated
machine-learning outputs, per the brief's requirement that simulated
predictions never be presented as validated model performance.
"""
import numpy as np
import pandas as pd
from datetime import timedelta

TODAY = pd.Timestamp("2026-11-05")

INTERVENTION_MAP = {
    "Transaction Friction": ("Prioritise transaction investigation & reversal", "Payment Operations"),
    "Delayed Reversal": ("Expedite reversal / compensate customer", "Payment Operations"),
    "Onboarding Abandonment": ("Initiate assisted onboarding outreach", "CAMU / Onboarding Team"),
    "Repeat Complaints": ("Assign dedicated service recovery officer", "Service Recovery Unit"),
    "Declining Engagement": ("Trigger relationship manager outreach", "Relationship Management"),
    "Digital Channel Friction": ("Guided digital channel walkthrough", "Digital Banking Support"),
    "SLA Breach Risk": ("Escalate case ahead of SLA breach", "Service Recovery Unit"),
}


def _severity(score):
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


def compute_customer_metrics(data: dict) -> pd.DataFrame:
    customers = data["customers"].copy()
    txns = data["transactions"]
    digi = data["digital_interactions"]
    comp = data["complaints"]
    fb = data["feedback"]

    m = customers[["customer_id", "segment", "region", "branch", "primary_channel",
                    "onboarding_abandoned", "onboarding_furthest_stage", "is_activated"]].copy()
    m = m.set_index("customer_id")

    # --- Transactions ---
    t = txns.copy()
    t["is_fail"] = t.status.isin(["Failed", "Reversed (Delayed)"])
    agg = t.groupby("customer_id").agg(
        txn_count=("txn_id", "count"),
        txn_fail_count=("is_fail", "sum"),
        last_txn_date=("timestamp", "max"),
    )
    agg["txn_success_rate"] = 1 - (agg.txn_fail_count / agg.txn_count.replace(0, np.nan))
    recent = t[t.timestamp >= TODAY - timedelta(days=14)]
    recent_fail = recent[recent.is_fail].groupby("customer_id").size().rename("fail_14d")
    prior30 = t[(t.timestamp >= TODAY - timedelta(days=60)) & (t.timestamp < TODAY - timedelta(days=30))].groupby("customer_id").size().rename("txn_prior30")
    last30 = t[t.timestamp >= TODAY - timedelta(days=30)].groupby("customer_id").size().rename("txn_last30")
    m = m.join(agg).join(recent_fail).join(prior30).join(last30)

    m["days_since_last_txn"] = (TODAY - m["last_txn_date"]).dt.days
    m["activity_change_pct"] = np.where(
        m["txn_prior30"].fillna(0) > 0,
        (m["txn_last30"].fillna(0) - m["txn_prior30"].fillna(0)) / m["txn_prior30"].fillna(1) * 100,
        0,
    )

    # --- Digital interactions ---
    d = digi.copy()
    dagg = d.groupby("customer_id").agg(
        digi_count=("event_id", "count"),
        digi_success_count=("success", "sum"),
        channel_nunique=("channel", "nunique"),
    )
    dagg["digi_success_rate"] = dagg.digi_success_count / dagg.digi_count.replace(0, np.nan)
    m = m.join(dagg)

    # --- Complaints ---
    c = comp.copy()
    cagg = c.groupby("customer_id").agg(
        complaint_count=("complaint_id", "count"),
        unresolved_count=("status", lambda s: (s != "Resolved").sum()),
        breach_count=("sla_breach", "sum"),
        avg_resolution_hrs=("resolution_time_hrs", "mean"),
        last_complaint_date=("opened_at", "max"),
    )
    m = m.join(cagg)
    m["repeat_complaint"] = m["complaint_count"].fillna(0) >= 2

    # --- Feedback (CSAT/NPS/CES) ---
    f = fb.copy()
    fp = f.pivot_table(index="customer_id", columns="type", values="score", aggfunc="mean")
    m = m.join(fp)
    for col in ["CSAT", "NPS", "CES"]:
        if col not in m.columns:
            m[col] = np.nan

    m = m.reset_index()
    for boolcol in ["onboarding_abandoned", "is_activated"]:
        if boolcol in m.columns:
            m[boolcol] = m[boolcol].astype(bool)
    # fill sensible defaults for customers with no activity in a given domain
    for col in ["txn_count", "txn_fail_count", "fail_14d", "complaint_count", "unresolved_count",
                "breach_count", "digi_count", "digi_success_count"]:
        if col in m.columns:
            m[col] = m[col].fillna(0)
    m["txn_success_rate"] = m["txn_success_rate"].fillna(1.0)
    m["digi_success_rate"] = m["digi_success_rate"].fillna(1.0)
    return m


def compute_health_scores(m: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    # Normalise each factor to 0-100 "healthy" direction
    txn_component = (m["txn_success_rate"].clip(0, 1) * 100)
    complaint_pressure = np.clip(m["complaint_count"].fillna(0) * 12 + m["breach_count"].fillna(0) * 8, 0, 100)
    complaint_component = 100 - complaint_pressure
    digi_component = (m["digi_success_rate"].clip(0, 1) * 100)
    activity_component = np.clip(100 + m["activity_change_pct"].fillna(0), 0, 100)
    csat_norm = (m["CSAT"].fillna(3.5) / 5 * 100)
    nps_norm = ((m["NPS"].fillna(6) + 0) / 10 * 100)
    ces_norm = 100 - (m["CES"].fillna(3) / 5 * 100)  # lower effort = healthier
    feedback_component = (csat_norm + nps_norm + ces_norm) / 3

    m["journey_health_score"] = (
        txn_component * 0.30 +
        complaint_component * 0.25 +
        digi_component * 0.15 +
        activity_component * 0.15 +
        feedback_component * 0.15
    ).round(1)

    m.loc[m["onboarding_abandoned"], "journey_health_score"] = np.minimum(
        m.loc[m["onboarding_abandoned"], "journey_health_score"].fillna(50), 45
    )

    def bucket(s):
        if pd.isna(s):
            return "Healthy"
        if s >= 75:
            return "Healthy"
        if s >= 60:
            return "Watchlist"
        if s >= 40:
            return "At Risk"
        return "Critical"

    m["risk_category"] = m["journey_health_score"].apply(bucket)

    # --- Specific risk sub-scores (illustrative) ---
    m["disengagement_risk"] = np.clip(
        (-m["activity_change_pct"].fillna(0)).clip(lower=0) * 0.6 +
        (m["days_since_last_txn"].fillna(0) / WINDOW_CAP(m) * 100) * 0.4,
        0, 100
    ).round(0)

    m["onboarding_abandonment_risk"] = np.where(m["onboarding_abandoned"], 100, 0)

    m["repeat_complaint_risk"] = np.clip(m["complaint_count"].fillna(0) * 18, 0, 100).round(0)

    m["sla_breach_risk"] = np.clip(
        (m["breach_count"].fillna(0) * 25) + (m["unresolved_count"].fillna(0) * 15), 0, 100
    ).round(0)

    return m


def WINDOW_CAP(m):
    return 90  # days considered "fully dormant" for normalisation


def generate_alerts(data: dict, m: pd.DataFrame) -> pd.DataFrame:
    """Rule-based friction + predictive alert generation (Module 3 / Module 4)."""
    alerts = []
    aid = 1

    # 1) Repeated transaction failures (individual)
    txns = data["transactions"]
    recent = txns[txns.timestamp >= TODAY - timedelta(days=14)]
    fails = recent[recent.status.isin(["Failed", "Reversed (Delayed)"])]
    fail_counts = fails.groupby("customer_id").size()
    flagged = fail_counts[fail_counts >= 3]
    for cid, cnt in flagged.items():
        last = fails[fails.customer_id == cid].timestamp.max()
        seg = m.loc[m.customer_id == cid, "segment"]
        alerts.append(dict(
            alert_id=f"ALT-{aid:05d}", customer_id=cid, segment=seg.iloc[0] if len(seg) else "Unknown",
            journey_stage="Transactions", friction_category="Transaction Friction",
            severity=_severity(min(100, cnt * 20)),
            triggering_event=f"{int(cnt)} failed/delayed transactions in 14 days",
            detection_time=last, business_impact="Revenue & trust at risk; possible churn trigger",
            recommended_action=INTERVENTION_MAP["Transaction Friction"][0],
            assigned_team=INTERVENTION_MAP["Transaction Friction"][1],
            status="Open",
        ))
        aid += 1

    # 2) Delayed reversals specifically
    delayed = txns[txns.status == "Reversed (Delayed)"]
    delayed_recent = delayed[delayed.timestamp >= TODAY - timedelta(days=21)]
    for _, r in delayed_recent.iterrows():
        alerts.append(dict(
            alert_id=f"ALT-{aid:05d}", customer_id=r.customer_id,
            segment=m.loc[m.customer_id == r.customer_id, "segment"].iloc[0] if (m.customer_id == r.customer_id).any() else "Unknown",
            journey_stage="Transactions", friction_category="Delayed Reversal",
            severity="High",
            triggering_event=f"Delayed reversal on {r.txn_type} ({r.amount:,.0f})",
            detection_time=r.timestamp, business_impact="High complaint/escalation likelihood",
            recommended_action=INTERVENTION_MAP["Delayed Reversal"][0],
            assigned_team=INTERVENTION_MAP["Delayed Reversal"][1], status="Open",
        ))
        aid += 1

    # 3) Onboarding abandonment (segment/individual)
    abandoned = m[m.onboarding_abandoned]
    for stage, grp in abandoned.groupby("onboarding_furthest_stage"):
        if len(grp) < 5:
            continue
        sample_customer = grp.customer_id.iloc[0]
        alerts.append(dict(
            alert_id=f"ALT-{aid:05d}", customer_id=f"{len(grp)} customers", segment="Multiple",
            journey_stage="Onboarding", friction_category="Onboarding Abandonment",
            severity=_severity(min(100, len(grp) / 5)),
            triggering_event=f"{len(grp)} customers stalled at '{stage}'",
            detection_time=TODAY, business_impact=f"~{len(grp)} potential activations at risk",
            recommended_action=INTERVENTION_MAP["Onboarding Abandonment"][0],
            assigned_team=INTERVENTION_MAP["Onboarding Abandonment"][1], status="Open",
        ))
        aid += 1

    # 4) Repeat complaints (individual)
    repeaters = m[(m.repeat_complaint) & (m.complaint_count >= 2)]
    for _, r in repeaters.iterrows():
        alerts.append(dict(
            alert_id=f"ALT-{aid:05d}", customer_id=r.customer_id, segment=r.segment,
            journey_stage="Complaints & Dispute Resolution", friction_category="Repeat Complaints",
            severity=_severity(r.repeat_complaint_risk),
            triggering_event=f"{int(r.complaint_count)} complaints logged",
            detection_time=r.get("last_complaint_date", TODAY), business_impact="High churn probability",
            recommended_action=INTERVENTION_MAP["Repeat Complaints"][0],
            assigned_team=INTERVENTION_MAP["Repeat Complaints"][1], status="Open",
        ))
        aid += 1

    # 5) Declining engagement / dormancy risk
    declining = m[(m.activity_change_pct <= -40) & (m.txn_prior30.fillna(0) >= 2)]
    for _, r in declining.iterrows():
        alerts.append(dict(
            alert_id=f"ALT-{aid:05d}", customer_id=r.customer_id, segment=r.segment,
            journey_stage="Transactions", friction_category="Declining Engagement",
            severity=_severity(r.disengagement_risk),
            triggering_event=f"Transaction activity down {abs(r.activity_change_pct):.0f}% month-on-month",
            detection_time=TODAY, business_impact="Dormancy / silent attrition risk",
            recommended_action=INTERVENTION_MAP["Declining Engagement"][0],
            assigned_team=INTERVENTION_MAP["Declining Engagement"][1], status="Open",
        ))
        aid += 1

    # 6) SLA breach risk on unresolved complaints
    sla_risk = m[(m.unresolved_count >= 1) & (m.sla_breach_risk >= 40)]
    for _, r in sla_risk.iterrows():
        alerts.append(dict(
            alert_id=f"ALT-{aid:05d}", customer_id=r.customer_id, segment=r.segment,
            journey_stage="Complaints & Dispute Resolution", friction_category="SLA Breach Risk",
            severity=_severity(r.sla_breach_risk),
            triggering_event=f"{int(r.unresolved_count)} unresolved case(s), breach history",
            detection_time=TODAY, business_impact="Regulatory/SLA exposure",
            recommended_action=INTERVENTION_MAP["SLA Breach Risk"][0],
            assigned_team=INTERVENTION_MAP["SLA Breach Risk"][1], status="Open",
        ))
        aid += 1

    df = pd.DataFrame(alerts)
    if len(df):
        df["detection_time"] = pd.to_datetime(df["detection_time"])
        df = df.sort_values("detection_time", ascending=False).reset_index(drop=True)
    return df


SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def value_at_risk(m: pd.DataFrame, avg_customer_value: float = 42000) -> dict:
    at_risk = m[m.risk_category.isin(["At Risk", "Critical"])]
    protected = m[m.risk_category.isin(["Healthy", "Watchlist"])]
    return {
        "value_at_risk": len(at_risk) * avg_customer_value,
        "value_protected": len(protected) * avg_customer_value * 0.15,  # illustrative uplift from monitoring
        "customers_at_risk": len(at_risk),
    }
