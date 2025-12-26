import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "FunctionGemma Agent"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Model Configuration
    # Using the specific 270M instruction-tuned model as requested
    MODEL_ID: str = "google/functiongemma-270m-it"
    DEVICE_MAP: str = "auto" # Will select CPU or CUDA automatically
    MAX_NEW_TOKENS: int = 128
    TORCH_DTYPE: str = "bfloat16" # Optimal for modern CPUs/GPUs
    
    # Logging
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = True
    
    # Environment
    ENV: str = "development"
    
    # Security
    LLM_API_KEY: str = ""  # API key for authentication

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()