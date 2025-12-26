def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_chat_endpoint_natural_language(client, mock_gemma_service):
    """
    Test a standard chat interaction without tool calls.
    """
    mock_gemma_service.generate.return_value = "Hello! How can I help you?"
    mock_gemma_service.parse_output.return_value = (None, None)
    
    response = client.post("/api/v1/chat", json={"message": "Hi"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Hello! How can I help you?"
    assert len(data["actions_taken"]) == 0

def test_chat_endpoint_with_tool(client, mock_gemma_service):
    """
    Test the full flow when the model triggers a tool.
    """
    # 1. Setup Mock to return a tool call
    mock_gemma_service.generate.return_value = \
        '<start_function_call>call:get_cluster_status{"cluster_id": "prod"}<end_function_call>'
    
    # 2. Setup Mock parser to return the extracted data
    mock_gemma_service.parse_output.return_value = (
        "get_cluster_status", 
        {"cluster_id": "prod"}
    )
    
    # 3. Call API
    response = client.post("/api/v1/chat", json={"message": "Check prod status"})
    
    # 4. Assertions
    assert response.status_code == 200
    data = response.json()
    
    # The response should contain the "Action: ..." log string
    assert "Action: get_cluster_status" in data["response"]
    assert "HEALTHY" in data["response"]
    
    # Check structured logs
    assert len(data["actions_taken"]) == 1
    assert data["actions_taken"][0]["tool"] == "get_cluster_status"
    assert data["actions_taken"][0]["status"] == "success"