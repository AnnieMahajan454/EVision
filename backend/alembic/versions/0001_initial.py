"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables using SQLAlchemy metadata."""
    # Import here to ensure model modules are available
    from backend.database.base import Base
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop all tables created by upgrade."""
    from backend.database.base import Base
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
