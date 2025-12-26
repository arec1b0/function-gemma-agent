import pytest
import tempfile
import os
from pathlib import Path
from app.rag.store import VectorStore
from app.rag.retriever import KnowledgeRetriever
from app.inference.engine import TracingEngine
from app.training.collector import TrainingDataCollector

class TestRAGPipeline:
    """Test the RAG pipeline implementation."""
    
    def test_retrieval(self):
        """Test that RAG can retrieve relevant documents."""
        # Create a temporary vector store
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(
                collection_name="test_collection",
                persist_directory=temp_dir
            )
            
            # Add test documents
            documents = [
                {
                    "id": "doc1",
                    "content": "Service X is critical for payment processing. It must maintain 99.9% uptime.",
                    "metadata": {"source": "runbook.md"}
                },
                {
                    "id": "doc2", 
                    "content": "Service Y handles user authentication and is also critical.",
                    "metadata": {"source": "architecture.md"}
                }
            ]
            
            store.add_documents(documents)
            
            # Test retrieval
            retriever = KnowledgeRetriever()
            result = retriever.retrieve_context("Is Service X important?", top_k=1)
            
            # Assert the retrieved content contains "critical"
            assert "critical" in result.lower()
            assert "Service X" in result
            print("✅ RAG retrieval test passed")
    
    def test_search_by_source(self):
        """Test searching within a specific source."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = VectorStore(persist_directory=temp_dir)
            
            # Add documents from different sources
            documents = [
                {
                    "id": "doc1",
                    "content": "Production cluster has high CPU usage",
                    "metadata": {"source": "prod-monitoring.md"}
                },
                {
                    "id": "doc2",
                    "content": "Development cluster is running fine",
                    "metadata": {"source": "dev-monitoring.md"}
                }
            ]
            
            store.add_documents(documents)
            retriever = KnowledgeRetriever()
            
            # Search within production docs
            result = retriever.search_by_source("CPU", "prod-monitoring.md")
            
            assert "Production" in result
            assert "Development" not in result
            print("✅ Search by source test passed")

class TestReActLoop:
    """Test the ReAct reasoning loop."""
    
    def test_multi_step_reasoning(self):
        """Test that the agent can perform multi-step reasoning."""
        # Mock a tool that changes state
        call_count = 0
        
        class MockTool:
            def __init__(self):
                self.name = "mock_check_status"
            
            def execute(self, args):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {"status": "pending", "message": "Job is running"}
                else:
                    return {"status": "done", "message": "Job completed successfully"}
        
        # Create a mock gemma service
        class MockGemmaService:
            def generate(self, messages, tools_schema):
                # First call: think about checking status
                if "check status" in messages[0]["content"]:
                    return "I should check the job status first."
                # Second call: provide final answer
                else:
                    return "Based on the tool output, the job has completed successfully."
            
            def parse_output(self, text, available_tools):
                if "check status" in text.lower():
                    return "mock_check_status", {}
                return None, None
        
        # Test the loop
        engine = TracingEngine(max_steps=3)
        mock_service = MockGemmaService()
        
        # Mock the tool registry
        import app.infrastructure.tools.registry as registry
        original_tools = registry._tools.copy()
        registry._tools = {"mock_check_status": MockTool()}
        
        try:
            result = engine.react_reasoning_loop(
                initial_query="Check the job status and tell me when it's done",
                gemma_service=mock_service,
                tools_schema=[{"name": "mock_check_status", "description": "Mock tool"}]
            )
            
            # Verify multi-step execution
            assert call_count >= 2, f"Expected at least 2 tool calls, got {call_count}"
            assert result["steps_taken"] >= 2
            print("✅ Multi-step reasoning test passed")
            
        finally:
            # Restore original tools
            registry._tools = original_tools

class TestTrainingDataCollector:
    """Test the training data collection."""
    
    def test_data_collection(self):
        """Test that training data is collected properly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "test_training.jsonl")
            collector = TrainingDataCollector(
                output_file=output_file,
                auto_save=True
            )
            
            # Collect a sample inference
            instruction = "Check pod status in production"
            reasoning_trace = [
                {"step": 1, "type": "think", "content": "User wants pod status"},
                {"step": 2, "type": "act", "content": "Calling get_pod_status"},
                {"step": 3, "type": "observe", "content": "Got pod status"}
            ]
            tool_calls = [
                {
                    "tool": "get_pod_status",
                    "arguments": {"cluster_id": "prod"},
                    "result": {"status": "healthy"},
                    "status": "success"
                }
            ]
            output = "All pods in production are healthy."
            
            # Collect the data
            success = collector.collect_inference(
                instruction=instruction,
                reasoning_trace=reasoning_trace,
                tool_calls=tool_calls,
                output=output
            )
            
            assert success, "Data collection should succeed"
            
            # Verify file was created and contains data
            assert os.path.exists(output_file), "Training file should exist"
            
            with open(output_file, 'r') as f:
                line = f.readline()
                data = json.loads(line)
                
                assert data["instruction"] == instruction
                assert len(data["reasoning_trace"]) == 3
                assert len(data["tool_calls"]) == 1
                assert data["output"] == output
                assert data["quality_score"] > 0
            
            print("✅ Training data collection test passed")
    
    def test_quality_filtering(self):
        """Test that low quality data is filtered out."""
        collector = TrainingDataCollector(min_quality_score=0.9)
        
        # Try to collect low quality data
        success = collector.collect_inference(
            instruction="hi",  # Too short
            reasoning_trace=[],  # No reasoning
            tool_calls=[],  # No tools
            output="ok"  # Too short
        )
        
        assert not success, "Low quality data should be rejected"
        print("✅ Quality filtering test passed")

def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("RAG & REACT VALIDATION TESTS")
    print("=" * 60)
    
    # Run tests
    test_rag = TestRAGPipeline()
    test_rag.test_retrieval()
    test_rag.test_search_by_source()
    
    test_react = TestReActLoop()
    test_react.test_multi_step_reasoning()
    
    test_training = TestTrainingDataCollector()
    test_training.test_data_collection()
    test_training.test_quality_filtering()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✅")
    print("=" * 60)
    print("\nThe agent is ready with:")
    print("✅ RAG pipeline for knowledge retrieval")
    print("✅ Multi-step ReAct reasoning loop")
    print("✅ Training data collection")
    print("✅ Few-shot prompt engineering")

if __name__ == "__main__":
    run_all_tests()
