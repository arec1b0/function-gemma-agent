import time
import json
from typing import Dict, Any, List
from app.domain.models import AgentRequest, AgentResponse
from app.infrastructure.ml import gemma_service
from app.infrastructure.tools import registry
from app.core.logger import log
from app.core.exceptions import ToolExecutionError
from app.inference.engine import tracing_engine
from app.observability.metrics import record_reasoning_failure

class AgentService:
    """
    Orchestrator service that manages the ReAct (Reason + Act) loop.
    It connects the ML model with the execution tools.
    """

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Main entry point for processing a user query.
        Now uses ReAct reasoning loop for multi-step tasks.
        """
        start_time = time.perf_counter()
        
        log.info(f"Processing agent request: {request.query}")
        
        # 1. Prepare Tools Schema
        tools_schema = registry.get_all_schemas()
        
        # 2. Use ReAct reasoning loop
        react_result = tracing_engine.react_reasoning_loop(
            initial_query=request.query,
            gemma_service=gemma_service,
            tools_schema=tools_schema
        )
        
        # Collect training data
        tracing_engine.collect_training_data(request.query, react_result)
        
        # 3. Construct Response
        execution_time = (time.perf_counter() - start_time) * 1000
        
        # Trace the request with MLflow
        tracing_engine.trace_inference(
            prompt=request.query,
            response=react_result["response"],
            tool_calls=react_result["tool_calls"],
            latency_ms=execution_time,
            tokens_used=None  # TODO: Get from gemma_service
        )
        
        return AgentResponse(
            query=request.query,
            response=react_result["response"],
            tool_calls=react_result["tool_calls"],
            execution_time_ms=round(execution_time, 2)
        )

# Global Service Instance
agent_service = AgentService()