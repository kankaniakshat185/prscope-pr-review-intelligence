import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.data.real_incidents import REAL_INCIDENTS
from datetime import datetime
import os
import uuid

def get_chroma_client():
    os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)

# IDs of the old 3 hand-written placeholder incidents this dataset
# replaces - removed on startup so an existing local/deployed instance
# doesn't keep matching against them forever alongside the real ones.
_OLD_STUB_IDS = ["INC-001", "INC-002", "INC-003"]

# Sentinel "repository" tag for the seeded reference incidents - they're not
# scoped to any one repo, unlike team-reported ones (see add_team_incident),
# so find_similar_incidents() treats this value as "visible from every repo"
# alongside the querying PR's own repository.
GLOBAL_REPOSITORY_TAG = "__global__"


def seed_reference_incidents():
    """
    Seeds the real, sourced incidents from app/data/real_incidents.py so
    find_similar_incidents() has real-world data to match against, not just
    whatever a team has gotten around to reporting themselves. Idempotent
    via upsert (not a blunt "only if the collection is totally empty"
    check, and not add-only-if-missing either) - re-running this always
    brings every reference incident's metadata (including the global
    repository tag below) up to date, even for one seeded by an older
    version of this function on an already-running instance. Called from
    main.py's startup event, not at import time, so importing this module
    never has side effects (creating a Chroma client, writing to disk) on
    its own.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")

    stale = collection.get(ids=_OLD_STUB_IDS)
    if stale and stale.get("ids"):
        collection.delete(ids=stale["ids"])

    collection.upsert(
        documents=[inc["description"] for inc in REAL_INCIDENTS],
        metadatas=[
            {
                "incident_id": inc["incident_id"],
                "date": inc["date"],
                "severity": inc["severity"],
                "source": inc["source"],
                "repository": GLOBAL_REPOSITORY_TAG,
            }
            for inc in REAL_INCIDENTS
        ],
        ids=[inc["incident_id"] for inc in REAL_INCIDENTS],
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


def _distance_to_score(distance: float) -> int:
    # ChromaDB distances (lower is closer for L2). Converted to a similarity
    # score out of 100 for display purposes.
    return max(0, min(100, int((2.0 - distance) * 50)))


# Empirically calibrated, not guessed: measured against the 15-query eval
# set in app/data/incident_eval_queries.py (see retrieval_eval.py). Genuine
# unrelated queries ("fix typo in changelog", "bump lodash version") scored
# 6-32; genuine correct top-1 matches on realistic PR-length text scored
# 41-80. The old value of 60 - never revisited since the 3-stub-example
# era - sat inside the range where real, correct matches actually land,
# silently hiding 12 of 15 genuine matches in that eval set. 35 sits in the
# empirical gap between the two distributions.
MIN_DISPLAY_SCORE = 35


def query_incidents(
    collection, query_text: str, n_results: int = 3, repository: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    The actual retrieval step, factored out of find_similar_incidents so
    retrieval_eval.py can run it against an isolated, disposable collection
    (a clean evaluation corpus) instead of the live production one, and get
    back ranked (incident_id, score, doc, meta) results rather than the
    already-thresholded/formatted response shape find_similar_incidents
    returns.

    `repository`, when given, restricts matches to the global reference
    incidents (GLOBAL_REPOSITORY_TAG) plus team incidents reported against
    that specific repo - otherwise a team-reported incident from one repo
    could surface as a "similar incident" on an unrelated repo's PR, which
    is both noise and a quiet cross-repo information leak. retrieval_eval.py
    passes None, since its evaluation corpus has no repository metadata at
    all.
    """
    where = None
    if repository:
        where = {"$or": [{"repository": GLOBAL_REPOSITORY_TAG}, {"repository": repository}]}
    results = collection.query(query_texts=[query_text], n_results=n_results, where=where)

    matches = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i] if "distances" in results and results["distances"] else 1.0
            matches.append({
                "incident_id": meta.get("incident_id"),
                "score": _distance_to_score(distance),
                "document": doc,
                "metadata": meta,
            })
    return matches


def find_similar_incidents(pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")

    query_text = f"{pr_data.get('title', '')} {pr_data.get('description', '')}"
    if not query_text.strip():
        query_text = "code changes"

    owner, repo = pr_data.get("owner"), pr_data.get("repo")
    repository = f"{owner}/{repo}" if owner and repo else None
    matches = query_incidents(collection, query_text, n_results=3, repository=repository)

    incidents = []
    for match in matches:
        if match["score"] < MIN_DISPLAY_SCORE:
            continue
        meta = match["metadata"]
        reported_by = meta.get("reported_by")
        source = f"team-reported by {reported_by}" if reported_by else f"reference: {meta.get('source', 'n/a')}"
        incidents.append({
            "similarity_score": match["score"],
            "matching_incident": match["document"],
            "explanation": f"Similar to past incident {match['incident_id']} ({source}) with severity {meta.get('severity')}"
        })

    if not incidents:
        return [{
            "similarity_score": 0,
            "matching_incident": "No relevant incidents found",
            "explanation": "Did not find any incidents matching the PR context with high confidence."
        }]

    return incidents
