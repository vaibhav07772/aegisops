"""Shared CSS + helpers for the admin UI."""
from __future__ import annotations

import streamlit as st

CUSTOM_CSS = """
<style>
.block-container { padding-top: 2rem; max-width: 1200px; }
h1, h2, h3 { color: #1f6feb; }
.status-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    margin-left: 6px;
}
.status-pending  { background: #fff4e5; color: #b05a00; }
.status-approved { background: #e6f4ea; color: #0f7b2e; }
.status-rejected { background: #fde7e9; color: #a01820; }
.status-executed { background: #e5f0ff; color: #0947a5; }
.guardrail-ok   { color: #0f7b2e; font-weight: 600; }
.guardrail-fail { color: #a01820; font-weight: 600; }
.kv-table { width: 100%; border-collapse: collapse; }
.kv-table td { padding: 4px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
.kv-table td:first-child { width: 30%; color: #555; font-weight: 600; }
</style>
"""


def setup_page(title: str, icon: str = "🛡️") -> None:
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    return f'<span class="status-badge status-{status}">{status.upper()}</span>'


def format_dt(v) -> str:
    if not v:
        return "—"
    if isinstance(v, str):
        return v.replace("T", " ")[:19]
    return v.strftime("%Y-%m-%d %H:%M:%S")