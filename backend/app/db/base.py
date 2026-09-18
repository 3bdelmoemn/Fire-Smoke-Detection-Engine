"""
SQLAlchemy declarative base.

Every ORM model imports ``Base`` from here so there is a single
metadata registry that Alembic and ``create_all`` can discover.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass
