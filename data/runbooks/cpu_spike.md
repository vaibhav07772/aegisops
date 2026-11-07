# CPU Spike Runbook (RB-003)

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
