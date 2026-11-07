# General On-Call Runbook (RB-000)

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
