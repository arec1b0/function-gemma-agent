from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from app.core.logger import log

# Create the limiter instance
# Using X-Forwarded-For header if available (for proxy setups)
def get_client_id(request: Request) -> str:
    """
    Get client ID for rate limiting.
    Uses X-Forwarded-For header if present (for reverse proxy setups),
    otherwise falls back to remote address.
    """
    # Check for X-Forwarded-For header (common in cloud/proxy setups)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one (original client)
        client_ip = forwarded_for.split(",")[0].strip()
        log.debug(f"Rate limiting using forwarded IP: {client_ip}")
        return client_ip
    
    # Fall back to remote address
    return get_remote_address(request)

# Initialize limiter
limiter = Limiter(key_func=get_client_id)

# Custom rate limit exceeded handler with logging
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded with logging.
    """
    client_id = get_client_id(request)
    log.warning(f"Rate limit exceeded for client {client_id} on {request.url.path}")
    
    # Create JSON response
    return Response(
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        status_code=429,
        headers={"Retry-After": str(exc.retry_after) if exc.retry_after else "60"}
    )
