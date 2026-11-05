"""
PCJI - Synthetic Data Generator
--------------------------------
Generates a fully fictional banking dataset for the Proactive Customer
Journey Intelligence (PCJI) demo. All customers, transactions, complaints
and outcomes are synthetic. Written to a local SQLite database so the
demo runs with zero external dependencies (swap-in for PostgreSQL in a
production build - the schema is plain relational SQL throughout).

Run:  python data_generator.py
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

RNG = np.random.default_rng(42)
N_CUSTOMERS = 25_000
TODAY = datetime(2026, 11, 5)
WINDOW_DAYS = 365

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pcji.db")

BANK_NAME = "Meridian Trust Bank"  # fictional

SEGMENTS = ["Mass Retail", "Youth & Students", "Affluent", "Small Business", "Premium"]
SEGMENT_W = [0.42, 0.18, 0.14, 0.18, 0.08]

CHANNELS = ["Mobile App", "Internet Banking", "USSD", "Branch", "Agent Banking", "Card/POS"]
ACQ_CHANNELS = ["Branch Walk-in", "Digital Self-Service", "Agent Network", "Referral", "Corporate/Payroll"]
REGIONS = ["Lagos", "Abuja (FCT)", "Port Harcourt", "Ibadan", "Kano", "Enugu", "Benin City", "Kaduna"]
BRANCHES = [f"{r} - Branch {n}" for r in REGIONS for n in range(1, 3)]
PRODUCTS = ["Savings Account", "Current Account", "Fixed Deposit", "Personal Loan", "Diaspora Account", "SME Business Account"]

TXN_TYPES = ["Funds Transfer", "Bill Payment", "Airtime/Data", "POS Purchase", "ATM Withdrawal", "Loan Repayment", "Card Payment"]
FAIL_REASONS = ["Insufficient Funds", "Network/Timeout Error", "Daily Limit Exceeded", "Beneficiary Bank Error", "Core Banking System Error", "Card Declined - Issuer"]

COMPLAINT_CATEGORIES = [
    ("Failed Transfer Not Reversed", "Transaction", 48),
    ("Delayed Reversal", "Transaction", 24),
    ("Card Transaction Dispute", "Transaction", 72),
    ("Account Access / Login Issue", "Digital Banking", 24),
    ("Onboarding Document Rejection", "Onboarding", 48),
    ("Unauthorized Debit", "Transaction", 72),
    ("Service Quality - Branch", "Support", 48),
    ("Charges / Fee Dispute", "Transaction", 48),
    ("ATM Dispense Error", "Transaction", 72),
    ("Statement / Account Information Request", "Support", 24),
]

COMPLAINT_CHANNELS = ["Contact Centre", "Email", "Social Media", "Branch", "Chatbot", "Mobile App"]

print(f"Generating synthetic PCJI dataset for {BANK_NAME} ({N_CUSTOMERS:,} customers)...")

# ---------------------------------------------------------------------------
# 1. CUSTOMERS
# ---------------------------------------------------------------------------
customer_ids = [f"CUS-{i:06d}" for i in range(1, N_CUSTOMERS + 1)]
acq_offsets = RNG.integers(30, 900, size=N_CUSTOMERS)  # acquired 30-900 days ago
acq_dates = [TODAY - timedelta(days=int(d)) for d in acq_offsets]

customers = pd.DataFrame({
    "customer_id": customer_ids,
    "segment": RNG.choice(SEGMENTS, N_CUSTOMERS, p=SEGMENT_W),
    "region": RNG.choice(REGIONS, N_CUSTOMERS),
    "branch": RNG.choice(BRANCHES, N_CUSTOMERS),
    "acquisition_channel": RNG.choice(ACQ_CHANNELS, N_CUSTOMERS, p=[0.30, 0.32, 0.18, 0.12, 0.08]),
    "acquisition_date": acq_dates,
    "age_band": RNG.choice(["18-24", "25-34", "35-44", "45-54", "55+"], N_CUSTOMERS, p=[0.14, 0.34, 0.27, 0.16, 0.09]),
    "primary_channel": RNG.choice(CHANNELS, N_CUSTOMERS, p=[0.46, 0.14, 0.18, 0.08, 0.08, 0.06]),
})

# Scripted demo customer - overwritten below with a deliberate story
customers.loc[customers.customer_id == "CUS-000001", "segment"] = "Mass Retail"
customers.loc[customers.customer_id == "CUS-000001", "region"] = "Lagos"
customers.loc[customers.customer_id == "CUS-000001", "primary_channel"] = "Mobile App"
customers.loc[customers.customer_id == "CUS-000001", "acquisition_date"] = TODAY - timedelta(days=58)
CUS_001 = "CUS-000001"

# ---------------------------------------------------------------------------
# 2. ONBOARDING FUNNEL  (Acquisition -> KYC -> Account Opened -> Activated)
# ---------------------------------------------------------------------------
# Each customer has a "furthest stage reached" - creates realistic abandonment
FUNNEL_STAGES = ["Acquired", "KYC Submitted", "KYC Verified", "Account Opened", "First Transaction (Activated)"]
# 100% acquired, drop-off at each subsequent stage
stage_probs = [1.00, 0.93, 0.87, 0.80, 0.71]  # ~29% onboarding abandonment by activation

furthest_idx = np.zeros(N_CUSTOMERS, dtype=int)
u = RNG.random(N_CUSTOMERS)
for i in range(1, len(FUNNEL_STAGES)):
    furthest_idx += (u < stage_probs[i]).astype(int) * (furthest_idx == i - 1)
# simpler reliable approach: sequential bernoulli survival
furthest_idx = np.zeros(N_CUSTOMERS, dtype=int)
survive = np.ones(N_CUSTOMERS, dtype=bool)
step_drop = [0.00, 0.07, 0.065, 0.08, 0.11]  # drop probability moving INTO this stage
for stage_i in range(len(FUNNEL_STAGES)):
    if stage_i == 0:
        reached = np.ones(N_CUSTOMERS, dtype=bool)
    else:
        advance = survive & (RNG.random(N_CUSTOMERS) > step_drop[stage_i])
        reached = advance
        survive = advance
    furthest_idx = np.where(reached, stage_i, furthest_idx)

customers["onboarding_furthest_stage"] = [FUNNEL_STAGES[i] for i in furthest_idx]
customers["onboarding_abandoned"] = furthest_idx < (len(FUNNEL_STAGES) - 1)
customers["is_activated"] = furthest_idx == (len(FUNNEL_STAGES) - 1)

# force CUS-001 to be fully activated (their story starts post-activation)
customers.loc[customers.customer_id == CUS_001, "onboarding_furthest_stage"] = FUNNEL_STAGES[-1]
customers.loc[customers.customer_id == CUS_001, "onboarding_abandoned"] = False
customers.loc[customers.customer_id == CUS_001, "is_activated"] = True

onboarding_rows = []
eid = 1
for idx, row in customers.iterrows():
    reach = FUNNEL_STAGES.index(row["onboarding_furthest_stage"])
    base_ts = row["acquisition_date"]
    for s in range(reach + 1):
        ts = base_ts + timedelta(hours=int(RNG.integers(1, 48)) * (s + 1))
        onboarding_rows.append((eid, row["customer_id"], FUNNEL_STAGES[s], ts, s == len(FUNNEL_STAGES) - 1))
        eid += 1
onboarding_df = pd.DataFrame(onboarding_rows, columns=["event_id", "customer_id", "stage", "timestamp", "is_activation"])
print(f"  onboarding events: {len(onboarding_df):,}")

# ---------------------------------------------------------------------------
# 3. ACCOUNTS
# ---------------------------------------------------------------------------
activated = customers[customers.is_activated].copy()
n_act = len(activated)
acc_rows = []
aid = 1
for _, row in activated.iterrows():
    n_products = RNG.choice([1, 2, 3], p=[0.62, 0.30, 0.08])
    chosen = RNG.choice(PRODUCTS, size=n_products, replace=False)
    for p in chosen:
        open_date = row["acquisition_date"] + timedelta(days=int(RNG.integers(0, 5)))
        acc_rows.append((f"ACC-{aid:07d}", row["customer_id"], p, open_date, row["branch"]))
        aid += 1
accounts = pd.DataFrame(acc_rows, columns=["account_id", "customer_id", "product", "open_date", "branch"])
print(f"  accounts: {len(accounts):,}")

# ---------------------------------------------------------------------------
# 4. CUSTOMER SEGMENT LABELS FOR FRICTION SIMULATION
#    ~12% of activated customers are pre-tagged into a "struggling" cohort
#    so the detection engine has rich, embedded patterns to surface.
# ---------------------------------------------------------------------------
activated = activated.reset_index(drop=True)
n_struggle = int(n_act * 0.12)
struggle_ids = set(RNG.choice(activated.customer_id, size=n_struggle, replace=False))
struggle_ids.add(CUS_001)  # ensure scripted customer is in the struggling cohort
dormant_risk_ids = set(RNG.choice(activated.customer_id, size=int(n_act * 0.09), replace=False))

# ---------------------------------------------------------------------------
# 5. TRANSACTIONS
# ---------------------------------------------------------------------------
txn_rows = []
tid = 1
for _, row in activated.iterrows():
    cid = row["customer_id"]
    is_struggler = cid in struggle_ids
    is_dormant_risk = cid in dormant_risk_ids
    # baseline monthly activity, tapering for dormancy-risk customers
    n_txns = int(RNG.poisson(0.55 if not is_dormant_risk else 0.22) * (WINDOW_DAYS / 30))
    n_txns = max(1, min(n_txns, 40))
    fail_rate = 0.06 if not is_struggler else RNG.uniform(0.22, 0.45)
    # recency weighting: dormancy-risk customers' activity decays toward present
    if is_dormant_risk:
        day_offsets = RNG.triangular(0, WINDOW_DAYS * 0.75, WINDOW_DAYS, n_txns).astype(int)
    else:
        day_offsets = RNG.integers(0, WINDOW_DAYS, n_txns)
    for d in day_offsets:
        ts = TODAY - timedelta(days=int(d), hours=int(RNG.integers(0, 24)))
        status_roll = RNG.random()
        if status_roll < fail_rate:
            status = "Failed"
        elif status_roll < fail_rate + 0.02:
            status = "Reversed (Delayed)"
        else:
            status = "Successful"
        reason = RNG.choice(FAIL_REASONS) if status != "Successful" else None
        txn_rows.append((
            f"TXN-{tid:08d}", cid, RNG.choice(CHANNELS), RNG.choice(TXN_TYPES),
            round(float(RNG.lognormal(9.2, 1.3)), 2), status, reason, ts
        ))
        tid += 1

# --- Inject CUS-001's scripted story: repeated transfer failures + delayed reversal ---
story_start = TODAY - timedelta(days=21)
for k in range(5):
    ts = story_start + timedelta(days=k * 2, hours=int(RNG.integers(0, 12)))
    txn_rows.append((f"TXN-{tid:08d}", CUS_001, "Mobile App", "Funds Transfer",
                      round(float(RNG.lognormal(9.5, 0.8)), 2), "Failed",
                      "Core Banking System Error", ts))
    tid += 1
# the delayed reversal case
reversal_ts = TODAY - timedelta(days=10)
txn_rows.append((f"TXN-{tid:08d}", CUS_001, "Mobile App", "Funds Transfer",
                  45000.00, "Reversed (Delayed)", "Core Banking System Error", reversal_ts))
tid += 1

transactions = pd.DataFrame(txn_rows, columns=["txn_id", "customer_id", "channel", "txn_type", "amount", "status", "failure_reason", "timestamp"])
print(f"  transactions: {len(transactions):,}")

# ---------------------------------------------------------------------------
# 6. DIGITAL INTERACTIONS
# ---------------------------------------------------------------------------
digi_rows = []
did = 1
for _, row in activated.iterrows():
    cid = row["customer_id"]
    is_struggler = cid in struggle_ids
    n_sessions = int(RNG.poisson(0.4) * (WINDOW_DAYS / 30))
    n_sessions = max(1, min(n_sessions, 12))
    fail_rate = 0.04 if not is_struggler else RNG.uniform(0.15, 0.35)
    for _ in range(n_sessions):  # cap per customer to control volume
        d = int(RNG.integers(0, WINDOW_DAYS))
        ts = TODAY - timedelta(days=d, hours=int(RNG.integers(0, 24)))
        success = RNG.random() > fail_rate
        action = RNG.choice(["Login", "Balance Check", "Funds Transfer", "Bill Payment", "View Statement", "Card Management"])
        # channel switching signal: struggler customers bounce between channels
        chan = RNG.choice(["Mobile App", "Internet Banking", "USSD"], p=[0.55, 0.25, 0.20] if not is_struggler else [0.4, 0.3, 0.3])
        digi_rows.append((did, cid, chan, action, ts, success))
        did += 1
    if cid == CUS_001:
        # channel-switching friction signal in the scripted story
        for k in range(4):
            ts = story_start + timedelta(days=k * 3)
            digi_rows.append((did, cid, "Internet Banking", "Funds Transfer", ts, False))
            did += 1
digital = pd.DataFrame(digi_rows, columns=["event_id", "customer_id", "channel", "action", "timestamp", "success"])
print(f"  digital interactions: {len(digital):,}")

# ---------------------------------------------------------------------------
# 7. COMPLAINTS
# ---------------------------------------------------------------------------
comp_rows = []
cidn = 1
for _, row in activated.iterrows():
    cid = row["customer_id"]
    is_struggler = cid in struggle_ids
    n_complaints = RNG.poisson(0.35 if not is_struggler else 2.5)
    n_complaints = min(n_complaints, 8)
    for _ in range(n_complaints):
        cat, stage, sla_hrs = COMPLAINT_CATEGORIES[RNG.integers(0, len(COMPLAINT_CATEGORIES))]
        d = int(RNG.integers(0, WINDOW_DAYS))
        opened = TODAY - timedelta(days=d, hours=int(RNG.integers(0, 24)))
        res_time = float(RNG.gamma(2.0, sla_hrs / 2.2))
        breached = res_time > sla_hrs
        is_resolved = d > 2 or RNG.random() > 0.15
        resolved_at = opened + timedelta(hours=res_time) if is_resolved else None
        comp_rows.append((
            f"CMP-{cidn:07d}", cid, RNG.choice(COMPLAINT_CHANNELS), cat, stage, sla_hrs,
            opened, resolved_at, round(res_time, 1), breached,
            "Resolved" if is_resolved else RNG.choice(["Open", "In Progress", "Escalated"])
        ))
        cidn += 1
    if cid == CUS_001:
        opened = TODAY - timedelta(days=9)
        comp_rows.append((
            f"CMP-{cidn:07d}", cid, "Contact Centre", "Delayed Reversal", "Transaction", 24,
            opened, None, None, True, "Escalated"
        ))
        cidn += 1

complaints = pd.DataFrame(comp_rows, columns=[
    "complaint_id", "customer_id", "channel", "category", "journey_stage", "sla_target_hrs",
    "opened_at", "resolved_at", "resolution_time_hrs", "sla_breach", "status"
])
# repeat-complaint flag: customer has 2+ complaints in the dataset
repeat_counts = complaints.customer_id.value_counts()
complaints["repeat_complaint"] = complaints.customer_id.map(lambda c: repeat_counts.get(c, 0) >= 2)
print(f"  complaints: {len(complaints):,}")

# ---------------------------------------------------------------------------
# 8. FEEDBACK (CSAT / NPS / CES)
# ---------------------------------------------------------------------------
fb_rows = []
fid = 1
for _, row in activated.iterrows():
    cid = row["customer_id"]
    is_struggler = cid in struggle_ids
    n_fb = RNG.poisson(1.1)
    for _ in range(min(n_fb, 5)):
        ftype = RNG.choice(["CSAT", "NPS", "CES"])
        if ftype == "CSAT":
            score = RNG.integers(1, 6) if not is_struggler else RNG.integers(1, 4)
        elif ftype == "NPS":
            score = RNG.integers(0, 11) if not is_struggler else RNG.integers(0, 7)
        else:
            score = RNG.integers(1, 6) if not is_struggler else RNG.integers(3, 6)  # higher CES = more effort = bad
        d = int(RNG.integers(0, WINDOW_DAYS))
        ts = TODAY - timedelta(days=d)
        touchpoint = RNG.choice(["Onboarding", "Transaction", "Support", "Digital Banking"])
        fb_rows.append((fid, cid, ftype, int(score), ts, touchpoint))
        fid += 1
feedback = pd.DataFrame(fb_rows, columns=["feedback_id", "customer_id", "type", "score", "timestamp", "touchpoint"])
print(f"  feedback records: {len(feedback):,}")

# ---------------------------------------------------------------------------
# 9. RETENTION / RENEWAL EVENTS (for journey_events backbone)
# ---------------------------------------------------------------------------
retention_rows = []
rid = 1
for _, row in activated.iterrows():
    cid = row["customer_id"]
    if RNG.random() < 0.35:
        d = int(RNG.integers(0, WINDOW_DAYS))
        ts = TODAY - timedelta(days=d)
        outcome = RNG.choice(["Renewed", "Reviewed - Active", "Upgrade Offered"], p=[0.55, 0.35, 0.10])
        retention_rows.append((rid, cid, ts, outcome))
        rid += 1
retention = pd.DataFrame(retention_rows, columns=["event_id", "customer_id", "timestamp", "outcome"])
print(f"  retention events: {len(retention):,}")

# ---------------------------------------------------------------------------
# 10. UNIFIED JOURNEY EVENTS (backbone used by Journey Intelligence module)
# ---------------------------------------------------------------------------
je_rows = []
jid = 1

for _, r in onboarding_df.iterrows():
    je_rows.append((jid, r.customer_id, "Onboarding", r.stage, "N/A", r.timestamp,
                     "Friction" if False else "Normal"))
    jid += 1

for _, r in transactions.iterrows():
    outcome = "Friction" if r.status in ("Failed", "Reversed (Delayed)") else "Normal"
    je_rows.append((jid, r.customer_id, "Transactions", r.txn_type, r.channel, r.timestamp, outcome))
    jid += 1

for _, r in digital.iterrows():
    outcome = "Normal" if r.success else "Friction"
    je_rows.append((jid, r.customer_id, "Digital Banking", r.action, r.channel, r.timestamp, outcome))
    jid += 1

for _, r in complaints.iterrows():
    outcome = "Friction"
    je_rows.append((jid, r.customer_id, "Complaints & Dispute Resolution", r.category, r.channel, r.opened_at, outcome))
    jid += 1

for _, r in retention.iterrows():
    je_rows.append((jid, r.customer_id, "Retention & Renewal", r.outcome, "N/A", r.timestamp, "Normal"))
    jid += 1

journey_events = pd.DataFrame(je_rows, columns=["event_id", "customer_id", "journey_stage", "event_type", "channel", "timestamp", "outcome"])
journey_events = journey_events.sort_values(["customer_id", "timestamp"]).reset_index(drop=True)
journey_events["event_id"] = range(1, len(journey_events) + 1)
print(f"  unified journey events: {len(journey_events):,}")

# ---------------------------------------------------------------------------
# WRITE TO SQLITE
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
conn = sqlite3.connect(DB_PATH)

customers.to_sql("customers", conn, index=False)
accounts.to_sql("accounts", conn, index=False)
onboarding_df.to_sql("onboarding_events", conn, index=False)
transactions.to_sql("transactions", conn, index=False)
digital.to_sql("digital_interactions", conn, index=False)
complaints.to_sql("complaints", conn, index=False)
feedback.to_sql("feedback", conn, index=False)
retention.to_sql("retention_events", conn, index=False)
journey_events.to_sql("journey_events", conn, index=False)

# useful indexes
cur = conn.cursor()
for tbl, col in [
    ("transactions", "customer_id"), ("digital_interactions", "customer_id"),
    ("complaints", "customer_id"), ("feedback", "customer_id"),
    ("journey_events", "customer_id"), ("accounts", "customer_id"),
    ("onboarding_events", "customer_id"), ("retention_events", "customer_id"),
]:
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_{col} ON {tbl}({col})")
conn.commit()
conn.close()

print(f"\nDone. SQLite database written to: {DB_PATH}")
print(f"Scripted demo customer for the presenter story: {CUS_001}")
