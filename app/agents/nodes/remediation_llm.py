"""LLM-powered remediation node with fallback."""
from __future__ import annotations

from app.agents.nodes.remediation_agent import remediation_agent_node
from app.agents.state import IncidentState
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import (
    PROMPT_VERSION_REMEDIATION,
    REMEDIATION_SYSTEM,
    build_remediation_prompt,
)
from app.llm.schemas import LLMRemediation
from app.logging_config import get_logger

logger = get_logger("agents.remediation_llm")

_client = LLMClient()


def remediation_llm_node(state: IncidentState) -> dict:
    root_cause = state.get("root_cause", {})
    runbook_context = state.get("runbook_context")
    llm_meta: dict = {"used": False}

    if _client.is_available and root_cause:
        try:
            prompt = build_remediation_prompt(
                root_cause,
                runbook_context=runbook_context,
            )
            result, usage = _client.complete_structured(
                prompt=prompt,
                schema=LLMRemediation,
                system_prompt=REMEDIATION_SYSTEM,
                prompt_version=PROMPT_VERSION_REMEDIATION,
            )
            remediation = _normalize_llm_remediation(result)
            llm_meta = {"used": True, **usage}
            logger.info(
                "remediation_llm_success", action=remediation["action"], **llm_meta
            )
        except (LLMError, Exception) as e:  # noqa: BLE001
            logger.warning("remediation_llm_fallback", error=str(e)[:200])
            remediation = remediation_agent_node(state)["remediation"]
            llm_meta = {"used": False, "fallback_reason": str(e)[:200]}
    else:
        logger.info("remediation_llm_disabled")
        remediation = remediation_agent_node(state)["remediation"]

    remediation["llm_meta"] = llm_meta
    return {
        "remediation": remediation,
        "timeline": [
            {
                "agent": "remediation_agent",
                "action": f"proposed_{remediation['action']}",
                "target": remediation.get("target_service"),
                "risk": remediation.get("risk_level"),
                "llm_used": llm_meta.get("used", False),
            }
        ],
    }


def _normalize_llm_remediation(llm: LLMRemediation) -> dict:
    from app.security.guardrails import validate_remediation

    result = {
        "action": llm.action,
        "target_service": llm.target_service,
        "reason": llm.reason,
        "risk_level": llm.risk_level,
        "requires_approval": llm.requires_approval,
        "executed": False,
        "dry_run_command": llm.steps[0].command if llm.steps else "# no command",
        "steps": [s.model_dump() for s in llm.steps],
        "estimated_mttr_minutes": llm.estimated_mttr_minutes,
    }

    # --- Guardrail check (may redact PII / flag dangerous commands) ---
    report = validate_remediation(result, role="operator")
    result["guardrail_check"] = {
        "passed": report.passed,
        "violations": report.violations,
        "warnings": report.warnings,
        "redactions_applied": report.redactions_applied,
    }

    # If guardrails block, escalate required approval + risk
    if not report.passed:
        result["requires_approval"] = True
        result["risk_level"] = "high"
        result["executed"] = False

    return result