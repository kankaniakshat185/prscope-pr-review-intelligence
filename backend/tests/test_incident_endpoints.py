import pytest

from app.services.incident_similarity import get_chroma_client


@pytest.fixture
def cleanup_incident_ids():
    ids = []
    yield ids
    if ids:
        get_chroma_client().get_or_create_collection(name="incidents").delete(ids=ids)


def test_report_incident_requires_auth(client):
    r = client.post("/api/analysis/incidents", json={"repository": "o/r", "description": "x"})
    assert r.status_code == 403


def test_list_incidents_requires_auth(client):
    r = client.get("/api/analysis/incidents", params={"repository": "o/r"})
    assert r.status_code == 403


def test_report_incident_rejects_empty_description(client, mock_token):
    r = client.post(
        "/api/analysis/incidents",
        headers={"Authorization": f"Bearer {mock_token}"},
        json={"repository": "acme/incident-endpoint-test", "description": "   "},
    )
    assert r.status_code == 400


def test_report_incident_attributes_the_reporting_user(client, mock_token, cleanup_incident_ids):
    r = client.post(
        "/api/analysis/incidents",
        headers={"Authorization": f"Bearer {mock_token}"},
        json={
            "repository": "acme/incident-endpoint-test",
            "description": "Deploy rollback failed silently, leaving two versions running simultaneously",
            "severity": "High",
        },
    )
    assert r.status_code == 200
    body = r.json()
    cleanup_incident_ids.append(body["incident_id"])

    assert body["repository"] == "acme/incident-endpoint-test"
    assert body["severity"] == "High"
    assert body["reported_by"] == "dev_reviewer"  # the mock login's username


def test_reported_incident_shows_up_in_the_team_list(client, mock_token, cleanup_incident_ids):
    repository = "acme/incident-endpoint-list-test"
    r = client.post(
        "/api/analysis/incidents",
        headers={"Authorization": f"Bearer {mock_token}"},
        json={"repository": repository, "description": "Some incident description", "severity": "Medium"},
    )
    incident_id = r.json()["incident_id"]
    cleanup_incident_ids.append(incident_id)

    r_list = client.get(
        "/api/analysis/incidents",
        headers={"Authorization": f"Bearer {mock_token}"},
        params={"repository": repository},
    )
    assert r_list.status_code == 200
    ids = {i["incident_id"] for i in r_list.json()}
    assert incident_id in ids
