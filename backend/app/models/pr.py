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

class RepoIndex(Base):
    """
    Tracks a persisted, repo-wide function/call index for one repository -
    built once (full scan of the default branch) and refreshed incrementally
    afterward (only the files that changed since indexed_sha get re-parsed).
    Powers cross-file "blast radius" lookups that a single PR's diff alone
    can't see (a caller in a file the PR never touched).
    """
    __tablename__ = "repo_indexes"

    id = Column(Integer, primary_key=True, index=True)
    repository = Column(String, unique=True, index=True)  # "owner/repo"
    status = Column(String, default="pending")  # pending, indexing, ready, failed
    indexed_sha = Column(String, nullable=True)
    indexed_at = Column(DateTime, nullable=True)
    file_count = Column(Integer, default=0)
    function_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    functions = relationship("IndexedFunction", back_populates="repo_index", cascade="all, delete-orphan")
    calls = relationship("IndexedCall", back_populates="repo_index", cascade="all, delete-orphan")


class IndexedFunction(Base):
    __tablename__ = "indexed_functions"

    id = Column(Integer, primary_key=True, index=True)
    repo_index_id = Column(Integer, ForeignKey("repo_indexes.id"), index=True)
    file_path = Column(String, index=True)
    name = Column(String, index=True)

    __table_args__ = (
        UniqueConstraint('repo_index_id', 'file_path', 'name', name='uix_repoindex_file_func'),
    )

    repo_index = relationship("RepoIndex", back_populates="functions")


class IndexedCall(Base):
    """
    One (caller_file, caller_name) -> callee_name edge, unresolved to a
    specific callee file at write time. Cross-file blast-radius queries
    resolve "who calls X" by matching callee_name against this table -
    approximate (a common function name could match unrelated definitions
    elsewhere in the repo), same bare-name-only tradeoff the PR-local call
    graph (dependency_engine.py) already makes.
    """
    __tablename__ = "indexed_calls"

    id = Column(Integer, primary_key=True, index=True)
    repo_index_id = Column(Integer, ForeignKey("repo_indexes.id"), index=True)
    caller_file_path = Column(String, index=True)
    caller_name = Column(String, index=True)
    callee_name = Column(String, index=True)

    repo_index = relationship("RepoIndex", back_populates="calls")


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Could not connect to database ({settings.DATABASE_URL}) to initialize tables. {e}")
