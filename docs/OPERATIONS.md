# Operations Guide

This guide provides operational procedures for managing the FunctionGemma Agent in production.

## Table of Contents

1. [Deployment](#deployment)
2. [Rollback](#rollback)
3. [Scaling](#scaling)
4. [Monitoring](#monitoring)
5. [Troubleshooting](#troubleshooting)
6. [Maintenance](#maintenance)

## Deployment

### Automated Deployment via CI/CD

The deployment is automated through GitHub Actions. The pipeline will:

1. Run tests and security scans
2. Build and push Docker image
3. Deploy with Helm to the appropriate environment

#### Deploy to Staging
```bash
# Push to develop branch
git push origin develop
```

#### Deploy to Production
```bash
# Push to main branch
git push origin main
```

### Manual Deployment

For manual deployments or emergencies:

```bash
# Set environment variables
export NAMESPACE="production"
export RELEASE_NAME="function-gemma-agent"
export IMAGE_TAG="sha-<commit-hash>"

# Deploy
helm upgrade --install $RELEASE_NAME k8s/chart/ \
  --namespace $NAMESPACE \
  --create-namespace \
  --set image.tag=$IMAGE_TAG \
  --wait \
  --timeout=15m
```

## Rollback

### Quick Rollback (Recommended)

Use the provided rollback script for instant rollback:

```bash
# Rollback to previous version
./scripts/rollback.sh

# Rollback to specific revision
./scripts/rollback.sh -v 2

# Rollback in different namespace
./scripts/rollback.sh -n staging -r function-gemma-agent-staging
```

### Manual Rollback

```bash
# View deployment history
helm history function-gemma-agent -n production

# Rollback to previous version
helm rollback function-gemma-agent 0 -n production

# Rollback to specific revision
helm rollback function-gemma-agent 2 -n production

# Wait for rollout
kubectl rollout status deployment/function-gemma-agent -n production
```

### Emergency Rollback

If the deployment is completely broken:

```bash
# Scale to zero to stop traffic
kubectl scale deployment/function-gemma-agent --replicas=0 -n production

# Rollback
helm rollback function-gemma-agent 0 -n production

# Scale back up
kubectl scale deployment/function-gemma-agent --replicas=3 -n production
```

## Scaling

### Horizontal Scaling

#### Manual Scaling
```bash
# Scale to 5 replicas
kubectl scale deployment/function-gemma-agent --replicas=5 -n production

# Or using Helm
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set replicaCount=5
```

#### Auto-scaling
The HPA is configured by default:
- Min replicas: 3
- Max replicas: 10
- Target CPU: 70%
- Target Memory: 80%

View HPA status:
```bash
kubectl get hpa -n production
```

Adjust HPA settings:
```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set autoscaling.minReplicas=5 \
  --set autoscaling.maxReplicas=20 \
  --set autoscaling.targetCPUUtilizationPercentage=60
```

### Vertical Scaling

Update resource limits:
```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set resources.limits.cpu=2000m \
  --set resources.limits.memory=4Gi \
  --set resources.requests.cpu=1000m \
  --set resources.requests.memory=2Gi
```

## Monitoring

### Health Checks

#### Application Health
```bash
# Check pod health
kubectl get pods -n production -l app.kubernetes.io/name=function-gemma-agent

# Check detailed pod status
kubectl describe pod -n production -l app.kubernetes.io/name=function-gemma-agent

# Health endpoint
curl https://agent.example.com/api/v1/health
```

#### Metrics Endpoint
```bash
# Prometheus metrics
curl https://agent.example.com/api/v1/metrics
```

### Logs

#### View Logs
```bash
# All pods
kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent -f

# Specific pod
kubectl logs -n production -f deployment/function-gemma-agent

# Previous container logs
kubectl logs -n production -p deployment/function-gemma-agent
```

#### Log Aggregation
Logs are structured and can be aggregated with:
- ELK Stack
- Loki
- CloudWatch (if using AWS)

### Alerts

Configure alerts for:
- High error rate (>5%)
- High latency (P95 > 2s)
- Pod restarts
- Memory/CPU usage > 90%
- Health check failures

## Troubleshooting

### Common Issues

#### Pod Not Starting
```bash
# Check pod events
kubectl describe pod -n production -l app.kubernetes.io/name=function-gemma-agent

# Check logs
kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent

# Common causes:
# - Resource limits too low
# - Image pull issues
# - Missing secrets/configmaps
```

#### Health Check Failing
```bash
# Check health endpoint directly
kubectl port-forward -n production deployment/function-gemma-agent 8000:8000
curl http://localhost:8000/api/v1/health

# Check probe configuration
kubectl get deployment function-gemma-agent -n production -o yaml | grep -A 10 "readinessProbe"
```

#### High Memory Usage
```bash
# Check resource usage
kubectl top pods -n production

# Check for memory leaks in logs
kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent | grep -i "memory\|oom"

# Consider increasing limits
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set resources.limits.memory=4Gi
```

#### Slow Response Times
```bash
# Check resource constraints
kubectl top pods -n production

# Check HPA status
kubectl describe hpa function-gemma-agent -n production

# Scale up temporarily
kubectl scale deployment/function-gemma-agent --replicas=10 -n production
```

### Debug Mode

Enable debug logging:
```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set env[0].name=LOG_LEVEL \
  --set env[0].value=DEBUG
```

## Maintenance

### Zero-Downtime Updates

The deployment strategy ensures zero downtime:
- `maxSurge: 25%` - Allows 25% extra pods during update
- `maxUnavailable: 0%` - No pods are terminated before new ones are ready
- Readiness probes ensure new pods receive traffic only when ready

### Canary Deployments

For risky changes, use canary deployment:

```bash
# Deploy canary (10% traffic)
helm upgrade --install function-gemma-agent-canary k8s/chart/ \
  --namespace production \
  --values k8s/chart/canary-values.yaml \
  --set image.tag=new-feature

# Monitor canary
kubectl get pods -n production -l deployment-type=canary

# Promote to production if successful
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set image.tag=new-feature

# Clean up canary
helm uninstall function-gemma-agent-canary -n production
```

### Database Migrations

If database migrations are needed:

1. Deploy migration job first
2. Verify migration success
3. Deploy application update
4. Keep old version running until verification complete

### Certificate Renewal

Certificates are managed by cert-manager. Check status:
```bash
kubectl get certificates -n production
kubectl describe certificate function-gemma-agent-tls -n production
```

### Backup and Recovery

#### Backup Configurations
```bash
# Backup all configurations
kubectl get all,configmaps,secrets,pvc -n production -o yaml > backup.yaml

# Backup specific release
helm get values function-gemma-agent -n production > prod-values.yaml
```

#### Recovery
```bash
# Restore from backup
kubectl apply -f backup.yaml

# Or redeploy from saved values
helm upgrade --install function-gemma-agent k8s/chart/ \
  --namespace production \
  --values prod-values.yaml
```

### Security Updates

Regularly update:
- Base Docker images
- Python dependencies
- Kubernetes versions

Monitor security advisories:
- GitHub Dependabot alerts
- Trivy security scans
- Kubernetes CVE announcements

## Performance Tuning

### Resource Optimization

Monitor and adjust:
1. CPU/Memory requests and limits
2. HPA thresholds
3. Pod anti-affinity rules
4. Persistent volume performance

### Network Optimization

- Use appropriate ingress class
- Enable HTTP/2
- Configure proper timeouts
- Consider CDN for static content

### Database Optimization

- Connection pooling
- Query optimization
- Index tuning
- Read replicas for scaling

## Contact and Escalation

### On-call Procedures

1. Check alerts and dashboards
2. Verify health endpoints
3. Review recent deployments
4. Check logs for errors
5. Perform rollback if needed
6. Escalate to team lead if unresolved

### Emergency Contacts

- Primary: [Team Lead]
- Secondary: [DevOps Lead]
- Management: [Engineering Manager]
