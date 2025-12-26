from typing import Dict, List, Type, Any  # Added 'Any' here
from app.domain.interfaces.tools import ToolRegistryProtocol
from app.infrastructure.tools.base import BaseTool
from app.infrastructure.tools.k8s_client import ClusterStatusTool
from app.core.exceptions import ToolExecutionError

class ToolRegistry(ToolRegistryProtocol):
    """
    Singleton-like registry to manage available tools.
    """
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Register default tools."""
        self.register(ClusterStatusTool())

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Returns schemas for all registered tools."""
        return [tool.to_schema() for tool in self._tools.values()]

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if not tool:
            raise ToolExecutionError(f"Tool '{name}' not found in registry.")
        
        try:
            return tool.execute(**arguments)
        except Exception as e:
            raise ToolExecutionError(f"Error executing '{name}': {str(e)}")

# Global instance
registry = ToolRegistry()