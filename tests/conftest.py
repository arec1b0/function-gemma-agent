import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from app.main import app
from app.infrastructure.ml.inference import GemmaService
from app.infrastructure.ml.loader import ModelLoader

@pytest.fixture
def mock_gemma_service(monkeypatch):
    """
    Mocks the GemmaService to avoid loading the real model during tests.
    """
    mock_service = MagicMock(spec=GemmaService)
    
    # Mock the generate method to return a deterministic string
    mock_service.generate.return_value = "This is a mock response."
    
    # Mock the parse_output method
    mock_service.parse_output.return_value = (None, None)
    
    # Apply patch
    monkeypatch.setattr("app.domain.agent.gemma_service", mock_service)
    
    return mock_service

@pytest.fixture
def client(mock_gemma_service):
    """
    FastAPI Test Client with mocked ML service.
    """
    # Prevent model loader from actually loading during startup
    with pytest.MonkeyPatch.context() as m:
        m.setattr(ModelLoader, "load_model", lambda self: None)
        with TestClient(app) as c:
            yield c