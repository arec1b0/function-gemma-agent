# Tutorial 01: Adding a New Tool to the Agent

## Overview

This tutorial walks you through creating a custom tool for the FunctionGemma Agent. Tools allow the agent to interact with external systems, APIs, and perform specific actions beyond text generation.

## Prerequisites

- Python 3.10+
- FunctionGemma Agent development environment
- Understanding of Python classes and async/await
- Basic knowledge of REST APIs

## What is a Tool?

A tool in the FunctionGemma Agent is a Python class that:
- Inherits from `BaseTool`
- Defines a name, description, and parameters
- Implements an `execute()` method
- Returns structured results

Tools are automatically discovered and can be called by the agent during reasoning.

## Step 1: Create the Tool Class

Create a new file `app/infrastructure/tools/weather_tool.py`:

```python
from typing import Dict, Any
import httpx
from app.infrastructure.tools.base import BaseTool
from app.core.logger import log

class WeatherTool(BaseTool):
    """
    Tool for fetching current weather information for a given city.
    """
    
    @property
    def name(self) -> str:
        return "get_weather"
    
    @property
    def description(self) -> str:
        return "Get the current weather information for a specified city"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The name of the city to get weather for"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "description": "Units for temperature (metric for Celsius, imperial for Fahrenheit)",
                    "default": "metric"
                }
            },
            "required": ["city"]
        }
    
    async def execute(self, city: str, units: str = "metric") -> Dict[str, Any]:
        """
        Execute the weather tool.
        
        Args:
            city: The city name
            units: Temperature units (metric/imperial)
            
        Returns:
            Dictionary with weather information
        """
        try:
            # Use OpenWeatherMap API (you'll need an API key)
            api_key = "your-api-key-here"  # In production, get from environment
            base_url = "https://api.openweathermap.org/data/2.5/weather"
            
            params = {
                "q": city,
                "appid": api_key,
                "units": units
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # Extract relevant information
                result = {
                    "city": data["name"],
                    "country": data["sys"]["country"],
                    "temperature": data["main"]["temp"],
                    "feels_like": data["main"]["feels_like"],
                    "humidity": data["main"]["humidity"],
                    "description": data["weather"][0]["description"],
                    "units": units
                }
                
                log.info(f"Weather retrieved for {city}: {data['main']['temp']}°")
                return result
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": f"City '{city}' not found"}
            return {"error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            log.error(f"Weather tool error: {str(e)}")
            return {"error": f"Failed to fetch weather: {str(e)}"}
```

## Step 2: Register the Tool

Update `app/infrastructure/tools/registry.py` to include your new tool:

```python
from app.infrastructure.tools.base import BaseTool
from app.infrastructure.tools.k8s_client import ClusterStatusTool
from app.infrastructure.tools.weather_tool import WeatherTool  # Add this import
from app.core.exceptions import ToolExecutionError

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Register default tools."""
        self.register(ClusterStatusTool())
        self.register(WeatherTool())  # Register the weather tool
```

## Step 3: Add Configuration (Optional)

For production tools, add configuration to `.env.example`:

```bash
# Weather Tool Configuration
WEATHER_API_KEY=your-openweather-api-key
WEATHER_API_URL=https://api.openweathermap.org/data/2.5/weather
```

Update the tool to use environment variables:

```python
import os
from typing import Dict, Any
import httpx
from app.infrastructure.tools.base import BaseTool
from app.core.logger import log

class WeatherTool(BaseTool):
    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_KEY")
        self.base_url = os.getenv("WEATHER_API_URL", "https://api.openweathermap.org/data/2.5/weather")
    
    # ... rest of the class remains the same ...
    
    async def execute(self, city: str, units: str = "metric") -> Dict[str, Any]:
        if not self.api_key:
            return {"error": "Weather API key not configured"}
        
        try:
            params = {
                "q": city,
                "appid": self.api_key,
                "units": units
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params)
                # ... rest of the method
```

## Step 4: Write Tests

Create `tests/unit/test_weather_tool.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.infrastructure.tools.weather_tool import WeatherTool

@pytest.fixture
def weather_tool():
    return WeatherTool()

@pytest.mark.asyncio
async def test_weather_tool_success(weather_tool):
    """Test successful weather retrieval."""
    mock_response = {
        "name": "London",
        "sys": {"country": "GB"},
        "main": {
            "temp": 15.5,
            "feels_like": 14.2,
            "humidity": 65
        },
        "weather": [{"description": "partly cloudy"}]
    }
    
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.return_value = AsyncMock()
        mock_get.return_value.raise_for_status = AsyncMock()
        mock_get.return_value.json = AsyncMock(return_value=mock_response)
        
        result = await weather_tool.execute("London", "metric")
        
        assert result["city"] == "London"
        assert result["temperature"] == 15.5
        assert result["units"] == "metric"

@pytest.mark.asyncio
async def test_weather_tool_city_not_found(weather_tool):
    """Test handling of non-existent city."""
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.return_value = AsyncMock()
        mock_get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=AsyncMock(), response=AsyncMock(status_code=404)
        )
        
        result = await weather_tool.execute("NonExistentCity")
        
        assert "error" in result
        assert "not found" in result["error"]

def test_tool_schema(weather_tool):
    """Test tool schema generation."""
    schema = weather_tool.to_schema()
    
    assert schema["name"] == "get_weather"
    assert "city" in schema["parameters"]["properties"]
    assert "units" in schema["parameters"]["properties"]
    assert "city" in schema["parameters"]["required"]
```

## Step 5: Test the Tool

Run the tests:

```bash
pytest tests/unit/test_weather_tool.py -v
```

Test the tool manually:

```python
# In a Python shell
from app.infrastructure.tools.weather_tool import WeatherTool
import asyncio

tool = WeatherTool()
result = asyncio.run(tool.execute("New York"))
print(result)
```

## Step 6: Use in Agent

Now the agent can use the weather tool automatically:

```python
from app.domain.agent import AgentService
from app.domain.models import AgentRequest

agent = AgentService()
request = AgentRequest(query="What's the weather like in Tokyo?")
response = await agent.process_request(request)

print(response.response)
# The agent will call the weather tool and include the results in its response
```

## Advanced Features

### 1. Tool with Multiple Methods

```python
class DatabaseTool(BaseTool):
    @property
    def name(self) -> str:
        return "database_query"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["select", "insert", "update", "delete"],
                    "description": "Database action to perform"
                },
                "table": {"type": "string", "description": "Table name"},
                "data": {"type": "object", "description": "Data for insert/update"},
                "condition": {"type": "string", "description": "WHERE clause for select/update/delete"}
            },
            "required": ["action", "table"]
        }
    
    async def execute(self, action: str, table: str, data: Dict = None, condition: str = None):
        if action == "select":
            return await self._select(table, condition)
        elif action == "insert":
            return await self._insert(table, data)
        # ... other methods
```

### 2. Streaming Tool

```python
class StreamTool(BaseTool):
    async def execute_stream(self, query: str):
        """Yield results as they're available."""
        for i in range(5):
            yield {"step": i, "data": f"Processing {query}..."}
            await asyncio.sleep(0.5)
```

### 3. Tool with Side Effects

```python
class NotificationTool(BaseTool):
    async def execute(self, message: str, channel: str = "default"):
        """Send notification and track metrics."""
        # Send notification
        await self._send_notification(message, channel)
        
        # Track usage
        record_tool_usage("notification", {"channel": channel})
        
        return {"status": "sent", "channel": channel}
```

## Best Practices

1. **Error Handling**: Always handle exceptions gracefully and return error information
2. **Logging**: Log important events and errors for debugging
3. **Async**: Use async/await for I/O operations
4. **Validation**: Validate input parameters before processing
5. **Documentation**: Provide clear descriptions for parameters
6. **Testing**: Write comprehensive tests for all scenarios
7. **Security**: Sanitize inputs and handle sensitive data properly
8. **Rate Limiting**: Implement rate limiting for external API calls

## Common Patterns

### API Client Tool

```python
class APITool(BaseTool):
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=os.getenv("API_BASE_URL"),
            headers={"Authorization": f"Bearer {os.getenv('API_TOKEN')}"}
        )
    
    async def execute(self, endpoint: str, method: str = "GET", data: Dict = None):
        if method.upper() == "GET":
            response = await self.client.get(endpoint)
        elif method.upper() == "POST":
            response = await self.client.post(endpoint, json=data)
        
        return response.json()
```

### File Operations Tool

```python
class FileTool(BaseTool):
    async def execute(self, operation: str, path: str, content: str = None):
        if operation == "read":
            with open(path, 'r') as f:
                return {"content": f.read()}
        elif operation == "write":
            with open(path, 'w') as f:
                f.write(content)
            return {"status": "success", "path": path}
```

## Troubleshooting

### Tool Not Showing Up

1. Check if the tool is registered in `registry.py`
2. Verify the import statement is correct
3. Restart the application after adding the tool

### Tool Execution Fails

1. Check the application logs for error messages
2. Verify all required environment variables are set
3. Test the tool independently of the agent

### Performance Issues

1. Use async/await for all I/O operations
2. Implement caching for frequently accessed data
3. Consider connection pooling for API calls

## Next Steps

- Add more complex tools with multiple methods
- Implement tool composition (tools that call other tools)
- Create tool categories and permissions
- Add tool usage analytics and monitoring

## Related Documentation

- [Tool Base Class Reference](../api/tools.md)
- [Testing Guidelines](../testing/README.md)
- [Configuration Guide](../configuration.md)

---

**Tutorial Completed!** You've successfully created and integrated a custom tool into the FunctionGemma Agent.
