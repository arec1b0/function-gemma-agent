# OPS-002: Reasoning Drift Alert Runbook

## Purpose

This runbook provides procedures for identifying and mitigating reasoning drift in the FunctionGemma Agent when the model's reasoning quality degrades over time.

## Alert Definition

**Alert Name**: `ReasoningDriftHigh`  
**Severity**: Warning  
**Condition**: `agent_reasoning_quality_score < 0.7 for 5m`  
**Dashboard**: [Grafana - Agent Quality](https://grafana.example.com/d/agent-quality)

## What is Reasoning Drift?

Reasoning drift occurs when the model:
- Produces inconsistent or illogical reasoning chains
- Fails to follow ReAct (Think-Act-Observe) patterns correctly
- Makes repetitive or circular arguments
- Ignores tool results or context
- Shows degraded task completion rates

## Prerequisites

- Access to Grafana dashboards
- kubectl cluster access
- MLflow UI access
- Understanding of the ReAct reasoning patterns

## Initial Investigation

### 1. Verify Alert Validity

```bash
# Check current reasoning quality metrics
curl -s https://agent.example.com/api/v1/metrics | grep reasoning_quality

# Check recent reasoning traces in MLflow
# Navigate to: https://mlflow.example.com/experiments/1
# Filter by last 1 hour, sort by reasoning_quality descending
```

### 2. Identify Affected Queries

```bash
# Get logs of recent requests with low reasoning scores
kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent \
  --since=1h | grep "reasoning_score" | grep "LOW"

# Sample problematic requests
kubectl logs -n production -l app.kubernetes.io/name=function-gemma-agent \
  --since=1h | grep -B5 -A5 "reasoning_failure"
```

### 3. Check Correlations

- **Recent Deployments**: Any new code/model deployments?
- **Data Changes**: Updates to knowledge base or prompts?
- **Load**: Sudden spike in traffic?
- **Infrastructure**: Resource constraints?

## Mitigation Procedures

### Option 1: Prompt Refresh (Quick Fix)

If drift is prompt-related:

1. **Check Active Prompts**
```bash
# View current system prompts
kubectl get configmap function-gemma-agent-config -n production -o yaml
```

2. **Rollback Prompt Changes**
```bash
# Get previous prompt version
helm history function-gemma-agent -n production | grep "prompt-update"

# Rollback to previous version
helm rollback function-gemma-agent <revision> -n production
```

3. **Verify Fix**
Monitor reasoning quality metric for 10 minutes

### Option 2: Model Rollback

If model is causing drift:

1. **Identify Last Good Model**
```bash
# Check deployed model version
kubectl get deployment function-gemma-agent -n production \
  -o jsonpath='{.spec.template.spec.containers[0].image}'

# Check model performance in MLflow
# Compare with previous model versions
```

2. **Rollback Model**
```bash
# Rollback to previous deployment
helm rollback function-gemma-agent 0 -n production

# Or update image tag specifically
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set image.tag=sha-<previous-good-sha>
```

### Option 3: Knowledge Base Issue

If RAG is causing issues:

1. **Check Vector Store Health**
```bash
# Connect to ChromaDB
kubectl exec -it -n production deployment/chromadb -- python
>>> import chromadb
>>> client = chromadb.HttpClient()
>>> collection = client.get_collection("knowledge")
>>> count = collection.count()
>>> print(f"Documents in store: {count}")
```

2. **Check Recent Ingestions**
```bash
# Check for recent knowledge base updates
kubectl logs -n deployment/knowledge-ingestor --since=24h
```

3. **Rollback Knowledge Base**
```bash
# Restore previous vector store backup
kubectl apply -f backups/vector-store-2025-12-25.yaml
```

### Option 4: Configuration Tuning

Adjust model parameters:

1. **Increase Temperature** (for more diverse reasoning)
```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set env[0].name=MODEL_TEMPERATURE \
  --set env[0].value=0.8
```

2. **Adjust Max Tokens**
```bash
helm upgrade function-gemma-agent k8s/chart/ \
  --namespace production \
  --set env[1].name=MAX_TOKENS \
  --set env[1].value=2048
```

## Deep Dive Analysis

### 1. Collect Reasoning Traces

```python
# Script to analyze reasoning patterns
import mlflow
import pandas as pd

# Get recent runs
experiment = mlflow.get_experiment_by_name("function-gemma-agent")
runs = mlflow.search_runs(experiment.experiment_id, 
                         filter_string="metrics.reasoning_quality < 0.7")

# Analyze common failure patterns
df = pd.DataFrame(runs)
failure_modes = df['tags.reasoning_failure'].value_counts()
print(failure_modes.head())
```

### 2. Compare with Baseline

```bash
# Export baseline data
mlflow experiments export --experiment-id 1 --output-dir baseline-data/

# Compare current performance
python scripts/compare_performance.py \
  --baseline baseline-data/ \
  --current current-data/ \
  --output drift-analysis.html
```

### 3. Root Cause Analysis

Common causes of reasoning drift:

1. **Model Degradation**
   - Model weights corruption
   - Quantization artifacts
   - Version incompatibility

2. **Prompt Injection Issues**
   - Malformed context
   - Prompt length overflow
   - Special token interference

3. **Tool Execution Failures**
   - Tool returning malformed data
   - Timeout issues
   - Permission problems

4. **RAG Retrieval Problems**
   - Low-quality embeddings
   - Outdated knowledge
   - Poor similarity matching

## Prevention Measures

### 1. Automated Quality Monitoring

```yaml
# Add to Prometheus rules
groups:
- name: reasoning_quality
  rules:
  - alert: ReasoningDriftHigh
    expr: avg_over_time(reasoning_quality_score[5m]) < 0.7
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Reasoning quality degraded"
      description: "Reasoning quality is {{ $value }} below threshold"
```

### 2. Continuous Evaluation

```python
# Automated evaluation script
def evaluate_reasoning_quality():
    test_cases = load_test_cases()
    results = []
    
    for case in test_cases:
        response = agent_service.process_request(case)
        score = evaluate_reasoning(response)
        results.append(score)
    
    avg_score = sum(results) / len(results)
    
    if avg_score < 0.8:
        send_alert(f"Reasoning quality: {avg_score}")
    
    mlflow.log_metric("automated_quality_score", avg_score)
```

### 3. Model Versioning

- Always tag model versions with quality metrics
- Maintain golden dataset for evaluation
- A/B test new models before full rollout

## Escalation Procedures

### Level 1: On-call Engineer (First 30 minutes)

1. Execute quick mitigation (Option 1 or 2)
2. Monitor metrics for 15 minutes
3. Document actions in incident log

### Level 2: ML Engineer (If unresolved after 30 minutes)

1. Perform deep dive analysis
2. Check training data quality
3. Evaluate model retraining needs

### Level 3: Research Team (If persistent issue)

1. Investigate fundamental model issues
2. Consider architecture changes
3. Plan model retraining pipeline

## Post-Incident Actions

### 1. Root Cause Report

Document:
- Timeline of drift detection
- Root cause analysis
- Mitigation effectiveness
- Prevention measures

### 2. Model Retraining (if needed)

```bash
# Trigger retraining pipeline
kubectl create job --from=cronjob/model-retraining retraining-$(date +%Y%m%d)

# Monitor training
kubectl logs -f job/retraining-$(date +%Y%m%d)
```

### 3. Update Monitoring

- Add specific alert for identified issue
- Create dashboard for new metric
- Update runbook with learned lessons

## Related Procedures

- [OPS-001: Emergency Rollback](OPS-001-ROLLBACK.md)
- [OPS-003: Scaling Operations](OPS-003-SCALING.md)
- [ML Retraining Guide](../ml/RETRAINING.md)

## Checklist

- [ ] Alert verified and validated
- [ ] Initial investigation completed
- [ ] Mitigation procedure applied
- [ ] Reasoning quality improved (>0.8)
- [ ] Stability maintained for 30 minutes
- [ ] Root cause identified
- [ ] Incident documented
- [ ] Prevention measures implemented
- [ ] Monitoring updated

---

**Last Updated**: 2025-12-26  
**Version**: 1.0  
**Owner**: ML Engineering Team
