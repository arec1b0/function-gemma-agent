import sys
from loguru import logger
from app.core.config import settings

def setup_logging():
    """
    Configures the logging system using Loguru.
    Intercepts standard library logging and redirects to Loguru.
    """
    # Remove default handlers
    logger.remove()
    
    # Define format
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Add console handler
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=log_format,
        serialize=settings.JSON_LOGS  # JSON format is better for MLOps aggregators
    )
    
    # Add file handler with rotation
    logger.add(
        "logs/agent.log",
        rotation="500 MB",
        retention="10 days",
        level="INFO",
        compression="zip"
    )

    return logger

# Initialize logger instance
log = setup_logging()