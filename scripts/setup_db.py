"""
setup_db.py — Create all database tables

Run this script once to create the 3 tables in your PostgreSQL database:
    python scripts/setup_db.py

It uses the ORM models defined in backend/models/db_models.py
and the engine from backend/database.py.
"""

import sys
import os

# Add the project root to Python's path so we can import from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, Base

# Import all models so Base.metadata knows about them
from backend.models.db_models import Persona, Conversation, KnowledgeDoc


def create_tables():
    """Create all tables defined by the ORM models."""
    print("Creating database tables...")
    print(f"  Database: {engine.url}")
    print()

    # This reads all classes that inherit from Base and creates
    # their corresponding tables in PostgreSQL (if they don't already exist)
    Base.metadata.create_all(bind=engine)

    # Print what was created
    for table_name in Base.metadata.tables:
        print(f"  [OK] Table '{table_name}' ready")

    print()
    print("Done! All tables created successfully.")


def verify_tables():
    """Verify tables exist by running a quick query."""
    from sqlalchemy import text

    print()
    print("Verifying tables...")

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """))
        tables = [row[0] for row in result]

        if tables:
            print(f"  Found {len(tables)} tables: {', '.join(tables)}")
        else:
            print("  ⚠️ No tables found!")

    return tables


if __name__ == "__main__":
    create_tables()
    verify_tables()
