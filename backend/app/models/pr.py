from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(String, unique=True, index=True)
    username = Column(String)
    avatar_url = Column(String)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    saved_reviews = relationship("SavedReview", back_populates="user")

class SavedReview(Base):
    __tablename__ = "saved_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    repository = Column(String, index=True)
    repository_owner = Column(String)
    repository_name = Column(String)
    pr_number = Column(Integer)
    pr_title = Column(String)
    pr_url = Column(String)
    risk_score = Column(Float)
    risk_category = Column(String)
    executive_summary = Column(Text)
    review_status = Column(String, index=True)
    review_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_reviewed_at = Column(DateTime, index=True)

    __table_args__ = (
        UniqueConstraint('user_id', 'repository', 'pr_number', name='uix_user_repo_pr'),
    )

    user = relationship("User", back_populates="saved_reviews")
    events = relationship("ReviewEvent", back_populates="review", cascade="all, delete-orphan")

class ReviewEvent(Base):
    __tablename__ = "review_events"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("saved_reviews.id"))
    event_type = Column(String)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    review = relationship("SavedReview", back_populates="events")

# Legacy tables
class PRAnalysisResult(Base):
    __tablename__ = "pr_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String, index=True)
    pr_number = Column(Integer, index=True)
    risk_score = Column(Float)
    risk_category = Column(String)
    executive_summary = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class ReviewNote(Base):
    __tablename__ = "review_notes"

    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String, index=True)
    pr_number = Column(Integer, index=True)
    status = Column(String, default="IN_PROGRESS")
    notes = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Could not connect to PostgreSQL database to initialize tables. {e}")
