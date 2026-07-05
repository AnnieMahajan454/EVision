"""Utility script to manage the database for local dev.

Usage:
  python manage_db.py create
  python manage_db.py drop

This is a convenience when Alembic is not available; for production use Alembic migrations instead.
"""
import sys
from database.session import engine
from database.base import Base


def create_all():
    print("Creating tables via SQLAlchemy metadata...")
    Base.metadata.create_all(bind=engine)
    print("Done.")


def drop_all():
    print("Dropping tables via SQLAlchemy metadata...")
    Base.metadata.drop_all(bind=engine)
    print("Done.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python manage_db.py [create|drop]")
        return
    cmd = sys.argv[1]
    if cmd == "create":
        create_all()
    elif cmd == "drop":
        drop_all()
    else:
        print("Unknown command", cmd)


if __name__ == "__main__":
    main()
