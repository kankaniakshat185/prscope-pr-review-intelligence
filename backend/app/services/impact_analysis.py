import networkx as nx
from typing import Dict, Any

def analyze_impact(pr_data: Dict[str, Any]) -> Dict[str, Any]:
    files = pr_data.get("files", [])
    
    graph = nx.DiGraph()
    affected_modules = set()
    affected_services = set()
    
    # We simulate a dependency graph based on directory structures
    for f in files:
        filename = f.get("filename", "")
        parts = filename.split('/')
        if len(parts) > 1:
            service = parts[0]
            module = parts[-2] if len(parts) > 2 else parts[-1]
            affected_services.add(service)
            affected_modules.add(module)
            graph.add_edge(service, module)
            graph.add_edge(module, filename)
        else:
            affected_modules.add(filename)
            graph.add_edge("root", filename)
            
    # Serialize graph for the frontend
    nodes = [{"id": node} for node in graph.nodes()]
    links = [{"source": u, "target": v} for u, v in graph.edges()]
    
    return {
        "affected_modules": list(affected_modules),
        "affected_services": list(affected_services),
        "graph_data": {
            "nodes": nodes,
            "links": links
        }
    }
