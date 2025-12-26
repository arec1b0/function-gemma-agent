import time
import json
from typing import Dict, Any, List
from app.domain.models import AgentRequest, AgentResponse
from app.infrastructure.ml import gemma_service
from app.infrastructure.tools import registry
from app.core.logger import log
from app.core.exceptions import ToolExecutionError

class AgentService:
    """
    Orchestrator service that manages the ReAct (Reason + Act) loop.
    It connects the ML model with the execution tools.
    """

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Main entry point for processing a user query.
        """
        start_time = time.perf_counter()
        
        log.info(f"Processing agent request: {request.query}")
        
        # 1. Prepare Tools Schema
        tools_schema = registry.get_all_schemas()
        
        # 2. Prepare Messages with System Instruction
        # Crucial for 270M models: Be explicit about the role and parameter inference.
        system_instruction = (
            "You are an expert MLOps Site Reliability Engineer. "
            "Your job is to manage Kubernetes clusters using the available tools. "
            "If a user asks for 'prod' or 'production', map it to cluster_id='prod'. "
            "If a user asks for 'dev' or 'development', map it to cluster_id='dev'. "
            "Do not ask for clarification if the intent is reasonably clear. "
            "Execute the function immediately."
        )

        messages = [
            {"role": "user", "content": f"{system_instruction}\n\nUser Query: {request.query}"}
        ]

        # 3. Model Inference (Reasoning)
        generated_text = gemma_service.generate(messages, tools_schema)
        
        tool_calls_log = []
        final_response_text = generated_text

        # 4. Check for Function Call (Acting)
        func_name, func_args = gemma_service.parse_output(generated_text)
        
        if func_name:
            log.info(f"Model triggered function call: {func_name} with args: {func_args}")
            
            try:
                # Execute the tool safely
                tool_result = registry.execute_tool(func_name, func_args)
                
                # Log the action
                tool_calls_log.append({
                    "tool": func_name,
                    "arguments": func_args,
                    "result": tool_result,
                    "status": "success"
                })
                
                # Format the result for the final output
                final_response_text = (
                    f"Action Taken: {func_name}\n"
                    f"Arguments: {json.dumps(func_args)}\n"
                    f"System Output: {json.dumps(tool_result, indent=2)}"
                )
                
            except Exception as e:
                log.error(f"Tool execution failed: {e}")
                tool_calls_log.append({
                    "tool": func_name,
                    "arguments": func_args,
                    "error": str(e),
                    "status": "failed"
                })
                final_response_text = f"Error executing action {func_name}: {str(e)}"
        else:
            log.info("Model generated a natural language response (no tool execution).")

        # 5. Construct Response
        execution_time = (time.perf_counter() - start_time) * 1000
        
        return AgentResponse(
            query=request.query,
            response=final_response_text,
            tool_calls=tool_calls_log,
            execution_time_ms=round(execution_time, 2)
        )

# Global Service Instance
agent_service = AgentService()