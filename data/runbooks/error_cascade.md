# Error Cascade Runbook (RB-005)

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
