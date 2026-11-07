"""Incident detail + human-in-loop approval workflow."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json

import plotly.graph_objects as go
import streamlit as st

from admin import api_client
from admin.styles import format_dt, setup_page, status_badge

setup_page("AegisOps — Incident", "🚨")

st.title("🚨 Incident Detail")

# ---------- Incident selector ----------
try:
    incidents = api_client.list_incidents(limit=200)
except Exception as e:
    st.error(f"Failed to list incidents: {e}")
    st.stop()

if not incidents:
    st.info("No incidents yet. Analyze a run from the Dashboard first.")
    st.stop()

ids = [i["incident_id"] for i in incidents]

# Default from session state if dashboard pushed one
default_id = st.session_state.get("last_incident_id")
default_idx = ids.index(default_id) if default_id in ids else 0

incident_id = st.selectbox("Incident", ids, index=default_idx)
st.session_state["last_incident_id"] = incident_id

try:
    detail = api_client.get_incident(incident_id)
except Exception as e:
    st.error(f"Failed to load incident: {e}")
    st.stop()

if detail is None:
    st.error(f"Incident '{incident_id}' not found")
    st.stop()

# ---------- Header ----------
st.markdown(
    f"### `{detail['incident_id']}` {status_badge(detail['status'])}",
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
c1.markdown(f"**Scenario**  \n{detail['scenario']}")
c2.markdown(f"**Category**  \n{detail['category']}")
c3.markdown(f"**Service**  \n{detail['service'] or '—'}")
c4.markdown(f"**Severity**  \n{detail['severity']:.1f} / 3.0")

st.caption(f"Run: `{detail['run_id']}` · Created: {format_dt(detail['created_at'])}")

st.divider()

# ---------- Analysis ----------
analysis = detail["analysis"]
root_cause = analysis.get("root_cause") or {}
remediation = analysis.get("remediation") or {}
guardrail_check = remediation.get("guardrail_check") or {}

st.subheader("🧠 Root Cause (LLM)")
st.write(root_cause.get("hypothesis") or "—")

evidence = (root_cause.get("evidence") or {}).get("llm_evidence") or []
if evidence:
    st.markdown("**Evidence**")
    for e in evidence:
        st.markdown(f"- {e}")

cands = root_cause.get("candidates") or []
if cands:
    st.markdown("**Candidates (ranked)**")
    st.dataframe(
        [
            {
                "service": c.get("service"),
                "metric": c.get("metric"),
                "severity": c.get("severity"),
                "baseline_ratio": c.get("baseline_ratio"),
                "reason": (c.get("reason") or "")[:80],
            }
            for c in cands
        ],
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ---------- Guardrails panel ----------
st.subheader("🛡️ Guardrails")
gc_pass = guardrail_check.get("passed", detail["guardrail_passed"])
if gc_pass:
    st.success("✅ All guardrail checks passed")
else:
    st.error("❌ Guardrail violations detected")
    for v in guardrail_check.get("violations") or detail.get("guardrail_violations", []):
        st.markdown(f"- `{v}`")
    for w in guardrail_check.get("warnings") or []:
        st.warning(w)
red = guardrail_check.get("redactions_applied", 0)
if red:
    st.info(f"🔒 {red} PII redaction(s) applied to remediation text")

st.divider()

# ---------- Remediation ----------
st.subheader("🔧 Proposed Remediation")
r1, r2, r3 = st.columns(3)
r1.markdown(f"**Action**  \n`{remediation.get('action')}`")
r2.markdown(f"**Target**  \n`{remediation.get('target_service') or '—'}`")
r3.markdown(f"**Risk**  \n`{remediation.get('risk_level')}`")

st.markdown(f"**Reason:** {remediation.get('reason') or '—'}")

steps = remediation.get("steps") or []
if steps:
    st.markdown("**Steps**")
    for s in steps:
        with st.container():
            st.markdown(
                f"**{s.get('order')}. {s.get('action')}**  ·  risk={s.get('risk')}"
            )
            if s.get("command"):
                st.code(s["command"], language="bash")
            if s.get("reason"):
                st.caption(s["reason"])

st.divider()

# ---------- Timeline ----------
st.subheader("🕒 Timeline")
timeline = analysis.get("timeline") or []
if timeline:
    for t in timeline:
        extras = {k: v for k, v in t.items() if k not in ("agent", "action")}
        st.markdown(
            f"**{t.get('agent')}** → `{t.get('action')}` "
            + (f"· {json.dumps(extras, default=str)[:100]}" if extras else "")
        )
else:
    st.caption("No timeline captured.")

st.divider()

# ---------- Approval workflow ----------
st.subheader("✅ Human-in-Loop Approval")

status = detail["status"]

if status == "pending":
    approver = st.text_input("Your name", value="oncall-eng")
    role = st.selectbox("Your role", ["operator", "admin"], index=0)
    reject_reason = st.text_input("Rejection reason (if rejecting)", value="")

    colA, colB = st.columns(2)
    with colA:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            if not approver.strip():
                st.error("Approver name required")
            else:
                try:
                    api_client.approve(incident_id, approver.strip(), role=role)
                    st.success("Approved — refreshing…")
                    st.rerun()
                except Exception as e:
                    st.error(f"Approve failed: {e}")
    with colB:
        if st.button("❌ Reject", use_container_width=True):
            if not reject_reason.strip():
                st.error("Rejection reason required")
            elif not approver.strip():
                st.error("Approver name required")
            else:
                try:
                    api_client.reject(
                        incident_id, approver.strip(), reject_reason.strip()
                    )
                    st.success("Rejected — refreshing…")
                    st.rerun()
                except Exception as e:
                    st.error(f"Reject failed: {e}")

elif status == "approved":
    st.info(
        f"Approved by **{detail.get('approved_by') or '—'}** "
        f"at {format_dt(detail.get('approved_at'))}"
    )
    executor = st.text_input("Executor name", value="oncall-eng")
    if st.button("⚙️ Execute (dry-run)", type="primary"):
        if not executor.strip():
            st.error("Executor name required")
        else:
            try:
                api_client.execute(incident_id, executor.strip())
                st.success("Executed — refreshing…")
                st.rerun()
            except Exception as e:
                st.error(f"Execute failed: {e}")

elif status == "rejected":
    st.error(
        f"Rejected by **{detail.get('approved_by') or '—'}** — "
        f"reason: {detail.get('rejection_reason') or '—'}"
    )

elif status == "executed":
    st.success(
        f"Executed by **{detail.get('executed_by') or '—'}** "
        f"at {format_dt(detail.get('executed_at'))}"
    )
    out = detail.get("execution_output") or ""
    if out:
        st.markdown("**Execution log (simulated)**")
        st.code(out, language="text")