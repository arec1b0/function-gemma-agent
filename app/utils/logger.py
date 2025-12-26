import sys
import structlog
import logging
from typing import Any, Dict
from contextvars import ContextVar
from app.core.config import settings

# Context variables for request-scoped data
request_id: ContextVar[str] = ContextVar('request_id', default='')
model_version: ContextVar[str] = ContextVar('model_version', default='unknown')
user_id: ContextVar[str] = ContextVar('user_id', default='')

def configure_structlog() -> structlog.stdlib.BoundLogger:
    """
    Configure structlog with JSON renderer for production and console for dev.
    """
    # Configure structlog processors
    processors = [
        # Add context variables from contextvars
        structlog.contextvars.merge_contextvars,
        # Add timestamp
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add call site
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Stack driver renderer for better JSON output
        structlog.processors.StackInfoRenderer(),
        # Format exception
        structlog.processors.format_exc_info,
    ]
    
    # Choose renderer based on environment
    if settings.JSON_LOGS or settings.ENV == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging to forward to structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )
    
    return structlog.get_logger()

# Initialize the logger
log = configure_structlog()

def get_logger_with_context(**kwargs) -> structlog.stdlib.BoundLogger:
    """
    Get a logger with additional context bound to it.
    
    Usage:
        logger = get_logger_with_context(request_id="123", user_id="user1")
        logger.info("Processing request", tool="search")
    """
    return log.bind(**kwargs)

def set_request_context(request_id_val: str, model_version_val: str = None, user_id_val: str = None):
    """
    Set context variables for the current request.
    This should be called at the beginning of each request.
    """
    if request_id_val:
        request_id.set(request_id_val)
    if model_version_val:
        model_version.set(model_version_val)
    if user_id_val:
        user_id.set(user_id_val)

# For backward compatibility, maintain the old interface
def setup_logging():
    """Backward compatibility function."""
    return log
