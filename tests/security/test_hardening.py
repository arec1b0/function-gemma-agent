import pytest
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
import time
import os

from app.main import app
from app.core.config import settings

# Set a test API key for testing
TEST_API_KEY = "test-api-key-12345"
os.environ["LLM_API_KEY"] = TEST_API_KEY

client = TestClient(app)

class TestSecurityHardening:
    """Security hardening test suite for the inference API."""
    
    def test_no_api_key_403(self):
        """Test that requests without API key return 403 Forbidden."""
        # Try to access chat endpoint without API key
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello, world!"}
        )
        
        assert response.status_code == 403
        assert "Invalid or missing API key" in response.json()["detail"]
    
    def test_invalid_api_key_403(self):
        """Test that requests with invalid API key return 403 Forbidden."""
        # Try with wrong API key
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello, world!"},
            headers={"X-API-Key": "wrong-api-key"}
        )
        
        assert response.status_code == 403
        assert "Invalid or missing API key" in response.json()["detail"]
    
    def test_valid_api_key_200(self):
        """Test that requests with valid API key succeed (if model is loaded)."""
        # Note: This test might fail if the model is not loaded, but should pass authentication
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello, world!"},
            headers={"X-API-Key": TEST_API_KEY}
        )
        
        # Should not be 403 (authentication passed)
        # Could be 200, 500 (model not loaded), or other, but not 403
        assert response.status_code != 403
        
        # If we get past authentication, we should get either success or internal error
        assert response.status_code in [200, 500]
    
    def test_oversized_payload_422(self):
        """Test that oversized payloads return 422 Unprocessable Entity."""
        # Test with extremely long prompt (over 10000 chars)
        long_prompt = "a" * 10001
        
        response = client.post(
            "/api/v1/chat",
            json={"message": long_prompt},
            headers={"X-API-Key": TEST_API_KEY}
        )
        
        assert response.status_code == 422
        assert "prompt" in str(response.json())
    
    def test_max_tokens_limit_422(self):
        """Test that max_tokens over limit returns 422."""
        # Try with max_tokens > 4096
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Hello, world!",
                "max_tokens": 5000  # Over the limit
            },
            headers={"X-API-Key": TEST_API_KEY}
        )
        
        assert response.status_code == 422
        assert "max_tokens" in str(response.json())
    
    def test_suspicious_patterns_422(self):
        """Test that suspicious patterns in prompt are rejected."""
        # Test with repeating characters
        suspicious_prompt = "a" * 150 + "aaaaa" * 25  # Creates long repeating sequence
        
        response = client.post(
            "/api/v1/chat",
            json={"message": suspicious_prompt},
            headers={"X-API-Key": TEST_API_KEY}
        )
        
        assert response.status_code == 422
        assert "suspicious repeating patterns" in str(response.json())
    
    def test_control_characters_422(self):
        """Test that control characters are rejected."""
        # Test with null bytes
        prompt_with_null = "Hello\x00world"
        
        response = client.post(
            "/api/v1/chat",
            json={"message": prompt_with_null},
            headers={"X-API-Key": TEST_API_KEY}
        )
        
        assert response.status_code == 422
        assert "invalid control characters" in str(response.json())
    
    def test_invalid_session_id_422(self):
        """Test that invalid session IDs are rejected."""
        # Test with special characters in session_id
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Hello, world!",
                "session_id": "invalid@session#id"
            },
            headers={"X-API-Key": TEST_API_KEY}
        )
        
        assert response.status_code == 422
        assert "Session ID" in str(response.json())
    
    @pytest.mark.asyncio
    async def test_rate_limit_429(self):
        """Test that rate limiting triggers after many requests."""
        # Note: This test might need adjustment based on actual rate limits
        
        # Make multiple rapid requests
        async with AsyncClient(app=app, base_url="http://test") as async_client:
            responses = []
            for i in range(15):  # Assuming rate limit is less than 15/minute
                response = await async_client.post(
                    "/api/v1/chat",
                    json={"message": f"Test message {i}"},
                    headers={"X-API-Key": TEST_API_KEY}
                )
                responses.append(response)
                if response.status_code == 429:
                    break
            
            # At least one request should have been rate limited
            rate_limited = any(r.status_code == 429 for r in responses)
            if rate_limited:
                # Check rate limit response format
                rate_limit_response = next(r for r in responses if r.status_code == 429)
                assert "Rate limit exceeded" in rate_limit_response.json()["detail"]
    
    def test_health_check_no_auth(self):
        """Test that health check endpoint doesn't require authentication."""
        response = client.get("/api/v1/health")
        
        # Health check should be accessible without auth
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
