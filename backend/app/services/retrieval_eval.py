"""
Precision@k evaluation for incident-similarity retrieval, run against an
isolated, disposable ChromaDB collection seeded only with the curated real
incident set + labeled queries (app/data/real_incidents.py and
app/data/incident_eval_queries.py) - never the live production collection,
so results are reproducible and unaffected by whatever a team has added.

This treats "does the embedding search actually find the right incident"
as a measurable, regression-testable property instead of an assumption -
see tests/test_retrieval_eval.py, which asserts a real minimum bar rather
than just printing a number.
"""

import chromadb
from typing import Any, Dict, List

from app.data.incident_eval_queries import EVAL_QUERIES
from app.data.real_incidents import REAL_INCIDENTS
from app.services.incident_similarity import query_incidents

EVAL_COLLECTION_NAME = "incidents_eval"


def build_eval_collection():
    """A fresh in-memory ChromaDB collection containing only the 15 curated
    real incidents - isolated from the live persistent 'incidents'
    collection (which may also contain team-added data) and from any state
    left over by a previous evaluation run."""
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(name=EVAL_COLLECTION_NAME)
    collection.add(
        documents=[inc["description"] for inc in REAL_INCIDENTS],
        metadatas=[
            {"incident_id": inc["incident_id"], "date": inc["date"], "severity": inc["severity"], "source": inc["source"]}
            for inc in REAL_INCIDENTS
        ],
        ids=[inc["incident_id"] for inc in REAL_INCIDENTS],
    )
    return collection


def precision_at_k(collection, k: int, queries: List[Dict[str, Any]] = EVAL_QUERIES) -> Dict[str, Any]:
    """
    For each labeled query, retrieves the top-k incidents and checks
    whether the expected incident_id is among them - the standard
    precision@k definition for a retrieval task with exactly one relevant
    document per query (precision@k = 1/k if found in the top k, else 0;
    averaged across all queries gives mean precision@k).
    """
    per_query = []
    for q in queries:
        query_text = f"{q['title']} {q['description']}"
        matches = query_incidents(collection, query_text, n_results=k)
        retrieved_ids = [m["incident_id"] for m in matches]
        hit = q["expected_incident_id"] in retrieved_ids
        rank = retrieved_ids.index(q["expected_incident_id"]) + 1 if hit else None
        per_query.append({
            "expected_incident_id": q["expected_incident_id"],
            "title": q["title"],
            "retrieved_ids": retrieved_ids,
            "hit": hit,
            "rank": rank,
            "precision": (1.0 / k) if hit else 0.0,
        })

    mean_precision = sum(r["precision"] for r in per_query) / len(per_query) if per_query else 0.0
    hit_rate = sum(1 for r in per_query if r["hit"]) / len(per_query) if per_query else 0.0

    return {
        "k": k,
        "mean_precision_at_k": mean_precision,
        "hit_rate_at_k": hit_rate,  # fraction of queries where the expected incident appeared anywhere in the top k
        "per_query": per_query,
    }


def run_evaluation(ks: List[int] = (1, 3, 5)) -> Dict[int, Dict[str, Any]]:
    """Convenience entry point: builds one eval collection and reports
    precision@k for each k in `ks` against it."""
    collection = build_eval_collection()
    return {k: precision_at_k(collection, k) for k in ks}


if __name__ == "__main__":
    results = run_evaluation()
    for k, result in results.items():
        print(f"precision@{k}: {result['mean_precision_at_k']:.3f}   hit_rate@{k}: {result['hit_rate_at_k']:.3f}")
        for r in result["per_query"]:
            status = f"hit (rank {r['rank']})" if r["hit"] else "MISS"
            print(f"  [{status:12}] {r['expected_incident_id']}: {r['title']!r} -> {r['retrieved_ids']}")
