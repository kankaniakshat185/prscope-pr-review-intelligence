import pytest

from app.services.incident_similarity import add_team_incident, find_similar_incidents, get_chroma_client, list_team_incidents


@pytest.fixture
def cleanup_incidents():
    created_ids = []
    yield created_ids
    if created_ids:
        client = get_chroma_client()
        client.get_or_create_collection(name="incidents").delete(ids=created_ids)


def test_add_team_incident_returns_the_stored_fields(cleanup_incidents):
    repository = "test-org/repo-incidents-add"
    incident = add_team_incident(repository, "Deploy caused a cascading outage due to a missing feature flag", "Critical", reported_by="alice")
    cleanup_incidents.append(incident["incident_id"])

    assert incident["repository"] == repository
    assert incident["severity"] == "Critical"
    assert incident["reported_by"] == "alice"
    assert incident["incident_id"].startswith("TEAM-")
    assert incident["description"] == "Deploy caused a cascading outage due to a missing feature flag"


def test_add_team_incident_without_reported_by_is_none_not_empty_string(cleanup_incidents):
    incident = add_team_incident("test-org/repo-incidents-anon", "Some incident", "Low")
    cleanup_incidents.append(incident["incident_id"])
    assert incident["reported_by"] is None


def test_list_team_incidents_returns_what_was_added(cleanup_incidents):
    repository = "test-org/repo-incidents-list"
    incident = add_team_incident(repository, "Race condition in the job scheduler duplicated payouts", "Critical", reported_by="carol")
    cleanup_incidents.append(incident["incident_id"])

    listed = list_team_incidents(repository)
    assert len(listed) == 1
    assert listed[0]["incident_id"] == incident["incident_id"]
    assert listed[0]["description"] == "Race condition in the job scheduler duplicated payouts"
    assert listed[0]["reported_by"] == "carol"


def test_list_team_incidents_only_returns_the_matching_repository(cleanup_incidents):
    repo_a = "test-org/repo-incidents-scope-a"
    repo_b = "test-org/repo-incidents-scope-b"
    incident_a = add_team_incident(repo_a, "Incident specific to repo A", "Low")
    incident_b = add_team_incident(repo_b, "Incident specific to repo B", "Low")
    cleanup_incidents.extend([incident_a["incident_id"], incident_b["incident_id"]])

    listed_a = list_team_incidents(repo_a)
    ids_a = {i["incident_id"] for i in listed_a}
    assert incident_a["incident_id"] in ids_a
    assert incident_b["incident_id"] not in ids_a


def test_list_team_incidents_returns_empty_for_a_repo_with_none(cleanup_incidents):
    assert list_team_incidents("test-org/repo-incidents-never-reported") == []


def test_find_similar_incidents_matches_a_team_reported_incident(cleanup_incidents):
    repository = "test-org/repo-incidents-match"
    incident = add_team_incident(
        repository,
        "Null pointer exception in the checkout service caused by an unhandled empty cart edge case during Black Friday traffic",
        "Critical",
        reported_by="bob",
    )
    cleanup_incidents.append(incident["incident_id"])

    pr_data = {
        "title": "Fix checkout crash",
        "description": "Handles empty cart edge case in checkout service to avoid null pointer exception",
    }
    results = find_similar_incidents(pr_data)

    matched = [r for r in results if incident["incident_id"] in r["explanation"]]
    assert len(matched) == 1
    assert "team-reported by bob" in matched[0]["explanation"]
