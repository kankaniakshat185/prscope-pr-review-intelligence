import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Dict, Any, List, Optional
from app.core.config import settings
from datetime import datetime
import os
import uuid

def get_chroma_client():
    os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)

def init_mock_incidents():
    """
    STUB: seeds exactly three hand-written example incidents so
    find_similar_incidents() has something to match against. This is not a
    real incident database or an ingestion pipeline - matches will only ever
    be against these three canned entries until real incident data is wired
    up. Called from main.py's startup event, not at import time, so that
    importing this module never has side effects (creating a Chroma client
    and writing to disk) on its own.
    """
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

def add_team_incident(repository: str, description: str, severity: str, reported_by: Optional[str] = None) -> Dict[str, Any]:
    """
    Lets a team record a real incident from their own repository, instead of
    similarity matching being limited to the 3 hand-written stub examples
    forever. Stored in the same ChromaDB collection as those seeded
    examples (find_similar_incidents' unfiltered query picks it up
    immediately, no separate wiring needed) - "repository" and
    "reported_by" are just additional metadata used to attribute it and to
    list a team's own incidents back to them.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")

    incident_id = f"TEAM-{uuid.uuid4().hex[:10]}"
    date = datetime.utcnow().strftime("%Y-%m-%d")
    collection.add(
        documents=[description],
        metadatas=[{
            "incident_id": incident_id,
            "date": date,
            "severity": severity,
            "repository": repository,
            "reported_by": reported_by or "",
        }],
        ids=[incident_id],
    )
    return {
        "incident_id": incident_id,
        "description": description,
        "severity": severity,
        "repository": repository,
        "date": date,
        "reported_by": reported_by,
    }


def list_team_incidents(repository: str) -> List[Dict[str, Any]]:
    """Incidents a team added themselves for this specific repository (not
    the global seeded examples, which have no "repository" metadata to
    match against)."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")
    results = collection.get(where={"repository": repository})

    incidents = []
    ids = results.get("ids") or []
    for i, incident_id in enumerate(ids):
        meta = results["metadatas"][i]
        incidents.append({
            "incident_id": incident_id,
            "description": results["documents"][i],
            "severity": meta.get("severity", "Medium"),
            "repository": meta.get("repository", repository),
            "date": meta.get("date", ""),
            "reported_by": meta.get("reported_by") or None,
        })
    return incidents


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
                reported_by = meta.get("reported_by")
                source = f"team-reported by {reported_by}" if reported_by else "reference example"
                incidents.append({
                    "similarity_score": score,
                    "matching_incident": doc,
                    "explanation": f"Similar to past incident {meta.get('incident_id')} ({source}) with severity {meta.get('severity')}"
                })
            
    if not incidents:
        return [{
            "similarity_score": 0,
            "matching_incident": "No relevant incidents found",
            "explanation": "Did not find any incidents matching the PR context with high confidence."
        }]

    return incidents
