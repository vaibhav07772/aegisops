"""Thin HTTP client for the Streamlit UI → FastAPI backend."""
from __future__ import annotations

import os

import httpx

BASE_URL = os.environ.get("AEGISOPS_API", "http://127.0.0.1:8000")
TIMEOUT = 60.0


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


def health() -> dict:
    with _client() as c:
        return c.get("/health").json()


def list_incidents(status: str | None = None, limit: int = 50) -> list[dict]:
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    with _client() as c:
        r = c.get("/api/v1/incidents", params=params)
        r.raise_for_status()
        return r.json()


def get_incident(incident_id: str) -> dict | None:
    with _client() as c:
        r = c.get(f"/api/v1/incidents/{incident_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


def analyze_run(run_id: str) -> dict:
    with _client() as c:
        r = c.post(f"/api/v1/agents/analyze/{run_id}")
        r.raise_for_status()
        return r.json()


def approve(incident_id: str, approver_name: str, role: str = "operator") -> dict:
    with _client() as c:
        r = c.post(
            f"/api/v1/incidents/{incident_id}/approve",
            json={"approver_name": approver_name, "role": role},
        )
        r.raise_for_status()
        return r.json()


def reject(incident_id: str, approver_name: str, reason: str) -> dict:
    with _client() as c:
        r = c.post(
            f"/api/v1/incidents/{incident_id}/reject",
            json={"approver_name": approver_name, "reason": reason},
        )
        r.raise_for_status()
        return r.json()


def execute(incident_id: str, executed_by: str) -> dict:
    with _client() as c:
        r = c.post(
            f"/api/v1/incidents/{incident_id}/execute",
            json={"executed_by": executed_by},
        )
        r.raise_for_status()
        return r.json()


def list_runs() -> list[dict]:
    with _client() as c:
        r = c.get("/api/v1/runs")
        r.raise_for_status()
        return r.json()


def guardrails_redact(text: str) -> dict:
    with _client() as c:
        r = c.post("/api/v1/security/redact", json={"text": text})
        r.raise_for_status()
        return r.json()


def guardrails_check_command(cmd: str) -> dict:
    with _client() as c:
        r = c.post(
            "/api/v1/security/check-command",
            json={"command": cmd, "allowlist_enabled": True},
        )
        r.raise_for_status()
        return r.json()


def guardrails_check_injection(text: str) -> dict:
    with _client() as c:
        r = c.post("/api/v1/security/check-injection", json={"text": text})
        r.raise_for_status()
        return r.json()