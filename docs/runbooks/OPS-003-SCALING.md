# OPS-003: Scaling Operations Runbook

## Purpose

This runbook provides procedures for scaling the FunctionGemma Agent horizontally and vertically to handle varying load conditions and optimize resource utilization.

## Prerequisites

- Kubernetes cluster admin access
- Helm 3.x installed
- Monitoring dashboard access (Grafana/Prometheus)
- Understanding of HPA and VPA concepts

## Scaling Triggers

Scale up when:
- CPU utilization > 80% for 5 minutes
- Memory utilization > 85% for 5 minutes
- Request latency P95 > 2 seconds
- Queue depth > 100 requests
- HPA at max replicas

Scale down when:
- CPU utilization < 20% for 15 minutes
- Memory utilization < 30% for 15 minutes
- Request latency P95 < 500ms
- Sustained low traffic

## Horizontal Scaling

### 1. Manual Horizontal Scaling

#### Quick Scale Up

```bash
# Scale to 10 replicas
kubectl scale deployment/function-gemma-agent --replicas=10 -n production

# Verify scaling
kubectl get pods -n production -l app.kubernetes.io/name=function-gemma-agent
```

#### Scale Down

```bash
# Scale to minimum replicas
kubectl scale deployment/function-gemma-agent --replicas=3 -n production
```

### 2. HPA Configuration

#### View Current HPA

```bash
kubectl get hpa function-gemma-agent -n production -o yaml
```

#### Update HPA Settings

```bash
# Increase max replicas and adjust targets
kubectl patch hpa function-gemma-agent -n production -p '{"spec":{"maxReplicas":20,"metrics":[{"type":"Resource","resource":{"name":"cpu","target":{"type":"Utilization","averageUtilization":60}}},{"type":"Resource","resource":{"name":"memory","target":{"type":"Utilization","averageUtilization":70}}}]}}'
```

#### Advanced HPA with Custom Metrics

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: function-gemma-agent-advanced
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: function-gemma-agent
  minReplicas: 3
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "100"
  - type: External
    external:
      metric:
        name: queue_depth
      target:
        type: Value
        value: "50"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### 3. Scaling via Helm

```bash
# Update replica count
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set replicaCount=15 \
  --set autoscaling.minReplicas=5 \
  --set autoscaling.maxReplicas=30 \
  --set autoscaling.targetCPUUtilizationPercentage=60
```

## Vertical Scaling

### 1. Update Resource Limits

```bash
# Increase CPU and memory
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set resources.limits.cpu=2000m \
  --set resources.limits.memory=4Gi \
  --set resources.requests.cpu=1000m \
  --set resources.requests.memory=2Gi
```

### 2. VPA (Vertical Pod Autoscaler)

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: function-gemma-agent-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: function-gemma-agent
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: function-gemma-agent
      maxAllowed:
        cpu: 4
        memory: 8Gi
      minAllowed:
        cpu: 100m
        memory: 128Mi
```

## Node Scaling

### 1. Add GPU Nodes for ML Workload

```bash
# Create GPU node pool (EKS example)
eksctl create nodegroup --cluster=production \
  --nodegroup-name=gpu-nodes \
  --node-type=p3.2xlarge \
  --nodes=2 --nodes-min=1 --nodes-max=5 \
  --node-labels=accelerator=nvidia-gpu \
  --asg-access \
  --external-dns-access
```

### 2. Taint Nodes for ML Workloads

```bash
# Taint GPU nodes
kubectl taint nodes -l accelerator=nvidia-gpu \
  nvidia.com/gpu=true:NoSchedule

# Add tolerations to deployment
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set tolerations[0].key=nvidia.com/gpu \
  --set tolerations[0].value=true \
  --set tolerations[0].effect=NoSchedule \
  --set nodeSelector.accelerator=nvidia-gpu
```

### 3. Cluster Autoscaler Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-autoscaler-status
data:
  nodes.max: "100"
  nodes.min: "3"
  scale-down-delay-after-add: "10m"
  scale-down-unneeded-time: "10m"
```

## Performance Tuning

### 1. Optimize Batch Size

```bash
# Increase batch size for higher throughput
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set env[0].name=BATCH_SIZE \
  --set env[0].value=16
```

### 2. Connection Pooling

```yaml
# Add to values.yaml
env:
  - name: DB_POOL_SIZE
    value: "20"
  - name: DB_MAX_OVERFLOW
    value: "30"
  - name: HTTP_POOL_SIZE
    value: "100"
```

### 3. Caching Strategy

```bash
# Enable Redis caching
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set redis.enabled=true \
  --set redis.master.persistence.size=20Gi
```

## Emergency Scaling

### 1. Burst Handling

```bash
# Quick scale to handle traffic burst
kubectl patch deployment function-gemma-agent -n production -p '{"spec":{"replicas":50}}'

# Add burst capacity with different service
helm install function-gemma-agent-burst k8s/chart/ \
  --namespace production \
  --set fullnameOverride=function-gemma-agent-burst \
  --set replicaCount=20 \
  --set resources.requests.cpu=500m \
  --set resources.requests.memory=512Mi
```

### 2. Traffic Splitting

```yaml
# Split traffic between regular and burst instances
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: function-gemma-agent
spec:
  http:
  - match:
    - headers:
        priority:
          exact: high
    route:
    - destination:
        host: function-gemma-agent-burst
      weight: 100
  - route:
    - destination:
        host: function-gemma-agent
      weight: 80
    - destination:
        host: function-gemma-agent-burst
      weight: 20
```

## Monitoring Scaling Events

### 1. HPA Events

```bash
# Watch HPA events
kubectl get hpa function-gemma-agent -n production --watch

# Check scaling events
kubectl describe hpa function-gemma-agent -n production
```

### 2. Custom Metrics Dashboard

```yaml
# Grafana panel queries
- CPU Utilization: avg(rate(container_cpu_usage_seconds_total[5m])) * 100
- Memory Usage: container_memory_usage_bytes / container_spec_memory_limit_bytes * 100
- Request Rate: sum(rate(http_requests_total[5m]))
- Latency: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
- Queue Depth: rabbitmq_queue_messages
```

## Cost Optimization

### 1. Right-Sizing Recommendations

```bash
# Get resource usage report
kubectl top nodes --use-protocol-buffers
kubectl top pods -n production --use-protocol-buffers

# Generate recommendations
kubectl get pods -n production -o json | jq '.items[] | {name: .metadata.name, cpu: .spec.containers[0].resources.requests.cpu, memory: .spec.containers[0].resources.requests.memory}'
```

### 2. Spot Instance Usage

```yaml
# Add spot instances to node pool
apiVersion: v1
kind: Node
metadata:
  labels:
    node-lifecycle: spot
spec:
  taints:
  - key: spot-instance
    value: "true"
    effect: NoSchedule
```

### 3. Scheduled Scaling

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-down-night
spec:
  schedule: "0 22 * * *"  # 10 PM daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: scaler
            image: bitnami/kubectl
            command:
            - /bin/sh
            - -c
            - kubectl scale deployment/function-gemma-agent --replicas=2 -n production
          restartPolicy: OnFailure
```

## Disaster Recovery Scaling

### 1. Multi-Region Scaling

```bash
# Deploy to secondary region
helm install function-gemma-agent-dr k8s/chart/ \
  --namespace production \
  --set global.region=us-west-2 \
  --set replicaCount=5
```

### 2. Blue-Green Scaling

```bash
# Scale green environment
helm upgrade function-gemma-agent-green k8s/chart/ \
  --namespace production-green \
  --set replicaCount=20

# Switch traffic
kubectl patch service function-gemma-agent -n production -p '{"spec":{"selector":{"version":"green"}}}'
```

## Troubleshooting

### Scaling Not Working

1. **Check HPA Metrics**
```bash
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/production/pods/*/http_requests_per_second"
```

2. **Verify Resource Requests**
```bash
kubectl describe deployment function-gemma-agent -n production | grep -A 10 "Requests:"
```

3. **Check Cluster Resources**
```bash
kubectl describe nodes | grep -A 5 "Allocated resources:"
```

### Pod Crashes After Scaling

1. **Check Resource Limits**
```bash
kubectl describe pod <pod-name> -n production | grep -A 10 "Limits:"
```

2. **View OOM Events**
```bash
kubectl get events -n production --sort-by=.metadata.creationTimestamp | grep OOMKilled
```

## Related Procedures

- [OPS-001: Emergency Rollback](OPS-001-ROLLBACK.md)
- [OPS-002: Reasoning Drift Alert](OPS-002-DRIFT-ALERT.md)
- [Cost Optimization Guide](../COST-OPTIMIZATION.md)

## Checklist

- [ ] Identify scaling trigger (CPU/memory/latency)
- [ ] Choose scaling strategy (horizontal/vertical)
- [ ] Execute scaling command
- [ ] Verify pod health and readiness
- [ ] Monitor metrics for stability
- [ ] Update HPA if needed
- [ ] Document scaling event
- [ ] Review cost impact
- [ ] Schedule follow-up review

---

**Last Updated**: 2025-12-26  
**Version**: 1.0  
**Owner**: DevOps Team
