# OPS-001: Emergency Rollback Runbook

## Purpose

This runbook provides step-by-step instructions for rolling back a problematic deployment of the FunctionGemma Agent to a previous stable version.

## Prerequisites

- Access to the Kubernetes cluster (`kubectl` configured)
- Helm 3.x installed
- Appropriate RBAC permissions in the target namespace
- Access to monitoring dashboards to verify rollback success

## When to Use

Use this runbook when:
- New deployment shows high error rates (>5%)
- Health checks are failing consistently
- Model inference is producing incorrect results
- Performance degradation (latency > 2x baseline)
- Customer-reported issues after deployment

## Rollback Procedures

### Option 1: Quick Rollback (Recommended)

Use the automated rollback script:

```bash
# Rollback to previous version
./scripts/rollback.sh

# Rollback to specific revision
./scripts/rollback.sh -v 2

# Rollback in staging environment
./scripts/rollback.sh -n staging -r function-gemma-agent-staging
```

### Option 2: Manual Rollback via Helm

1. **Check Deployment History**
```bash
helm history function-gemma-agent -n production
```

2. **Identify Last Good Revision**
Look for the last successful deployment (status: deployed)

3. **Perform Rollback**
```bash
# Rollback to previous version (revision 0)
helm rollback function-gemma-agent 0 -n production

# Rollback to specific revision
helm rollback function-gemma-agent 2 -n production
```

4. **Verify Rollback**
```bash
# Check rollout status
kubectl rollout status deployment/function-gemma-agent -n production

# Check pod status
kubectl get pods -n production -l app.kubernetes.io/name=function-gemma-agent
```

### Option 3: Emergency Rollback (Severe Issues)

If the deployment is completely broken:

1. **Scale to Zero** (Stop traffic immediately)
```bash
kubectl scale deployment/function-gemma-agent --replicas=0 -n production
```

2. **Rollback**
```bash
helm rollback function-gemma-agent 0 -n production
```

3. **Scale Back Up**
```bash
kubectl scale deployment/function-gemma-agent --replicas=3 -n production
```

## Verification Steps

### 1. Health Check Verification

```bash
# Check health endpoint
curl -f https://agent.example.com/api/v1/health

# Expected response: {"status": "ok"}
```

### 2. Pod Status Check

```bash
# All pods should be Running
kubectl get pods -n production -l app.kubernetes.io/name=function-gemma-agent

# Check for restarts
kubectl get pods -n production -l app.kubernetes.io/name=function-gemma-agent --show-labels
```

### 3. Service Metrics

```bash
# Check error rate (should be < 1%)
kubectl port-forward -n production svc/function-gemma-agent 8000:80
curl http://localhost:8000/api/v1/metrics | grep http_requests_total
```

### 4. Application Logs

```bash
# Check recent logs for errors
kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent --tail=100 | grep ERROR
```

### 5. Business Logic Test

```bash
# Test a simple query
curl -X POST https://agent.example.com/api/v1/chat \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?"}'
```

## Post-Rollback Actions

### 1. Document the Incident

Create an incident report with:
- Time of rollback
- Reason for rollback
- Revision rolled back to
- Verification results

### 2. Analyze the Problem

1. **Collect Logs**
```bash
# Save logs from failed deployment
kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent --previous > failed-deployment.log
```

2. **Check Metrics**
- Review Prometheus graphs around deployment time
- Look for spikes in error rate, latency, or resource usage

3. **Review Changes**
- Check Git diff for the problematic commit
- Review PR that introduced the issue

### 3. Communicate

1. **Internal Communication**
- Post in Slack channel: `#deployments`
- Send email to engineering team
- Update incident tracking system

2. **External Communication** (if customer-impacting)
- Follow company communication policy
- Provide ETA for fix

### 4. Prevent Recurrence

1. **Add Automated Tests**
```bash
# Add regression test for the specific issue
# Example: tests/test_regression.py
def test_issue_123():
    """Test for regression of issue #123"""
    response = client.post("/api/v1/chat", json={"prompt": "test case"})
    assert response.status_code == 200
    assert "expected_result" in response.json()["response"]
```

2. **Improve Monitoring**
- Add alert for the specific metric that failed
- Create dashboard for the problematic component

3. **Update Deployment Checklist**
- Add manual verification step
- Include automated smoke test

## Troubleshooting

### Rollback Fails

If `helm rollback` fails:

1. **Check Helm Status**
```bash
helm status function-gemma-agent -n production
```

2. **Force Uninstall and Reinstall**
```bash
helm uninstall function-gemma-agent -n production
helm install function-gemma-agent k8s/chart/ \
  --namespace production \
  --set image.tag=<stable-tag>
```

### Pods Not Starting

After rollback, if pods are stuck:

1. **Check Events**
```bash
kubectl describe pod -n production -l app.kubernetes.io/name=function-gemma-agent
```

2. **Check Resources**
```bash
kubectl top nodes
kubectl top pods -n production
```

3. **Check PVC**
```bash
kubectl get pvc -n production
```

### Health Check Still Failing

1. **Check Readiness Probe**
```bash
kubectl get deployment function-gemma-agent -n production -o yaml | grep -A 10 readinessProbe
```

2. **Manual Health Check**
```bash
kubectl exec -it -n production deployment/function-gemma-agent -- curl localhost:8000/api/v1/health
```

## Recovery Time Objectives (RTO)

| Severity | Target RTO | Escalation |
|----------|------------|------------|
| Critical (P0) | 5 minutes | On-call engineer → Team lead |
| High (P1) | 15 minutes | Team lead → Engineering manager |
| Medium (P2) | 1 hour | Engineering team |
| Low (P3) | 4 hours | Next business day |

## Related Procedures

- [OPS-002: Reasoning Drift Alert](OPS-002-DRIFT-ALERT.md)
- [OPS-003: Scaling Operations](OPS-003-SCALING.md)
- [Emergency Contact List](../CONTACTS.md)

## Checklist

- [ ] Identified problematic deployment
- [ ] Selected rollback target revision
- [ ] Executed rollback command
- [ ] Verified pod status is healthy
- [ ] Confirmed health checks passing
- [ ] Tested application functionality
- [ ] Documented incident
- [ ] Communicated to stakeholders
- [ ] Created follow-up tasks to prevent recurrence

---

**Last Updated**: 2025-12-26  
**Version**: 1.0  
**Owner**: DevOps Team
