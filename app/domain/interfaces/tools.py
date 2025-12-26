from abc import ABC, abstractmethod
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.infrastructure.tools.base import BaseTool

class ToolRegistryProtocol(ABC):
    """
    Abstract interface for Tool Registry.
    Defines the contract for managing and executing tools.
    """
    
    @abstractmethod
    def get_tool(self, name: str) -> 'BaseTool':
        """
        Retrieve a tool by name.
        
        Args:
            name: The name of the tool to retrieve
            
        Returns:
            The tool instance if found, None otherwise
        """
        pass
    
    @abstractmethod
    def list_tools(self) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of tool names
        """
        pass
    
    @abstractmethod
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """
        Get schemas for all registered tools.
        
        Returns:
            List of tool schemas
        """
        pass
    
    @abstractmethod
    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given arguments.
        
        Args:
            name: The name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool
            
        Returns:
            Result of tool execution
            
        Raises:
            ToolExecutionError: If tool is not found or execution fails
        """
        pass
