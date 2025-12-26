from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logger import log
from app.api.routes import router as api_router
from app.infrastructure.ml.loader import model_loader
from app.api.limiter import limiter, rate_limit_exceeded_handler

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events: handled at startup and shutdown.
    Used here to pre-load the ML model into memory.
    """
    log.info("Starting up FunctionGemma Agent...")
    
    # Pre-load model to avoid cold start latency on first request
    try:
        model_loader.load_model()
        log.info("Model warm-up complete.")
    except Exception as e:
        log.critical(f"Failed to load model on startup: {e}")
        # We don't raise here to allow the app to start, 
        # but the health check might need to reflect this failure in a real scenario.
    
    yield
    
    log.info("Shutting down FunctionGemma Agent...")
    # Clean up resources if needed (e.g. close DB connections)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set up rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app", 
        host=settings.HOST, 
        port=settings.PORT, 
        reload=(settings.ENV == "development")
    )