from app.services.incident_similarity import find_similar_incidents, seed_reference_incidents
from app.services.retrieval_eval import EVAL_QUERIES, build_eval_collection, precision_at_k


def test_eval_set_covers_every_real_incident_exactly_once():
    # Sanity check on the labeled set itself, not the retrieval system -
    # catches a typo'd or duplicated expected_incident_id before it can
    # silently make the precision numbers below meaningless.
    from app.data.real_incidents import REAL_INCIDENTS

    real_ids = {inc["incident_id"] for inc in REAL_INCIDENTS}
    query_ids = [q["expected_incident_id"] for q in EVAL_QUERIES]

    assert len(query_ids) == len(set(query_ids)), "duplicate expected_incident_id in EVAL_QUERIES"
    assert set(query_ids) == real_ids, "EVAL_QUERIES doesn't cover exactly the incidents in REAL_INCIDENTS"


def test_precision_at_1_meets_a_real_minimum_bar():
    # Empirically measured at 0.933 (14/15 exact top-1 hits) against the
    # real embedding model - asserting a bar below that, not at it, so a
    # minor embedding-model version bump doesn't make this flaky, while
    # still catching an actual regression in retrieval quality.
    collection = build_eval_collection()
    result = precision_at_k(collection, k=1)
    assert result["mean_precision_at_k"] >= 0.8, result["per_query"]


def test_hit_rate_at_3_is_high():
    # Empirically measured at 1.0 (every incident found somewhere in its
    # own top-3) - the one query that doesn't rank its exact incident #1
    # (REAL-009, a rare-config-value bug) still finds it at rank 2, beaten
    # by REAL-015 (a different config-scope bug), a legitimate semantic
    # near-miss rather than a retrieval failure.
    collection = build_eval_collection()
    result = precision_at_k(collection, k=3)
    assert result["hit_rate_at_k"] >= 0.9, result["per_query"]


def test_every_query_at_least_finds_its_incident_within_top_5():
    collection = build_eval_collection()
    result = precision_at_k(collection, k=5)
    misses = [r for r in result["per_query"] if not r["hit"]]
    assert misses == [], f"queries that never retrieved their expected incident in the top 5: {misses}"


def test_find_similar_incidents_actually_surfaces_most_genuine_matches_to_the_user():
    """
    Ranking correctly (the tests above) isn't the same as the user ever
    seeing the match - find_similar_incidents() also applies
    MIN_DISPLAY_SCORE, a separate product-facing cutoff. This was caught
    empirically while building this eval set: the old cutoff of 60 (never
    revisited since the 3-stub-example era) sat inside the score range
    genuine matches actually land in for realistic PR-length text, so 12 of
    these 15 correct top-1 matches were being silently hidden even though
    retrieval had ranked them correctly. Runs against the real, live
    seeded collection (not the isolated eval one) to test the actual
    end-to-end behavior a user would see.
    """
    seed_reference_incidents()

    shown = 0
    for q in EVAL_QUERIES:
        results = find_similar_incidents({"title": q["title"], "description": q["description"]})
        if results[0]["similarity_score"] > 0 and q["expected_incident_id"] in results[0]["explanation"]:
            shown += 1

    assert shown >= 12, f"only {shown}/{len(EVAL_QUERIES)} genuine matches were actually surfaced to the user"
