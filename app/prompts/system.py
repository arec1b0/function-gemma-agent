from typing import List, Dict, Any, Optional
from app.rag.retriever import knowledge_retriever
from app.utils.logger import log

class PromptManager:
    """
    Manages system prompts with few-shot examples for small models.
    Dynamically injects relevant examples based on the query.
    """
    
    def __init__(self):
        self.base_system_prompt = """You are an expert MLOps Site Reliability Engineer managing Kubernetes clusters.
You have access to tools to check status, get logs, and search documentation.
Always think step by step and use tools when needed.

Important rules:
1. If you need information, search the knowledge base FIRST
2. Use tools to get real-time data from clusters
3. Provide clear, actionable responses
4. Always format tool calls in valid JSON
5. Map 'prod'/'production' to cluster_id='prod' and 'dev'/'development' to 'dev'"""
        
        self.few_shot_examples = [
            {
                "task": "Check pod status",
                "query": "Check the status of pods in production",
                "thinking": "The user wants to check pod status in production. I should use the get_pod_status tool with cluster_id='prod'.",
                "tool_call": """<start_function_call>
call: get_pod_status
{"cluster_id": "prod"}
<end_function_call>"""
            },
            {
                "task": "Get logs for issue",
                "query": "Get logs for the failing api-service pod",
                "thinking": "The user wants logs for a specific pod. I need to use get_pod_logs with the pod name and cluster.",
                "tool_call": """<start_function_call>
call: get_pod_logs
{"cluster_id": "prod", "pod_name": "api-service", "tail_lines": 50}
<end_function_call>"""
            },
            {
                "task": "Search documentation",
                "query": "What is the restart policy for critical services?",
                "thinking": "The user is asking about policy information. I should search the knowledge base first.",
                "tool_call": """<start_function_call>
call: search_knowledge_base
{"query": "restart policy critical services"}
<end_function_call>"""
            },
            {
                "task": "Multi-step troubleshooting",
                "query": "The payment service is down, investigate",
                "thinking": "I need to first check the pod status, then if it's degraded, get logs to understand why.",
                "tool_call": """<start_function_call>
call: get_pod_status
{"cluster_id": "prod"}
<end_function_call>"""
            }
        ]
    
    def build_system_prompt(self, query: str, tools_schema: List[Dict[str, Any]]) -> str:
        """
        Build a system prompt with relevant few-shot examples.
        
        Args:
            query: The user's query
            tools_schema: Available tools schema
            
        Returns:
            Complete system prompt with examples
        """
        # Select relevant examples based on query
        examples = self._select_examples(query, max_examples=2)
        
        # Build the prompt
        prompt_parts = [self.base_system_prompt]
        
        if examples:
            prompt_parts.append("\n\nExamples:")
            for i, example in enumerate(examples, 1):
                prompt_parts.append(f"\nExample {i}:")
                prompt_parts.append(f"Task: {example['task']}")
                prompt_parts.append(f"Query: {example['query']}")
                prompt_parts.append(f"Thinking: {example['thinking']}")
                prompt_parts.append(f"Tool Call: {example['tool_call']}")
        
        # Add available tools info
        prompt_parts.append("\n\nAvailable Tools:")
        for tool in tools_schema:
            prompt_parts.append(f"- {tool['name']}: {tool['description']}")
        
        # Add strict format reminder
        prompt_parts.append("\n\nIMPORTANT: Always use this exact format for tool calls:")
        prompt_parts.append("<start_function_call>")
        prompt_parts.append("call: tool_name")
        prompt_parts.append('{"parameter": "value"}')
        prompt_parts.append("<end_function_call>")
        
        return "\n".join(prompt_parts)
    
    def _select_examples(self, query: str, max_examples: int = 2) -> List[Dict[str, Any]]:
        """
        Select relevant few-shot examples based on the query.
        
        Args:
            query: The user's query
            max_examples: Maximum number of examples to include
            
        Returns:
            List of relevant examples
        """
        query_lower = query.lower()
        scored_examples = []
        
        for example in self.few_shot_examples:
            score = 0
            
            # Check for keyword matches
            if "status" in query_lower and "status" in example['task'].lower():
                score += 2
            if "log" in query_lower and "log" in example['task'].lower():
                score += 2
            if "search" in query_lower or "documentation" in query_lower:
                if "search" in example['task'].lower():
                    score += 2
            if "down" in query_lower or "issue" in query_lower or "problem" in query_lower:
                if "troubleshooting" in example['task'].lower():
                    score += 2
            
            # Check for cluster mentions
            if "prod" in query_lower or "production" in query_lower:
                if "prod" in example['query'].lower():
                    score += 1
            if "dev" in query_lower or "development" in query_lower:
                if "dev" in example['query'].lower():
                    score += 1
            
            # Add base score for all examples
            score += 0.5
            
            scored_examples.append((score, example))
        
        # Sort by score and return top examples
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        
        return [example for _, example in scored_examples[:max_examples]]
    
    def build_thinking_prompt(self, context: str, step: int, examples: List[str] = None) -> str:
        """
        Build a prompt for the thinking step in ReAct loop.
        
        Args:
            context: Current context
            step: Current step number
            examples: Optional examples to include
            
        Returns:
            Thinking prompt
        """
        if step == 0:
            prompt = f"""Analyze this request step by step: {context}

Step 1: What is the user asking for?
Step 2: What information do I need?
Step 3: Should I search the knowledge base or use a tool?
Step 4: What specific action should I take?

Think carefully and then decide your action."""
        else:
            prompt = f"""Based on the previous steps, think about what to do next:

Context: {context}

What should I do next?
1. Search for more information?
2. Use a specific tool?
3. Provide the final answer?

Consider what information I still need to answer the user's question."""
        
        # Add examples if provided
        if examples:
            prompt += f"\n\nReference examples:\n" + "\n".join(examples)
        
        return prompt
    
    def get_json_format_reminder(self) -> str:
        """Get a reminder about JSON format for tool calls."""
        return """
REMEMBER: Tool calls must use valid JSON format:
- Use double quotes for strings: {"key": "value"}
- Don't use trailing commas
- Escape quotes inside strings: {"text": "He said \"hello\""}

Examples:
✅ Correct: {"cluster_id": "prod", "namespace": "default"}
❌ Wrong: {cluster_id: 'prod', namespace: 'default',}
"""

# Global prompt manager
prompt_manager = PromptManager()
