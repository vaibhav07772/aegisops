"""Analytics dashboard — pulls live Prometheus metrics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

from admin import api_client
from admin.styles import setup_page

setup_page("AegisOps — Analytics", "📊")

st.title("📊 System Analytics")
st.caption("Live telemetry from Prometheus (LLM costs, cache performance, guardrails)")

API_BASE = api_client.BASE_URL

@st.cache_data(ttl=10)
def fetch_prometheus_metrics() -> dict:
    """Scrape /metrics and parse into a dict for easy display."""
    try:
        resp = httpx.get(f"{API_BASE}/metrics", timeout=10.0)
        resp.raise_for_status()
        return {"ok": True, "text": resp.text}
    except Exception as e:
        return {"ok": False, "error": str(e), "text": ""}

def extract_metric(text: str, metric_name: str) -> float:
    """Helper to pull a specific metric from raw Prom text."""
    for line in text.splitlines():
        if line.startswith(f"{metric_name} ") or line.startswith(f"{metric_name}{{"):
            try:
                # Handle labels or no labels
                value_str = line.split(" ")[-1]
                return float(value_str)
            except ValueError:
                pass
    return 0.0

with st.spinner("Fetching metrics..."):
    metrics_data = fetch_prometheus_metrics()

if not metrics_data["ok"]:
    st.error(f"Failed to fetch Prometheus metrics: {metrics_data.get('error')}")
    st.stop()

raw_metrics = metrics_data["text"]

# --- Top-level KPIs ---
total_cost = extract_metric(raw_metrics, "aegisops_llm_cost_usd_total")
cache_hits = extract_metric(raw_metrics, "aegisops_llm_cache_total{result=\"hit\"}")
cache_misses = extract_metric(raw_metrics, "aegisops_llm_cache_total{result=\"miss\"}")
total_incidents = extract_metric(raw_metrics, "aegisops_incidents_total")
guardrail_blocks = extract_metric(raw_metrics, "aegisops_guardrail_blocks_total")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total LLM Cost", f"${total_cost:.4f}")
col2.metric("Incidents Processed", int(total_incidents) if total_incidents else "0")
col3.metric("Cache Hits", int(cache_hits))
col4.metric("Guardrail Blocks", int(guardrail_blocks))

st.divider()

# --- Cache Performance Chart ---
st.subheader("⚡ Semantic Cache Performance")
if cache_hits > 0 or cache_misses > 0:
    total_requests = cache_hits + cache_misses
    hit_rate = cache_hits / total_requests if total_requests > 0 else 0
    
    fig = px.pie(
        values=[cache_hits, cache_misses],
        names=["Cache Hit", "Cache Miss"],
        hole=0.6,
        color_discrete_sequence=["#28a745", "#dc3545"]
    )
    fig.update_layout(
        annotations=[dict(text=f"{hit_rate:.1%}", x=0.5, y=0.5, font_size=20, showarrow=False)],
        showlegend=True,
        height=300,
        margin=dict(t=30, b=0, l=0, r=0),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No cache metrics recorded yet. Analyze an incident to generate data.")

st.divider()

# --- Agent Timings (if available) ---
st.subheader("⏱️ Agent Latency (p95)")
st.caption("Pulled from `aegisops_agent_duration_seconds` histogram. This may require a few incident runs to populate.")

# LangSmith Hint
st.info("💡 **Deep Tracing (LangSmith):** Check [smith.langchain.com](https://smith.langchain.com) under project `aegisops-prod` for full agent traces, prompts, and token usage.")