import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.services.auth import create_access_token, verify_token


def test_token_round_trip():
    token = create_access_token({"sub": "42"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert verify_token(creds) == 42


def test_garbage_token_is_rejected():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-real-token")
    with pytest.raises(HTTPException) as exc_info:
        verify_token(creds)
    assert exc_info.value.status_code == 401


def test_token_signed_with_a_different_secret_is_rejected():
    import jwt as pyjwt
    forged = pyjwt.encode({"sub": "1"}, "some-other-secret", algorithm="HS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged)
    with pytest.raises(HTTPException):
        verify_token(creds)
