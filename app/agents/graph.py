"""Builds and compiles the LangGraph incident-analysis graph."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.log_agent import log_agent_node
from app.agents.nodes.metric_agent import metric_agent_node
from app.agents.nodes.reasoner import reasoner_node
from app.agents.nodes.reasoner_llm import reasoner_llm_node
from app.agents.nodes.remediation_agent import remediation_agent_node
from app.agents.nodes.remediation_llm import remediation_llm_node
from app.agents.nodes.runbook_agent import runbook_agent_node
from app.agents.nodes.trace_agent import trace_agent_node
from app.agents.state import IncidentState
from app.agents.supervisor import route_from_supervisor, supervisor_node
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger("agents.graph")


def build_graph():
    settings = get_settings()
    builder = StateGraph(IncidentState)

    # Core observation nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("metric_agent", metric_agent_node)
    builder.add_node("log_agent", log_agent_node)
    builder.add_node("trace_agent", trace_agent_node)
    builder.add_node("runbook_agent", runbook_agent_node)

    # Reasoning nodes — LLM or rule-based
    if settings.use_llm_reasoner:
        logger.info(
            "graph_building",
            mode="llm",
            llm_available=bool(settings.groq_api_key),
            model=settings.groq_model,
            rag_enabled=settings.rag_enabled,
        )
        builder.add_node("reasoner", reasoner_llm_node)
        builder.add_node("remediation_agent", remediation_llm_node)
    else:
        logger.info("graph_building", mode="rule_based", rag_enabled=settings.rag_enabled)
        builder.add_node("reasoner", reasoner_node)
        builder.add_node("remediation_agent", remediation_agent_node)

    builder.add_edge(START, "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "metric_agent": "metric_agent",
            "log_agent": "log_agent",
            "trace_agent": "trace_agent",
            "runbook_agent": "runbook_agent",
            "reasoner": "reasoner",
            "remediation_agent": "remediation_agent",
            "__end__": END,
        },
    )

    for node in (
        "metric_agent",
        "log_agent",
        "trace_agent",
        "runbook_agent",
        "reasoner",
        "remediation_agent",
    ):
        builder.add_edge(node, "supervisor")

    return builder.compile()