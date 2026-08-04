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
    # Use TestClient as a context manager so FastAPI's startup event actually
    # fires (init_db() creates the tables). Without this, requests still work
    # but every DB-backed route fails with "no such table" on a fresh
    # checkout - it only looked fine locally because a pre-existing
    # prscope.db with tables already created was sitting on disk.
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_token(client):
    res = client.get("/api/analysis/auth/github/callback?code=mock")
    assert res.status_code == 200, res.text
    return res.json()["access_token"]
