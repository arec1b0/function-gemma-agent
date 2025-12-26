from typing import Dict, Any
from kubernetes import client, config
from app.infrastructure.tools.base import BaseTool
from app.core.logger import log

class ClusterStatusTool(BaseTool):
    """
    Tool to check Kubernetes cluster status using the official Python client.
    """
    
    @property
    def name(self) -> str:
        return "get_cluster_status"

    @property
    def description(self) -> str:
        return "Get the status of a Kubernetes cluster and node load."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string", 
                    "description": "The ID of the cluster to check. Common values: 'prod', 'dev', 'staging'. If user says 'production', use 'prod'."
                },
                "verbose": {
                    "type": "boolean", 
                    "description": "Set to true if user wants detailed logs."
                }
            },
            "required": ["cluster_id"]
        }

    def execute(self, cluster_id: str, verbose: bool = False) -> Dict[str, Any]:
        log.info(f"Executing ClusterStatusTool for cluster: {cluster_id}")
        
        try:
            # Load local kubeconfig
            # In a container, you would use config.load_incluster_config()
            try:
                config.load_kube_config()
            except config.ConfigException:
                # Fallback for inside cluster or if no config exists
                return {"error": "Could not load kubeconfig. Are you connected to a cluster?"}

            v1 = client.CoreV1Api()
            
            # Fetch Nodes
            nodes = v1.list_node()
            total_nodes = len(nodes.items)
            
            ready_nodes = 0
            cpu_allocatable = 0
            memory_allocatable = 0
            
            node_details = []

            for node in nodes.items:
                # Check conditions
                conditions = node.status.conditions
                is_ready = False
                for c in conditions:
                    if c.type == "Ready" and c.status == "True":
                        is_ready = True
                        ready_nodes += 1
                        break
                
                # Aggregate resources (simplified parsing)
                if node.status.allocatable:
                    cpu = node.status.allocatable.get("cpu", "0")
                    memory = node.status.allocatable.get("memory", "0")
                    # Note: Parsing '1234Ki' or '2' requires specific logic, simplified here for logging
                    
                if verbose:
                    node_details.append({
                        "name": node.metadata.name,
                        "ready": is_ready,
                        "cpu": cpu,
                        "memory": memory
                    })

            status = "HEALTHY" if ready_nodes == total_nodes and total_nodes > 0 else "DEGRADED"

            return {
                "cluster_id": cluster_id,
                "status": status,
                "nodes_total": total_nodes,
                "nodes_active": ready_nodes,
                "nodes_not_ready": total_nodes - ready_nodes,
                "details": node_details if verbose else "Run with verbose=True for node details"
            }

        except Exception as e:
            log.error(f"Kubernetes API Error: {e}")
            return {"error": str(e)}