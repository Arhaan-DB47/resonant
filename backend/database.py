"""
database.py — SQLAlchemy Engine & Session Setup

This module creates:
1. The database ENGINE — the connection to PostgreSQL
2. SessionLocal — a factory that creates new database sessions
3. Base — the declarative base class that all ORM models inherit from
4. get_db() — a dependency that FastAPI uses to get a DB session per request
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read the database URL from .env
# Format: postgresql://username:password@host:port/database_name
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set! "
        "Create a .env file with DATABASE_URL=postgresql://user:password@localhost:5432/resonant"
    )

# Create the SQLAlchemy engine
# - The engine manages the actual database connection pool
# - echo=True prints all SQL statements to the console (helpful for learning, disable in production)
engine = create_engine(DATABASE_URL, echo=False)

# Create a session factory
# - autocommit=False: we manually commit transactions (safer — prevents accidental partial writes)
# - autoflush=False: we manually control when changes are sent to the DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the declarative base class
# - Every ORM model (Persona, Conversation, KnowledgeDoc) inherits from this
# - It keeps a registry of all models so create_all() knows what tables to create
Base = declarative_base()


def get_db():
    """
    Dependency function for FastAPI.

    Usage in a route:
        @app.get("/api/personas")
        def list_personas(db: Session = Depends(get_db)):
            return db.query(Persona).all()

    The 'yield' pattern ensures the session is always closed after the request,
    even if an error occurs. This prevents database connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
