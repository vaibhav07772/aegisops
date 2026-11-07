# Slow Database Runbook (RB-002)

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
