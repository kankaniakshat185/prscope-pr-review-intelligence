import os

# Required settings must exist before app.core.config is imported by anything
# below. In CI there's no .env file, so these provide safe test-only values;
# locally, backend/.env already sets real ones and takes precedence.
os.environ.setdefault("JWT_SECRET", "test-only-secret-do-not-use-in-prod")
os.environ.setdefault("ENABLE_MOCK_AUTH", "true")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def mock_token(client):
    res = client.get("/api/analysis/auth/github/callback?code=mock")
    assert res.status_code == 200, res.text
    return res.json()["access_token"]
