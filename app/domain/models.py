from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class AgentRequest(BaseModel):
    """
    Represents the incoming user query.
    """
    query: str = Field(..., description="The user's natural language request")
    session_id: Optional[str] = Field(None, description="For tracking conversation context")

class AgentResponse(BaseModel):
    """
    Represents the final response from the agent.
    """
    query: str
    response: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Log of tools executed")
    execution_time_ms: float