import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Dict, Any, List
from app.core.config import settings
import os

def get_chroma_client():
    os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)

def init_mock_incidents():
    # Initialize some mock incidents if collection is empty
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")
    
    if collection.count() == 0:
        collection.add(
            documents=[
                "Database connection timeout during peak load due to unoptimized queries in the payment module",
                "Authentication bypass vulnerability caused by missing null check in refresh token flow",
                "Memory leak in the worker service when processing large files resulting in OOM kills"
            ],
            metadatas=[
                {"incident_id": "INC-001", "date": "2025-01-15", "severity": "High"},
                {"incident_id": "INC-002", "date": "2025-03-22", "severity": "Critical"},
                {"incident_id": "INC-003", "date": "2025-05-10", "severity": "High"}
            ],
            ids=["INC-001", "INC-002", "INC-003"]
        )

# Initialize on startup
init_mock_incidents()

def find_similar_incidents(pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")
    
    query_text = f"{pr_data.get('title', '')} {pr_data.get('description', '')}"
    if not query_text.strip():
        query_text = "code changes"
        
    results = collection.query(
        query_texts=[query_text],
        n_results=3
    )
    
    incidents = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            # ChromaDB distances (lower is closer for L2). We convert to a similarity score out of 100
            distance = results["distances"][0][i] if "distances" in results and results["distances"] else 1.0
            score = max(0, min(100, int((2.0 - distance) * 50)))
            
            if score >= 60:
                incidents.append({
                    "similarity_score": score,
                    "matching_incident": doc,
                    "explanation": f"Similar to past incident {meta.get('incident_id')} with severity {meta.get('severity')}"
                })
            
    if not incidents:
        return [{
            "similarity_score": 0,
            "matching_incident": "No relevant incidents found",
            "explanation": "Did not find any incidents matching the PR context with high confidence."
        }]

    return incidents
