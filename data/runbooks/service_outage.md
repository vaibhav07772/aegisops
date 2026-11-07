# Service Outage Runbook (RB-004)

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
