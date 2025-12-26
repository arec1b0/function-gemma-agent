from fastapi import APIRouter, Depends, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.api.schemas import ChatRequest, ChatResponse
from app.domain.models import AgentRequest
from app.domain.agent import AgentService
from app.api.dependencies import get_agent_service
from app.api.security import get_api_key
from app.core.logger import log

router = APIRouter()

# Initialize limiter for route-specific limits
limiter = Limiter(key_func=get_remote_address)

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")  # Strict limit for chat endpoint
async def chat_endpoint(
    request: ChatRequest,
    service: AgentService = Depends(get_agent_service),
    api_key: str = Depends(get_api_key)
):
    """
    Primary endpoint to interact with the FunctionGemma Agent.
    """
    try:
        # Map API DTO to Domain Model
        domain_request = AgentRequest(
            query=request.prompt,
            session_id=request.session_id
        )
        
        # Execute logic
        result = await service.process_request(domain_request)
        
        # Map Domain Result to API Response
        return ChatResponse(
            response=result.response,
            actions_taken=result.tool_calls,
            latency_ms=result.execution_time_ms
        )
        
    except Exception as e:
        log.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error processing request.")

@router.get("/health")
async def health_check():
    """
    Simple health check for K8s liveness probes.
    No authentication required for load balancers and monitoring.
    """
    return {"status": "ok"}