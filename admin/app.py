"""AegisOps Admin — Live Dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from admin import api_client
from admin.styles import format_dt, setup_page, status_badge

setup_page("AegisOps — Dashboard")

st.title("🛡️ AegisOps — Live Dashboard")
st.caption("AI SRE & Incident Response Platform · Human-in-Loop Review")

# ---------- Health strip ----------
try:
    h = api_client.health()
    st.success(f"Backend OK · {h.get('service')} v{h.get('version')} · {h.get('environment')}")
except Exception as e:
    st.error(f"Backend unreachable at {api_client.BASE_URL}: {e}")
    st.stop()

# ---------- Stats ----------
col1, col2, col3, col4 = st.columns(4)

try:
    all_inc = api_client.list_incidents(limit=200)
except Exception as e:
    st.error(f"Failed to fetch incidents: {e}")
    all_inc = []

pending = [i for i in all_inc if i["status"] == "pending"]
approved = [i for i in all_inc if i["status"] == "approved"]
executed = [i for i in all_inc if i["status"] == "executed"]
failed_g = [i for i in all_inc if not i["guardrail_passed"]]

col1.metric("Total Incidents", len(all_inc))
col2.metric("Pending Review", len(pending))
col3.metric("Approved / Executed", f"{len(approved)} / {len(executed)}")
col4.metric("Guardrail Failures", len(failed_g))

st.divider()

# ---------- Trigger new analysis ----------
st.subheader("🔍 Analyze a Run")
try:
    runs = api_client.list_runs()
except Exception:
    runs = []

if not runs:
    st.warning("No ingested runs found. Run `python scripts/ingest_data.py` first.")
else:
    run_ids = [r["run_id"] for r in runs]
    with st.form("analyze_form"):
        selected_run = st.selectbox("Select a run_id", run_ids, index=0)
        submitted = st.form_submit_button("Analyze this run", type="primary")
    if submitted:
        with st.spinner("Running multi-agent analysis… (LLM + RAG, may take 5-10s)"):
            try:
                resp = api_client.analyze_run(selected_run)
                st.success(f"Analysis complete · incident_id={resp['incident_id']}")
                st.session_state["last_incident_id"] = resp["incident_id"]
            except Exception as e:
                st.error(f"Analysis failed: {e}")

    last_id = st.session_state.get("last_incident_id")
    if last_id:
        st.info(f"Last analyzed: **{last_id}**  →  view in *Incident* page")

st.divider()

# ---------- Incidents list ----------
st.subheader("📋 Incidents")
status_filter = st.selectbox(
    "Filter by status", ["all", "pending", "approved", "rejected", "executed"], index=0
)
filtered = all_inc if status_filter == "all" else [i for i in all_inc if i["status"] == status_filter]

if not filtered:
    st.info("No incidents match this filter.")
else:
    df = pd.DataFrame([
        {
            "incident_id": i["incident_id"],
            "scenario": i["scenario"],
            "category": i["category"],
            "service": i["service"] or "—",
            "severity": f"{i['severity']:.1f}",
            "guardrails": "✅" if i["guardrail_passed"] else "❌",
            "status": i["status"].upper(),
            "created": format_dt(i["created_at"]),
            "approved_by": i["approved_by"] or "—",
        }
        for i in filtered
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.caption("👉 To review an incident, use the **Incident** page in the sidebar and enter its ID.")