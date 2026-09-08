"""SQLAlchemy declarative base.

Empty of models by design. Phase 0 establishes the migration machinery; the
product's tables arrive with their stories, so the schema is never built ahead
of a requirement for it.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
