# Kubernetes Deployment

This directory contains Kubernetes manifests and Helm charts for deploying the FunctionGemma Agent.

## Structure

```
k8s/
├── chart/                    # Helm chart
│   ├── Chart.yaml           # Chart metadata
│   ├── values.yaml          # Default values
│   ├── canary-values.yaml   # Canary deployment values
│   └── templates/           # Kubernetes templates
│       ├── deployment.yaml  # Main deployment
│       ├── service.yaml     # Service definition
│       ├── ingress.yaml     # Ingress configuration
│       ├── hpa.yaml         # Horizontal Pod Autoscaler
│       ├── pvc.yaml         # Persistent Volume Claim
│       ├── configmap.yaml   # ConfigMap
│       ├── secret.yaml      # Secret
│       ├── serviceaccount.yaml # ServiceAccount
│       └── _helpers.tpl     # Template helpers
└── old/                     # Legacy manifests (deprecated)
    ├── deployment.yaml
    └── service.yaml
```

## Quick Start

### Prerequisites

- Kubernetes 1.24+
- Helm 3.0+
- Ingress controller (nginx recommended)
- cert-manager (for TLS)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/your-org/function-gemma-agent.git
cd function-gemma-agent
```

2. Install the chart:
```bash
# Add Helm repository (if published)
helm repo add function-gemma-agent https://charts.example.com
helm repo update

# Install from local directory
helm install function-gemma-agent k8s/chart/ \
  --namespace production \
  --create-namespace \
  --set image.tag=latest \
  --set ingress.hosts[0].host=agent.example.com
```

3. Verify installation:
```bash
kubectl get all -n production -l app.kubernetes.io/name=function-gemma-agent
```

## Configuration

### Key Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `replicaCount` | `3` | Number of replicas |
| `image.repository` | `ghcr.io/your-org/function-gemma-agent` | Image repository |
| `image.tag` | `latest` | Image tag |
| `resources.limits.cpu` | `1000m` | CPU limit |
| `resources.limits.memory` | `2Gi` | Memory limit |
| `autoscaling.enabled` | `true` | Enable HPA |
| `ingress.enabled` | `true` | Enable Ingress |
| `persistentVolume.enabled` | `true` | Enable PVC for model cache |

### Custom Values

Create a custom values file:
```yaml
# prod-values.yaml
replicaCount: 5
image:
  tag: "v1.2.3"
resources:
  limits:
    cpu: 2000m
    memory: 4Gi
ingress:
  hosts:
    - host: agent.prod.com
```

Deploy with custom values:
```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --values prod-values.yaml
```

## Deployment Strategies

### Standard Deployment

```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set image.tag=new-version
```

### Canary Deployment

1. Deploy canary:
```bash
helm upgrade --install function-gemma-agent-canary k8s/chart/ \
  --namespace production \
  --values k8s/chart/canary-values.yaml \
  --set image.tag=new-version
```

2. Monitor canary performance

3. Promote to production:
```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set image.tag=new-version
```

4. Clean up canary:
```bash
helm uninstall function-gemma-agent-canary -n production
```

### Blue-Green Deployment

1. Deploy green version:
```bash
helm upgrade --install function-gemma-agent-green k8s/chart/ \
  --namespace production \
  --set fullnameOverride=function-gemma-agent-green \
  --set image.tag=new-version
```

2. Switch traffic:
```bash
# Update service selector to point to green deployment
kubectl patch service function-gemma-agent -n production -p '{"spec":{"selector":{"app.kubernetes.io/instance":"function-gemma-agent-green"}}}'
```

3. Verify and clean up blue deployment

## Monitoring and Observability

### Health Checks

- Liveness probe: `/api/v1/health`
- Readiness probe: `/api/v1/health`
- Metrics endpoint: `/api/v1/metrics`

### Logs

```bash
# View logs
kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent -f

# View previous logs
kubectl logs -n production -p -l app.kubernetes.io/name=function-gemma-agent
```

### Metrics

The application exposes Prometheus metrics on the `/api/v1/metrics` endpoint.

Key metrics:
- `http_requests_total` - HTTP request count
- `http_request_duration_seconds` - Request latency
- `model_inference_total` - Model inference count
- `model_inference_duration_seconds` - Inference latency

## Security

### Security Contexts

- Run as non-root user (UID: 1000)
- Read-only root filesystem
- Drop all capabilities
- No privilege escalation

### Network Policies

Consider adding network policies:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: function-gemma-agent-netpol
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: function-gemma-agent
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
```

### Pod Security Policies

If using PSPs, ensure the chart complies with your organization's policies.

## Troubleshooting

### Common Issues

1. **Pod stuck in Pending**
   - Check resource requests vs available capacity
   - Verify PVC can be provisioned
   - Check node taints and tolerations

2. **Health check failures**
   - Verify application is binding to 0.0.0.0
   - Check if health endpoint is accessible
   - Review probe configuration

3. **Image pull errors**
   - Verify image registry credentials
   - Check if image tag exists
   - Review imagePullSecrets configuration

### Debug Commands

```bash
# Describe pod
kubectl describe pod -n production -l app.kubernetes.io/name=function-gemma-agent

# Exec into pod
kubectl exec -it -n production deployment/function-gemma-agent -- /bin/bash

# Port forward
kubectl port-forward -n production deployment/function-gemma-agent 8000:8000

# Check events
kubectl get events -n production --sort-by=.metadata.creationTimestamp
```

## Maintenance

### Upgrading

1. Check chart dependencies:
```bash
helm dependency update k8s/chart/
```

2. Review breaking changes in chart version

3. Test in staging first

4. Upgrade production:
```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --values prod-values.yaml
```

### Backup

```bash
# Save current values
helm get values function-gemma-agent -n production > current-values.yaml

# Backup release
helm get manifest function-gemma-agent -n production > current-manifest.yaml
```

### Uninstall

```bash
helm uninstall function-gemma-agent -n production
```

Note: This will also delete the PVC. Set `persistentVolume.enabled=false` before uninstalling if you want to keep data.

## Contributing

When updating the chart:

1. Update Chart.yaml version
2. Update values.yaml with new options
3. Test with `helm lint` and `helm template`
4. Update this README
5. Tag the chart version in git

## Support

For issues related to:
- Kubernetes deployment: Check this guide and operations documentation
- Application issues: Check the main repository
- Chart issues: Create an issue in the repository
