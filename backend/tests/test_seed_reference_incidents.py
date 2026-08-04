from app.data.real_incidents import REAL_INCIDENTS
from app.services.incident_similarity import _OLD_STUB_IDS, get_chroma_client, seed_reference_incidents

ALL_REAL_IDS = [inc["incident_id"] for inc in REAL_INCIDENTS]


def test_seeding_removes_the_old_placeholder_stub_incidents():
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")

    # Simulate a pre-existing deployment that still has the old 3 stub
    # examples this dataset replaces.
    collection.add(
        documents=["stub description"] * len(_OLD_STUB_IDS),
        metadatas=[{"severity": "High"}] * len(_OLD_STUB_IDS),
        ids=_OLD_STUB_IDS,
    )

    seed_reference_incidents()

    remaining = collection.get(ids=_OLD_STUB_IDS).get("ids") or []
    assert remaining == []


def test_seeding_populates_all_real_incidents():
    seed_reference_incidents()

    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")
    found = set(collection.get(ids=ALL_REAL_IDS).get("ids") or [])
    assert found == set(ALL_REAL_IDS)


def test_seeding_twice_does_not_duplicate():
    seed_reference_incidents()
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")
    count_before = len(collection.get(ids=ALL_REAL_IDS).get("ids") or [])

    seed_reference_incidents()
    count_after = len(collection.get(ids=ALL_REAL_IDS).get("ids") or [])

    assert count_before == count_after == len(REAL_INCIDENTS)


def test_seeding_fills_in_a_missing_incident_without_touching_the_rest():
    seed_reference_incidents()
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="incidents")

    # Simulate a data gap: one real incident is missing (e.g. deleted by
    # accident), the rest are present.
    collection.delete(ids=["REAL-001"])
    assert collection.get(ids=["REAL-001"]).get("ids") == []

    seed_reference_incidents()

    restored = collection.get(ids=["REAL-001"])
    assert restored.get("ids") == ["REAL-001"]
