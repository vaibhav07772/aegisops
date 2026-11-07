"""Create all 6 runbook markdown files programmatically (idempotent).

Safest way to bootstrap runbooks — no manual paste errors.
Overwrites existing files only if --force is passed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger("scripts.setup_runbooks")


RUNBOOKS: dict[str, str] = {
    "memory_leak": """# Memory Leak Runbook (RB-001)

## Symptoms
- Service memory grows steadily over time (2.5x+ baseline)
- No immediate errors — process stays healthy
- Latency rises as GC pressure builds
- Eventually OOMKill or pod restart

## Root Cause Indicators
- Linear memory growth over minutes
- GC frequency increases
- No matching traffic spike
- Common culprits: unbounded cache, connection pool leak, batch accumulator

## Remediation Steps
1. Identify pod: `kubectl get pods -l app=<service> -n production`
2. Rolling restart: `kubectl rollout restart deployment/<service> -n production`
3. Capture heap dump: `kubectl exec <pod> -- jcmd 1 GC.heap_dump /tmp/heap.hprof`
4. Analyze retained objects (top-10 by size)
5. Deploy memory limit: `kubectl set resources deployment/<service> --limits=memory=2Gi`

## Verification
- Memory returns to baseline (<1.5x) within 5 minutes
- No OOMKill events in `kubectl describe pods`
- Latency p95 back under 100ms

## Escalation
- If memory >3x baseline: page on-call SRE + open P1
- If heap dump shows unknown classes: escalate to service owner
""",

    "slow_database": """# Slow Database Runbook (RB-002)

## Symptoms
- Database latency (p95) >5x baseline
- Downstream services show errors/timeouts
- Connection pool saturation on callers
- CPU on DB may rise but not necessarily

## Root Cause Indicators
- Query latency spike in DB metrics
- Lock waits / deadlocks
- Missing index on hot query
- Connection pool exhaustion

## Remediation Steps
1. Check current latency with pg_stat_statements
2. Find slow queries: `SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;`
3. Quick mitigation — add read replica: `kubectl scale statefulset postgres-db --replicas=3 -n production`
4. If specific query slow — suggest index to DBA
5. Enable query timeout: `kubectl set env deployment/<service> DB_QUERY_TIMEOUT_MS=5000`

## Verification
- p95 latency <2x baseline within 10 minutes
- Downstream error rate returns to <1%
- No new timeout errors in logs

## Escalation
- If latency >10x baseline: page DBA + incident commander
- If data corruption suspected: STOP, escalate to CTO
""",

    "cpu_spike": """# CPU Spike Runbook (RB-003)

## Symptoms
- CPU percent on service >90% sustained
- Request queuing / increased latency
- Downstream services get 5xx errors
- Logs show throttled or timeout messages

## Root Cause Indicators
- CPU pegged at limit
- Request queue depth increases
- Insufficient replicas for load
- Or: runaway process (infinite loop, hot regex)

## Remediation Steps
1. Check current replicas: `kubectl get deployment <service> -n production`
2. Immediate scale: `kubectl scale deployment <service> --replicas=+2 -n production`
3. If runaway CPU — profile: `kubectl exec <pod> -- top -b -n 1`
4. If hot code path — rollback: `kubectl rollout undo deployment/<service> -n production`
5. Review HPA config: `kubectl get hpa -n production`

## Verification
- CPU drops below 70% within 5 minutes
- Latency p95 <2x baseline
- No new errors in downstream services

## Escalation
- If scale-up doesn't help: suspect DDoS, enable WAF
- If sustained >10 minutes: page on-call + check for runaway
""",

    "service_outage": """# Service Outage Runbook (RB-004)

## Symptoms
- error_rate on service >50% (near 100% in severe cases)
- Fatal logs: connection refused or unreachable
- Downstream services fail (cascade)
- Health checks failing

## Root Cause Indicators
- Service process dead or unreachable
- Network partition
- Bad deployment (last 30 min)
- External dependency down (payment gateway, auth provider)

## Remediation Steps
1. Check service status: `kubectl get pods -l app=<service> -n production`
2. If crashloop: `kubectl logs <pod> --tail=100 --previous`
3. If bad deploy: rollback: `kubectl rollout undo deployment/<service> -n production`
4. If network: verify ingress + service endpoints: `kubectl get endpoints <service> -n production`
5. If external dependency: enable circuit breaker / fallback mode

## Verification
- error_rate drops below 5% within 10 minutes
- Health checks green
- Downstream error rate returns to baseline

## Escalation
- ALWAYS page on-call for outages
- Notify stakeholders via status page within 15 minutes
- If external dependency: contact provider status page
""",

    "error_cascade": """# Error Cascade Runbook (RB-005)

## Symptoms
- Auth or entry service error_rate spikes
- Upstream services show cascading errors
- User-facing errors (401/403/500)
- Logs: token verification failed, JWT expired

## Root Cause Indicators
- Auth service failure (signing key rotated, JWKS endpoint down)
- Token issuer misconfiguration
- Bad deployment of auth-service
- Clock skew causing JWT validation failures

## Remediation Steps
1. Check auth-service logs: `kubectl logs -l app=auth-service -n production --tail=200`
2. Verify JWT public keys match issuer: check JWKS endpoint
3. If bad deploy: `kubectl rollout undo deployment/auth-service -n production`
4. If clock skew: `kubectl exec <pod> -- date` — check NTP sync
5. Rotate keys if compromised: notify security

## Verification
- auth-service error_rate <2% within 10 minutes
- Upstream services (api-gateway, frontend) error rate drops
- 401/403 errors disappear from logs

## Escalation
- If security concern (suspected key compromise): SECURITY INCIDENT
- If sustained >15 min: rollback + page service owner
""",

    "general_oncall": """# General On-Call Runbook (RB-000)

## Triage Checklist
- Identify affected service(s) from metrics/logs/traces
- Check recent deployments: `kubectl rollout history deployment/<service> -n production`
- Check external status pages (AWS, payment providers, auth providers)
- Verify blast radius — how many customers affected?
- Open incident channel if P1/P2

## Severity Definitions
- P1: full outage, revenue impact, >25% customer impact
- P2: significant degradation, workaround exists
- P3: minor issue, single customer
- P4: cosmetic, no user impact

## Communication
- P1: page on-call + IC + notify status page
- P2: page on-call, status page
- P3/P4: ticket, no page

## Post-Incident
- Blameless postmortem within 5 business days
- Root cause + remediation + prevention
- Action items assigned with owners

## Common Mistakes
- Don't restart everything blindly — collect evidence first
- Don't merge fixes without review during incident (hotfix branch OK)
- Don't forget to communicate — status page is critical
""",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    runbooks_dir = get_settings().runbooks_dir
    runbooks_dir.mkdir(parents=True, exist_ok=True)

    created = overwritten = skipped = 0
    for name, content in RUNBOOKS.items():
        path = runbooks_dir / f"{name}.md"
        if path.exists() and not args.force:
            existing = path.stat().st_size
            if existing > 0:
                skipped += 1
                print(f"[skip]   {path.name}  ({existing} bytes)")
                continue
        path.write_text(content, encoding="utf-8")
        if path.exists() and path.stat().st_size > 0:
            created += 1
            print(f"[write]  {path.name}  ({path.stat().st_size} bytes)")

    print()
    print("=" * 55)
    print(" Runbooks setup")
    print("=" * 55)
    print(f"  Directory : {runbooks_dir}")
    print(f"  Files     : {len(RUNBOOKS)}")
    print(f"  Written   : {created}")
    print(f"  Skipped   : {skipped}")
    if skipped and not args.force:
        print("  Tip: use --force to overwrite existing non-empty files")

    # Sanity check: parse each file
    from app.rag.runbooks import parse_markdown_runbook

    print()
    print(" Parse check:")
    total_chunks = 0
    for name in RUNBOOKS:
        path = runbooks_dir / f"{name}.md"
        chunks = parse_markdown_runbook(path)
        total_chunks += len(chunks)
        status = "OK" if chunks else "FAIL"
        print(f"  [{status}] {path.name:<25} chunks={len(chunks)}")
    print(f"  Total chunks: {total_chunks}")


if __name__ == "__main__":
    main()