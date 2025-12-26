# Kubernetes Runbook

## Service Criticality

### Service X - Payment Processing
Service X is critical for payment processing and must maintain 99.9% uptime. It handles all customer transactions and is deployed across multiple availability zones.

**Restart Policy:**
- Always restart on failure
- Maximum 5 restart attempts within 10 minutes
- If restarts exceed limit, escalate to on-call engineer

### Service Y - User Authentication
Service Y handles user authentication and is also critical. It manages user sessions and JWT token validation.

**Restart Policy:**
- Always restart on failure
- Use rolling updates to maintain availability
- Monitor authentication failure rates

## Troubleshooting Guide

### Pod Status Issues
When pods are not running:
1. Check pod status with `get_pod_status`
2. If status is `CrashLoopBackOff`, get logs with `get_pod_logs`
3. Check resource limits and requests
4. Verify configuration maps and secrets

### High CPU/Memory Usage
For resource issues:
1. Identify the problematic pod using `get_pod_status`
2. Check resource usage trends
3. Consider scaling up or optimizing the application
4. Review recent deployments for changes

## Cluster Information

### Production Cluster
- Cluster ID: `prod`
- Node Count: 10
- Region: us-west-2
- Monitoring: Prometheus + Grafana

### Development Cluster
- Cluster ID: `dev`
- Node Count: 3
- Region: us-west-2
- Purpose: Development and testing

## Common Commands

### Check Service Health
Use the `get_pod_status` tool to check the health of all pods in a namespace.

### View Logs
Use the `get_pod_logs` tool to retrieve logs from specific pods. Use the `tail_lines` parameter to limit output.

### Search Documentation
Use the `search_knowledge_base` tool to find information about specific topics or procedures.
