import time
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import CollectorRegistry
from prometheus_client.exposition import MetricsHandler
from app.utils.logger import log

# Create a custom registry for our metrics
registry = CollectorRegistry()

# Define metrics with appropriate buckets and labels
# Histogram for token latency - buckets from 10ms to 5s
agent_token_latency_seconds = Histogram(
    'agent_token_latency_seconds',
    'Time spent generating tokens',
    ['model_name', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry
)

# Counter for tool usage
agent_tool_usage_total = Counter(
    'agent_tool_usage_total',
    'Total number of tool usage attempts',
    ['tool_name', 'status'],  # status: success, fail, timeout
    registry=registry
)

# Counter for request errors
agent_request_error_total = Counter(
    'agent_request_error_total',
    'Total number of request errors',
    ['error_type'],  # error_type: validation, authentication, model_error, timeout
    registry=registry
)

# Counter for reasoning failures (drift detection)
agent_reasoning_failure_total = Counter(
    'agent_reasoning_failure_total',
    'Total number of reasoning failures',
    ['failure_type'],  # failure_type: invalid_json, unknown_tool, infinite_loop
    registry=registry
)

# Gauge for active requests
agent_active_requests = Gauge(
    'agent_active_requests',
    'Number of currently active requests',
    registry=registry
)

# Histogram for request duration
agent_request_duration_seconds = Histogram(
    'agent_request_duration_seconds',
    'Total duration of requests',
    ['endpoint', 'status'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=registry
)

# Counter for tokens generated
agent_tokens_generated_total = Counter(
    'agent_tokens_generated_total',
    'Total number of tokens generated',
    ['model_name'],
    registry=registry
)

class MetricsMiddleware:
    """
    FastAPI middleware to automatically collect metrics for all endpoints.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract request info
        method = scope["method"]
        path = scope["path"]
        
        # Skip metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return
        
        # Start timing
        start_time = time.time()
        
        # Increment active requests
        agent_active_requests.inc()
        
        # Create a wrapped send to capture response status
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            # Process the request
            await self.app(scope, receive, send_wrapper)
            
            # Record metrics
            duration = time.time() - start_time
            status = "success" if 200 <= status_code < 400 else "error"
            
            agent_request_duration_seconds.labels(
                endpoint=path,
                status=status
            ).observe(duration)
            
            log.info(
                "Request completed",
                method=method,
                path=path,
                status_code=status_code,
                duration=duration
            )
            
        except Exception as e:
            # Record error
            duration = time.time() - start_time
            error_type = "internal_error"
            
            if "validation" in str(e).lower():
                error_type = "validation"
            elif "auth" in str(e).lower() or "permission" in str(e).lower():
                error_type = "authentication"
            
            agent_request_error_total.labels(error_type=error_type).inc()
            agent_request_duration_seconds.labels(
                endpoint=path,
                status="error"
            ).observe(duration)
            
            log.error(
                "Request failed",
                method=method,
                path=path,
                error=str(e),
                duration=duration
            )
            
            raise
        
        finally:
            # Decrement active requests
            agent_active_requests.dec()

def record_tool_usage(tool_name: str, success: bool, duration: float = None):
    """
    Record a tool usage event.
    
    Args:
        tool_name: Name of the tool used
        success: Whether the tool execution was successful
        duration: Optional duration of tool execution
    """
    status = "success" if success else "fail"
    agent_tool_usage_total.labels(tool_name=tool_name, status=status).inc()
    
    log.info(
        "Tool usage recorded",
        tool=tool_name,
        status=status,
        duration=duration
    )

def record_reasoning_failure(failure_type: str, details: Dict[str, Any] = None):
    """
    Record a reasoning failure for drift detection.
    
    Args:
        failure_type: Type of failure (invalid_json, unknown_tool, infinite_loop)
        details: Additional context about the failure
    """
    agent_reasoning_failure_total.labels(failure_type=failure_type).inc()
    
    log.warning(
        "Reasoning failure detected",
        failure_type=failure_type,
        details=details or {}
    )

def record_token_generation(model_name: str, num_tokens: int, latency: float):
    """
    Record token generation metrics.
    
    Args:
        model_name: Name of the model used
        num_tokens: Number of tokens generated
        latency: Time taken to generate tokens
    """
    agent_tokens_generated_total.labels(model_name=model_name).inc(num_tokens)
    agent_token_latency_seconds.labels(model_name=model_name, endpoint="/chat").observe(latency)
    
    log.info(
        "Token generation completed",
        model=model_name,
        tokens=num_tokens,
        latency=latency
    )

def get_metrics():
    """
    Get the latest metrics in Prometheus format.
    """
    return generate_latest(registry)
