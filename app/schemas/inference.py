from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
import re

class InferenceRequest(BaseModel):
    """
    Strict inference request model with security validations.
    """
    prompt: str = Field(
        ..., 
        min_length=1, 
        max_length=10000,
        description="The input prompt for generation"
    )
    max_tokens: int = Field(
        default=512,
        ge=1,
        le=4096,
        description="Maximum number of tokens to generate (1-4096)"
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0)"
    )
    session_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional session ID for tracking"
    )
    
    @validator('prompt')
    def validate_prompt(cls, v):
        """Reject suspicious patterns in prompts."""
        # Check for extremely long repeating sequences
        if re.search(r'(.)\1{100,}', v):
            raise ValueError('Prompt contains suspicious repeating patterns')
        
        # Check for null bytes and other control characters
        if '\x00' in v or '\x0b' in v or '\x0c' in v:
            raise ValueError('Prompt contains invalid control characters')
            
        # Check for excessive whitespace (potential DoS)
        if len(re.findall(r'\s', v)) > len(v) * 0.9:
            raise ValueError('Prompt contains excessive whitespace')
            
        return v
    
    @validator('session_id')
    def validate_session_id(cls, v):
        """Ensure session ID contains only safe characters."""
        if v is not None and not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Session ID can only contain alphanumeric characters, underscores, and hyphens')
        return v

class InferenceResponse(BaseModel):
    """
    Inference response model.
    """
    response: str = Field(..., description="The generated response")
    actions_taken: List[Dict[str, Any]] = Field(default=[], description="List of tools executed")
    latency_ms: float = Field(..., description="Execution time in milliseconds")
    tokens_used: Optional[int] = Field(None, description="Number of tokens generated")
