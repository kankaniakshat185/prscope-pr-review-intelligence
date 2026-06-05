from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class PRAnalysisResult(Base):
    __tablename__ = "pr_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String, index=True)
    pr_number = Column(Integer, index=True)
    risk_score = Column(Float)
    risk_category = Column(String)
    executive_summary = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Could not connect to PostgreSQL database to initialize tables. {e}")
