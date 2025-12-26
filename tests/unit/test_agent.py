import pytest
from app.infrastructure.ml.inference import GemmaService
from app.infrastructure.tools.registry import registry

def test_parse_output_function_call():
    """
    Test if the parsing logic correctly extracts function calls
    from the specific FunctionGemma token format.
    """
    service = GemmaService()
    # Mocking the loader since we only test the static parsing method
    service.loader = None 
    
    # Valid JSON format expected by our parser
    valid_text = '<start_function_call>call:get_cluster_status{"cluster_id": "prod"}<end_function_call>'
    
    func_name, args = service.parse_output(valid_text)
    
    assert func_name == "get_cluster_status"
    assert args == {"cluster_id": "prod"}

def test_parse_output_no_call():
    """Test parsing of normal text."""
    service = GemmaService()
    text = "Just a normal conversation."
    func_name, args = service.parse_output(text)
    assert func_name is None
    assert args is None

def test_tool_registry_execution():
    """Test if the registry correctly finds and executes the tool."""
    tool_name = "get_cluster_status"
    args = {"cluster_id": "dev"}
    
    result = registry.execute_tool(tool_name, args)
    
    assert result["cluster_id"] == "dev"
    assert "cpu_load" in result