from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import api_router
from app.models.pr import init_db
from app.services.incident_similarity import seed_reference_incidents

app = FastAPI(title=settings.PROJECT_NAME)

allowed_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(api_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    init_db()
    seed_reference_incidents()

@app.get("/")
def read_root():
    return {"message": "Welcome to PRScope API"}
