from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.schemas.inference import InferenceRequest

class ChatRequest(InferenceRequest):
    """
    API Request model for the chat endpoint.
    Inherits security validations from InferenceRequest.
    """
    # Map 'prompt' from InferenceRequest to 'message' for API compatibility
    @property
    def message(self) -> str:
        return self.prompt
    
    @message.setter
    def message(self, value: str):
        self.prompt = value

class ChatResponse(BaseModel):
    """
    API Response model.
    """
    response: str = Field(..., description="The natural language response or action report.")
    actions_taken: List[Dict[str, Any]] = Field(default=[], description="List of tools executed.")
    latency_ms: float = Field(..., description="Execution time in milliseconds.")