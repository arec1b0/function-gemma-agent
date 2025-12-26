from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    """
    Abstract Base Class for all tools.
    Enforces a strict contract for tool definition and execution.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the function (e.g., 'get_cluster_status')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does for the LLM."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema defining the parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        The actual implementation of the tool.
        Must return a serializable dictionary.
        """
        pass

    def to_schema(self) -> Dict[str, Any]:
        """
        Returns the schema formatted for the tokenizer (OpenAI Standard).
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }