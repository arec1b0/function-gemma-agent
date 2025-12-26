import time
import json
import uuid
import os
from typing import Dict, Any, List, Optional, ContextManager
from contextlib import contextmanager
import mlflow
import mlflow.sklearn
from app.utils.logger import log, get_logger_with_context, set_request_context
from app.observability.metrics import record_tool_usage, record_reasoning_failure, record_token_generation
from app.core.config import settings

# Configure MLflow
MLFLOW_EXPERIMENT_NAME = "function-gemma-agent"
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")

# Set up MLflow tracking
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

@contextmanager
def mlflow_trace(request_id: str, model_name: str = "functiongemma-270m-it") -> ContextManager[mlflow.ActiveRun]:
    """
    Context manager for MLflow tracing of inference requests.
    
    Args:
        request_id: Unique identifier for the request
        model_name: Name of the model being used
    
    Usage:
        with mlflow_trace("req-123") as run:
            # Do inference work
            mlflow.log_param("prompt", prompt)
            mlflow.log_metric("latency", latency)
    """
    with mlflow.start_run(run_name=f"request-{request_id}") as run:
        # Log basic parameters
        mlflow.log_param("model_name", model_name)
        mlflow.log_param("request_id", request_id)
        mlflow.log_param("timestamp", time.time())
        
        # Set tags for better organization
        mlflow.set_tag("model_version", model_name)
        mlflow.set_tag("request_id", request_id)
        mlflow.set_tag("component", "inference")
        
        yield run

class TracingEngine:
    """
    Engine that wraps inference operations with comprehensive tracing.
    Integrates MLflow for trace visualization and metrics for monitoring.
    """
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.MODEL_ID
        self.logger = get_logger_with_context(component="tracing_engine")
    
    def trace_inference(
        self,
        prompt: str,
        response: str,
        tool_calls: List[Dict[str, Any]] = None,
        latency_ms: float = None,
        tokens_used: int = None,
        error: str = None
    ) -> str:
        """
        Trace a complete inference request with MLflow.
        
        Args:
            prompt: Input prompt
            response: Generated response
            tool_calls: List of tool executions
            latency_ms: Execution time in milliseconds
            tokens_used: Number of tokens generated
            error: Error message if any
            
        Returns:
            request_id: Unique identifier for this request
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Set context for structured logging
        set_request_context(
            request_id=request_id,
            model_version=self.model_name
        )
        
        # Start MLflow trace
        with mlflow_trace(request_id, self.model_name) as run:
            try:
                # Log input/output
                mlflow.log_param("prompt", prompt[:1000] + "..." if len(prompt) > 1000 else prompt)
                mlflow.log_param("prompt_length", len(prompt))
                
                if error:
                    mlflow.log_param("error", error)
                    mlflow.set_tag("status", "error")
                else:
                    mlflow.log_param("response", response[:1000] + "..." if len(response) > 1000 else response)
                    mlflow.log_param("response_length", len(response))
                    mlflow.set_tag("status", "success")
                
                # Log metrics
                if latency_ms:
                    mlflow.log_metric("latency_ms", latency_ms)
                    mlflow.log_metric("latency_seconds", latency_ms / 1000)
                
                if tokens_used:
                    mlflow.log_metric("tokens_used", tokens_used)
                    # Record token generation metrics
                    record_token_generation(self.model_name, tokens_used, latency_ms / 1000)
                
                # Log tool calls as nested runs for better visualization
                if tool_calls:
                    mlflow.log_param("num_tool_calls", len(tool_calls))
                    
                    for i, tool_call in enumerate(tool_calls):
                        # Create a nested run for each tool call
                        with mlflow.start_run(
                            run_name=f"tool-{tool_call.get('tool', 'unknown')}-{i}",
                            nested=True,
                            experiment_id=run.info.experiment_id
                        ) as tool_run:
                            mlflow.log_param("tool_name", tool_call.get("tool"))
                            mlflow.log_param("tool_arguments", json.dumps(tool_call.get("arguments", {})))
                            
                            if "result" in tool_call:
                                mlflow.log_param("tool_result", str(tool_call["result"])[:500])
                                mlflow.set_tag("status", "success")
                                record_tool_usage(tool_call.get("tool"), True)
                            elif "error" in tool_call:
                                mlflow.log_param("tool_error", tool_call["error"])
                                mlflow.set_tag("status", "failed")
                                record_tool_usage(tool_call.get("tool"), False)
                            
                            # Link to parent run
                            mlflow.set_tag("parent_run_id", run.info.run_id)
                
                # Log to structured logger
                self.logger.info(
                    "Inference completed",
                    request_id=request_id,
                    prompt_length=len(prompt),
                    response_length=len(response) if response else 0,
                    num_tools=len(tool_calls) if tool_calls else 0,
                    latency_ms=latency_ms,
                    has_error=error is not None
                )
                
                return request_id
                
            except Exception as e:
                self.logger.error(
                    "Failed to trace inference",
                    request_id=request_id,
                    error=str(e)
                )
                mlflow.log_param("tracing_error", str(e))
                return request_id
    
    def trace_reasoning_step(
        self,
        step_type: str,  # "think", "act", "observe"
        content: str,
        request_id: str,
        step_number: int,
        metadata: Dict[str, Any] = None
    ):
        """
        Trace individual reasoning steps for detailed analysis.
        
        Args:
            step_type: Type of reasoning step
            content: Content of the step
            request_id: Parent request ID
            step_number: Order of this step
            metadata: Additional metadata
        """
        with mlflow.start_run(
            run_name=f"step-{step_number}-{step_type}",
            nested=True
        ) as step_run:
            mlflow.log_param("step_type", step_type)
            mlflow.log_param("step_number", step_number)
            mlflow.log_param("content", content[:500] + "..." if len(content) > 500 else content)
            mlflow.log_param("request_id", request_id)
            
            if metadata:
                for key, value in metadata.items():
                    mlflow.log_param(f"meta_{key}", str(value))
            
            # Log to structured logger
            self.logger.info(
                "Reasoning step",
                request_id=request_id,
                step_type=step_type,
                step_number=step_number,
                content_length=len(content)
            )

# Global tracing engine instance
tracing_engine = TracingEngine()
