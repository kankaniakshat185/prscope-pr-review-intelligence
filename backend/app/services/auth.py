import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

ALGORITHM = "HS256"
SECRET_KEY = settings.JWT_SECRET

security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


OAUTH_STATE_TTL_SECONDS = 600  # long enough to get through GitHub's consent screen


def create_oauth_state(origin: str) -> str:
    """
    A short-lived, signed nonce round-tripped through GitHub's OAuth flow
    (authorize URL -> callback) - standard CSRF protection for the
    callback, and a way for the callback to learn which extension origin
    actually started this login (from the `Origin` header on the original
    /auth/github/login request) so it can target its postMessage response
    at that one origin instead of broadcasting the session token to "*".
    A distinct `purpose` claim (and no 7-day expiry) keeps this from being
    confused with, or usable as, a real session token.
    """
    payload = {
        "purpose": "oauth_state",
        "origin": origin,
        "exp": datetime.utcnow() + timedelta(seconds=OAUTH_STATE_TTL_SECONDS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_oauth_state(state: str) -> str:
    """Returns the origin embedded in a valid, unexpired state value this
    backend issued. Raises HTTPException(400) otherwise - an invalid state
    means either a forged/replayed callback or a stale popup, and either
    way the login shouldn't proceed."""
    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        payload = None
    if not payload or payload.get("purpose") != "oauth_state":
        raise HTTPException(status_code=400, detail="Invalid or expired login session. Please try logging in again.")
    return payload.get("origin") or ""

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return int(user_id)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
