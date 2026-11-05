"""Shared visual language: brand colors, CSS injection, small UI helpers."""
import streamlit as st

NAVY = "#152850"
CRIMSON = "#B5172E"
TEAL = "#0E7C7B"
SLATE = "#5B6B82"
CREAM = "#F7F4EC"
LIGHT_GRID = "#E7EBF0"

SEVERITY_COLOR = {"Critical": "#B5172E", "High": "#D97B29", "Medium": "#C9A227", "Low": "#5B6B82"}
RISK_COLOR = {"Healthy": "#0E7C7B", "Watchlist": "#C9A227", "At Risk": "#D97B29", "Critical": "#B5172E"}

PLOTLY_TEMPLATE = dict(
    layout=dict(
        font=dict(family="Helvetica, Arial, sans-serif", color=NAVY, size=13),
        paper_bgcolor="white",
        plot_bgcolor="white",
        colorway=[NAVY, CRIMSON, TEAL, "#D97B29", "#C9A227", SLATE],
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(gridcolor=LIGHT_GRID, zeroline=False),
        yaxis=dict(gridcolor=LIGHT_GRID, zeroline=False),
    )
)


def merged_layout(**overrides):
    """Merge override kwargs into the base Plotly layout template, without
    colliding on literal 'xaxis'/'yaxis' dict keys (the common failure mode
    when both the template and a call site set them directly)."""
    base = {k: (dict(v) if isinstance(v, dict) else v) for k, v in PLOTLY_TEMPLATE["layout"].items()}
    for k, v in overrides.items():
        if k in ("xaxis", "yaxis") and isinstance(base.get(k), dict) and isinstance(v, dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return base


def inject_css():
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: #FFFFFF; }}
        .pcji-eyebrow {{
            font-size: 0.72rem; letter-spacing: 0.18em; font-weight: 700;
            color: {CRIMSON}; text-transform: uppercase; margin-bottom: -0.3rem;
        }}
        .pcji-title {{ color: {NAVY}; font-weight: 800; margin-top: 0.1rem; }}
        .pcji-sub {{ color: {SLATE}; font-size: 0.95rem; margin-top: -0.6rem; }}
        .kpi-box {{
            background: linear-gradient(180deg, #FFFFFF 0%, {CREAM} 100%);
            border: 1px solid {LIGHT_GRID}; border-left: 4px solid {NAVY};
            border-radius: 8px; padding: 0.9rem 1.1rem; margin-bottom: 0.4rem;
        }}
        .kpi-label {{ font-size: 0.74rem; color: {SLATE}; text-transform: uppercase; letter-spacing: 0.06em; }}
        .kpi-value {{ font-size: 1.6rem; font-weight: 800; color: {NAVY}; }}
        .kpi-delta-up {{ color: {TEAL}; font-size: 0.82rem; font-weight: 600; }}
        .kpi-delta-down {{ color: {CRIMSON}; font-size: 0.82rem; font-weight: 600; }}
        .badge {{
            display:inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
            font-size: 0.72rem; font-weight: 700; color: white;
        }}
        div[data-testid="stSidebar"] {{ background-color: {NAVY}; }}
        div[data-testid="stSidebar"] * {{ color: #EAEFF5 !important; }}
        div[data-testid="stSidebar"] .stRadio label {{ color: #EAEFF5 !important; }}
        hr {{ border-color: {LIGHT_GRID}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, subtitle: str = ""):
    st.markdown(f"<div class='pcji-eyebrow'>{eyebrow}</div>", unsafe_allow_html=True)
    st.markdown(f"<h2 class='pcji-title'>{title}</h2>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='pcji-sub'>{subtitle}</div>", unsafe_allow_html=True)
    st.write("")


def kpi(label, value, delta=None, delta_good_if_up=True):
    delta_html = ""
    if delta is not None:
        up = delta >= 0
        good = up if delta_good_if_up else not up
        cls = "kpi-delta-up" if good else "kpi-delta-down"
        arrow = "▲" if up else "▼"
        delta_html = f"<div class='{cls}'>{arrow} {abs(delta):.1f}</div>"
    st.markdown(
        f"""<div class="kpi-box">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>""",
        unsafe_allow_html=True,
    )


def severity_badge(sev: str) -> str:
    color = SEVERITY_COLOR.get(sev, "#5B6B82")
    return f"<span class='badge' style='background:{color}'>{sev}</span>"


def risk_badge(cat: str) -> str:
    color = RISK_COLOR.get(cat, "#5B6B82")
    return f"<span class='badge' style='background:{color}'>{cat}</span>"
