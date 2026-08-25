import os
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jobpilot.db")

# Handle PostgreSQL vs SQLite engine parameters
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class JobRecord(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False, index=True)
    company = Column(String, nullable=True, index=True)
    location = Column(String, nullable=True)
    url = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    salary = Column(String, nullable=True)
    publication_date = Column(String, nullable=True)
    job_type = Column(String, nullable=True)
    
    # AI Analysis Fields
    match_score = Column(Integer, default=0, index=True)
    seniority_level = Column(String, default="Unknown")
    required_skills = Column(JSON, default=list)
    matching_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)
    recommendation = Column(String, default="CONSIDER", index=True)
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
