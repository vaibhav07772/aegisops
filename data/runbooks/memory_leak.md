# Memory Leak Runbook (RB-001)

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
