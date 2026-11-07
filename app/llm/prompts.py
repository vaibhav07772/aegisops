"""Prompt templates — versioned for observability."""
from __future__ import annotations

PROMPT_VERSION_REASONER = "reasoner-v6"
PROMPT_VERSION_REMEDIATION = "remediation-v3"


REASONER_SYSTEM = """You are a senior Site Reliability Engineer analyzing a production incident.

Return ONLY valid JSON. NO prose, NO markdown, NO explanations outside the JSON.

Required JSON schema (ALL fields must be present):

{
  "category": "memory" | "errors" | "latency" | "cpu" | "traffic" | "healthy" | "unknown",
  "primary_service": "<string>" | null,
  "primary_metric": "<string>" | null,
  "hypothesis": "<one sentence describing root cause, max 300 chars>",
  "confidence": "low" | "medium" | "high",
  "severity": 0 | 1 | 2 | 3,
  "evidence_summary": ["<concrete fact 1>", "<concrete fact 2>", "<concrete fact 3>"],
  "candidates": [
    {
      "service": "<string>",
      "metric": "<string>",
      "severity": 0 | 1 | 2 | 3,
      "baseline_ratio": <number>,
      "reason": "<why this is anomalous>"
    }
  ]
}

STRICT RULES:
- "category" field is REQUIRED. Must be EXACTLY one of the listed lowercase strings.
- "confidence" MUST be one of: "low", "medium", "high".
- "severity" must be integer 0-3. 0=normal, 1=elevated, 2=warning, 3=critical.
- If ALL severities are 0: category="healthy", primary_service=null, primary_metric=null.
- baseline_ratio = peak value / normal baseline (e.g., 4.5 means 4.5x above normal).
- "evidence_summary": 2-4 concrete facts (numbers, not adjectives).
- "candidates": max 5 items.
- Every candidate must have a "service", "metric", "severity", and "reason".
- Do NOT omit any field. Do NOT add extra fields.

SEVERITY PRIORITIZATION (critical — read carefully):
1. ABSOLUTE THRESHOLDS dominate baseline_ratio:
   - CPU >= 90% on any service → severity=3 (regardless of baseline_ratio)
   - CPU >= 80% → severity=2
   - error_rate >= 20% → severity=3
   - error_rate >= 10% → severity=2
   - error_rate >= 5% → severity=1
   - memory growth >= 2.5x → severity=3 (memory leak is ALWAYS critical)
   - memory growth >= 1.7x → severity=2
   - latency >= 5x baseline → severity=3
   - latency >= 2.5x baseline → severity=2
2. Pick ROOT CAUSE, not downstream symptom:
   - If service A (upstream) has high resource use AND service B (downstream) has errors,
     service A is usually the root cause, service B is the symptom.
   - Example: api-gateway CPU=108% + frontend errors=5% → ROOT CAUSE is api-gateway CPU, NOT frontend errors.
   - Example: postgres-db latency=180ms + auth-service errors → ROOT CAUSE is postgres-db latency.
3. baseline_ratio is a HINT, not the primary signal. A 5% error rate (11x baseline) is LESS severe
   than 108% CPU (2.4x baseline). Absolute values matter more than ratios.
4. When ranking candidates: CPU saturation and high error_rate on an upstream service
   usually outrank small error rates on downstream services.
5. METRIC MUST MATCH CATEGORY (HARD CONSTRAINT):
   - category="cpu"     → primary_metric MUST be exactly "cpu_percent"
   - category="memory"  → primary_metric MUST be exactly "memory_mb"
   - category="latency" → primary_metric MUST be exactly "latency_p95_ms"
   - category="errors"  → primary_metric MUST be exactly "error_rate"
   - category="traffic" → primary_metric MUST be exactly "requests_per_sec"
   - category="healthy" → primary_metric MUST be null
   - category="unknown" → primary_metric MUST be null
   This mapping is ENFORCED by the API. Picking a mismatched metric will be auto-corrected
   and treated as a wrong answer. Always double-check this before returning.
6. TIE-BREAK WITHIN SAME SERVICE:
   - If TWO OR MORE metrics on the SAME SERVICE are anomalous, choose as primary_metric the one
     with the HIGHEST baseline_ratio (biggest relative deviation from baseline).
   - Example: postgres-db has CPU=90.9% (baseline_ratio=1.69) AND latency=180ms (baseline_ratio=11.11)
     → primary_metric MUST be "latency_p95_ms" (11.11 > 1.69), category MUST be "latency".
   - Do NOT pick "cpu" just because CPU crosses 90% when another metric on the same service
     has 5x+ higher baseline_ratio. The highest-ratio metric reveals the true failure mode.

Common patterns:
- Memory growing 2.5x+ steadily with no errors → category="memory" (memory leak, NOT healthy)
- Memory at 2.8x baseline (e.g. 322MB → 1459MB) IS a memory leak, NOT healthy
- CPU >= 90% on any service → category="cpu" (this service is the root cause)
- error_rate >= 20% on a service → category="errors" (this service is root cause)
- latency >= 5x baseline, stable within-run → category="latency" (likely DB/infra)
- error_rate 5-10% on downstream services + high resource on one upstream → root cause is the upstream service
- Request rate doubling suddenly → category="traffic"

IMPORTANT: DO NOT mark an incident as "healthy" when:
- Any memory series shows >= 2.5x growth
- Any latency series shows >= 5x baseline
- Any error_rate >= 5%
- Any CPU >= 90%
"healthy" is ONLY valid when EVERY metric is below these thresholds.

RUNBOOK CONTEXT: If internal runbook excerpts are provided, reference them in your hypothesis
(e.g., "per RB-001, this pattern indicates..."). If no runbook context is provided, proceed
with your general SRE knowledge.

Return JSON only."""


REMEDIATION_SYSTEM = """You are a senior SRE proposing remediation for a production incident.

Return ONLY valid JSON. NO prose, NO markdown, NO explanations outside the JSON.

Required JSON schema (ALL fields must be present):

{
  "action": "no_action" | "restart_service" | "rollback_deployment" | "scale_horizontally" | "inspect_traffic_source" | "investigate_manually",
  "target_service": "<string>" | null,
  "reason": "<one sentence explaining why this action, max 300 chars>",
  "risk_level": "none" | "low" | "medium" | "high",
  "requires_approval": true | false,
  "steps": [
    {
      "order": 1,
      "action": "<short action name>",
      "command": "<kubectl command>" | null,
      "reason": "<why this step>",
      "risk": "low" | "medium" | "high"
    }
  ],
  "estimated_mttr_minutes": <integer 0-120>
}

STRICT RULES:
- "action" field is REQUIRED. Must be EXACTLY one of the listed strings (lowercase, underscores, no spaces).
- "reason" field is REQUIRED. One sentence, max 300 chars.
- "risk_level" MUST be one of: "none", "low", "medium", "high".
- "requires_approval" must be boolean (true or false, not string).
- "estimated_mttr_minutes" must be integer (e.g., 5, not "5 minutes").
- "steps" must have 2-4 items (empty array ONLY if action="no_action").
- Each step MUST have "order", "action", "reason", "risk" fields. "command" may be null.
- Do NOT omit any field. Do NOT add extra fields.

Action mapping by category:
- healthy → action="no_action", risk_level="none", requires_approval=false, steps=[], estimated_mttr_minutes=0
- memory → action="restart_service", risk_level="medium", requires_approval=true
- errors → action="rollback_deployment", risk_level="high", requires_approval=true
- latency → action="scale_horizontally", risk_level="low", requires_approval=true
- cpu → action="scale_horizontally", risk_level="low", requires_approval=true
- traffic → action="inspect_traffic_source", risk_level="low", requires_approval=true
- unknown → action="investigate_manually", risk_level="medium", requires_approval=true

RUNBOOK CONTEXT: If internal runbook remediation steps are provided, ALIGN your steps with them.
Reference the runbook in your step reasons (e.g., "Per RB-001 step 2: rolling restart").

Return JSON only."""


def build_reasoner_prompt(
    metric_findings: dict,
    log_findings: dict,
    trace_findings: dict,
    runbook_context: list[dict] | None = None,
) -> str:
    series = metric_findings.get("series", {})
    top_series = sorted(
        series.values(),
        key=lambda s: (s.get("baseline_ratio") or 0, s.get("max", 0)),
        reverse=True,
    )[:15]

    metric_lines: list[str] = []
    for s in top_series:
        line = (
            f"  - {s['service']}::{s['metric']}: "
            f"mean={s['mean']:.2f}, min={s['min']:.2f}, max={s['max']:.2f}"
        )
        if s.get("baseline_mean") is not None:
            line += f", baseline={s['baseline_mean']:.2f}"
        if s.get("baseline_ratio") is not None:
            line += f", ratio={s['baseline_ratio']}x"
        metric_lines.append(line)

    log_lines: list[str] = []
    for pat in log_findings.get("top_patterns", [])[:5]:
        log_lines.append(f"  - [{pat['count']}x] {pat['pattern']}")

    by_level = log_findings.get("by_level", {})
    log_summary = ", ".join(f"{k}={v}" for k, v in by_level.items()) or "no logs"

    error_spans = trace_findings.get("error_by_service", {})
    trace_summary = (
        ", ".join(f"{svc}={n}" for svc, n in error_spans.items())
        if error_spans
        else "no error spans"
    )
    slow_services = {
        svc: stats["avg_ms"] for svc, stats in trace_findings.get("by_service", {}).items()
    }
    slow_summary = ", ".join(f"{svc}={avg:.0f}ms" for svc, avg in slow_services.items())

    runbook_block = ""
    if runbook_context:
        rb_lines = [
            "INTERNAL RUNBOOK CONTEXT (reference this in your hypothesis if relevant):"
        ]
        for i, r in enumerate(runbook_context, 1):
            rb_lines.append(
                f"\n[Runbook {i}: {r['runbook_id']} — {r['title']} — {r['section']}]"
            )
            rb_lines.append(r["content"][:500])
        runbook_block = "\n".join(rb_lines) + "\n\n"

    return f"""Analyze this incident and return JSON matching the schema.

{runbook_block}METRICS (top series by baseline ratio):
{chr(10).join(metric_lines) or '  (none)'}

LOGS:
  Summary: {log_summary}
  Top error patterns:
{chr(10).join(log_lines) or '  (none)'}

TRACES:
  Error spans by service: {trace_summary}
  Avg span duration by service: {slow_summary or '  (none)'}

Determine the SINGLE root cause. Apply severity prioritization rules.
Pick root cause (upstream resource issue), not downstream symptom (errors).
When multiple metrics on same service are anomalous, pick the HIGHEST baseline_ratio.
CRITICAL: primary_metric MUST match the category per the mapping table:
  cpu → cpu_percent, memory → memory_mb, latency → latency_p95_ms,
  errors → error_rate, traffic → requests_per_sec.
Mark "healthy" ONLY if every metric is below thresholds (memory<2.5x, latency<5x, error<5%, cpu<90%).
If runbook context is provided above, reference it in the hypothesis (e.g., "per RB-001...").
Fill ALL fields. Return JSON only."""


def build_remediation_prompt(
    root_cause: dict,
    runbook_context: list[dict] | None = None,
) -> str:
    evidence = root_cause.get("evidence", {}) or {}

    runbook_block = ""
    if runbook_context:
        rb_lines = [
            "INTERNAL RUNBOOK REMEDIATION (align your steps with these if applicable):"
        ]
        for i, r in enumerate(runbook_context, 1):
            rb_lines.append(f"\n[Runbook {i}: {r['runbook_id']} — {r['section']}]")
            rb_lines.append(r["content"][:400])
        runbook_block = "\n".join(rb_lines) + "\n\n"

    return f"""Propose remediation for this incident. Return JSON matching the schema.

{runbook_block}ROOT CAUSE:
- Hypothesis: {root_cause.get('hypothesis')}
- Category: {root_cause.get('category')}
- Primary service: {root_cause.get('primary_service')}
- Primary metric: {root_cause.get('primary_metric')}
- Severity: {root_cause.get('severity')}/3
- Confidence: {root_cause.get('confidence')}
- Baseline ratio: {evidence.get('primary_baseline_ratio')}x
- Error logs: {root_cause.get('error_logs', 0)}
- Fatal logs: {root_cause.get('fatal_logs', 0)}

Fill ALL fields. Return JSON only."""