from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.core.config import settings
from app.core.logger import log

# Define the API key header
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)):
    """
    Validate API key from request header.
    
    Args:
        api_key: The API key from the X-API-Key header
        
    Returns:
        str: The validated API key
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    # Check if API key is configured
    if not settings.LLM_API_KEY:
        log.critical("LLM_API_KEY environment variable not set!")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured on server"
        )
    
    # Validate the provided API key
    if api_key != settings.LLM_API_KEY:
        log.warning(f"Invalid API key attempted: {api_key[:8]}..." if api_key else "No API key provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key"
        )
    
    return api_key
