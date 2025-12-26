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
from app.rag.retriever import knowledge_retriever
from app.training.collector import training_collector
from app.prompts.system import prompt_manager

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
    Now includes ReAct reasoning loop for multi-step tasks.
    """
    
    def __init__(self, model_name: str = None, max_steps: int = 5):
        self.model_name = model_name or settings.MODEL_ID
        self.logger = get_logger_with_context(component="tracing_engine")
        self.max_steps = max_steps
        self.retriever = knowledge_retriever
    
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
    
    def react_reasoning_loop(
        self,
        initial_query: str,
        gemma_service,
        tools_schema: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a ReAct (Reason-Act-Observe) reasoning loop.
        
        Args:
            initial_query: The initial user query
            gemma_service: The Gemma service for generation
            tools_schema: Available tools schema
            
        Returns:
            Dictionary with final response, tool calls, and reasoning trace
        """
        reasoning_trace = []
        tool_calls_log = []
        current_context = initial_query
        final_response = None
        completed = False
        
        for step in range(self.max_steps):
            self.logger.info(
                "ReAct step",
                step=step + 1,
                max_steps=self.max_steps,
                context_length=len(current_context)
            )
            
            # Step 1: THINK - Analyze current state
            think_prompt = self._build_think_prompt(current_context, step)
            thought = self._generate_thought(gemma_service, think_prompt, tools_schema)
            reasoning_trace.append({
                "step": step + 1,
                "type": "think",
                "content": thought,
                "context": current_context[:200] + "..." if len(current_context) > 200 else current_context
            })
            
            # Step 2: ACT - Decide on action
            action_result = self._execute_action(
                gemma_service, 
                thought, 
                current_context, 
                tools_schema,
                tool_calls_log
            )
            
            if action_result["action"] == "answer":
                final_response = action_result["response"]
                completed = True
                reasoning_trace.append({
                    "step": step + 1,
                    "type": "final_answer",
                    "content": final_response
                })
                break
            
            # Step 3: OBSERVE - Process tool output
            observation = action_result["observation"]
            current_context = self._update_context(current_context, thought, observation)
            
            reasoning_trace.append({
                "step": step + 1,
                "type": "observe",
                "content": observation
            })
            
            # Check if we should continue
            if action_result.get("should_continue", False) is False:
                break
        
        # If we didn't complete, generate a final response
        if not completed and not final_response:
            final_response = self._generate_fallback_response(current_context, reasoning_trace)
        
        return {
            "response": final_response,
            "tool_calls": tool_calls_log,
            "reasoning_trace": reasoning_trace,
            "steps_taken": step + 1
        }
    
    def collect_training_data(self, initial_query: str, react_result: Dict[str, Any]):
        """
        Collect the interaction for training data.
        
        Args:
            initial_query: The original user query
            react_result: Result from react_reasoning_loop
        """
        try:
            training_collector.collect_inference(
                instruction=initial_query,
                reasoning_trace=react_result.get("reasoning_trace", []),
                tool_calls=react_result.get("tool_calls", []),
                output=react_result.get("response", ""),
                metadata={
                    "steps_taken": react_result.get("steps_taken", 0),
                    "model_name": self.model_name
                }
            )
        except Exception as e:
            log.error(f"Failed to collect training data: {e}")
    
    def _build_think_prompt(self, context: str, step: int) -> str:
        """Build a prompt for the thinking step."""
        # Get relevant examples for this step
        if step == 0:
            examples = prompt_manager._select_examples(context, max_examples=1)
            example_texts = [f"- {ex['task']}: {ex['query']}" for ex in examples]
        else:
            example_texts = None
        
        return prompt_manager.build_thinking_prompt(context, step, example_texts)
    
    def _generate_thought(self, gemma_service, prompt: str, tools_schema: List[Dict[str, Any]]) -> str:
        """Generate a thought using the model."""
        messages = [{"role": "user", "content": prompt}]
        return gemma_service.generate(messages, tools_schema)
    
    def _execute_action(
        self,
        gemma_service,
        thought: str,
        context: str,
        tools_schema: List[Dict[str, Any]],
        tool_calls_log: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute an action based on the thought."""
        # Check if the thought indicates we should answer
        if self._should_answer(thought):
            return {
                "action": "answer",
                "response": self._extract_answer(thought),
                "should_continue": False
            }
        
        # Parse for tool calls
        func_name, func_args = gemma_service.parse_output(thought, 
            [tool['name'] for tool in tools_schema])
        
        if func_name:
            from app.infrastructure.tools import registry
            
            try:
                # Execute the tool
                tool_result = registry.execute_tool(func_name, func_args)
                
                # Log the tool call
                tool_calls_log.append({
                    "tool": func_name,
                    "arguments": func_args,
                    "result": tool_result,
                    "status": "success"
                })
                
                record_tool_usage(func_name, True)
                
                return {
                    "action": "tool_call",
                    "tool": func_name,
                    "observation": f"Tool {func_name} returned: {tool_result}",
                    "should_continue": True
                }
                
            except Exception as e:
                tool_calls_log.append({
                    "tool": func_name,
                    "arguments": func_args,
                    "error": str(e),
                    "status": "failed"
                })
                
                record_tool_usage(func_name, False)
                
                return {
                    "action": "tool_call",
                    "tool": func_name,
                    "observation": f"Tool {func_name} failed with error: {str(e)}",
                    "should_continue": True
                }
        
        # No tool call, check if we should answer
        return {
            "action": "answer",
            "response": thought,
            "should_continue": False
        }
    
    def _should_answer(self, thought: str) -> bool:
        """Check if the thought indicates we should provide a final answer."""
        answer_indicators = [
            "final answer",
            "the answer is",
            "conclusion",
            "based on the information",
            "therefore",
            "in conclusion"
        ]
        
        thought_lower = thought.lower()
        return any(indicator in thought_lower for indicator in answer_indicators)
    
    def _extract_answer(self, thought: str) -> str:
        """Extract the final answer from the thought."""
        # Simple extraction - in production, you'd use more sophisticated parsing
        if "final answer:" in thought.lower():
            parts = thought.split("final answer:")
            return parts[-1].strip() if len(parts) > 1 else thought
        return thought
    
    def _update_context(self, old_context: str, thought: str, observation: str) -> str:
        """Update the context for the next iteration."""
        return f"""Previous context: {old_context}

My thought: {thought}

Observation: {observation}

Now, based on this information, what should I do next?"""
    
    def _generate_fallback_response(self, context: str, trace: List[Dict[str, Any]]) -> str:
        """Generate a fallback response when the loop doesn't complete."""
        return f"""I wasn't able to complete your request within the allowed steps. 
Here's what I found: {context}

If you need more specific information, please let me know and I'll try a different approach."""

# Global tracing engine instance
tracing_engine = TracingEngine()
