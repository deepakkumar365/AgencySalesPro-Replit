"""Add service_type to ASP_service_catalog (alembic revision)

Revision ID: 20251019_alembic_add_service_type
Revises: 
Create Date: 2025-10-19 00:00:00.000000

This revision adds a non-destructive `service_type` column to the
`ASP_service_catalog` table and backfills existing records with 'garage'.

If you use Alembic, place this file in your `migrations/versions/` folder and
run `alembic upgrade head`.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251019_alembic_add_service_type'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Add column if not exists. SQLAlchemy/Alembic has no built-in "IF NOT EXISTS"
    # so we attempt to add and ignore failures if column already exists.
    try:
        op.add_column('ASP_service_catalog', sa.Column('service_type', sa.String(length=50), nullable=True, server_default='garage'))
    except Exception:
        # Column probably exists; continue
        pass

    # Backfill existing rows
    conn.execute(sa.text("""
        UPDATE ASP_service_catalog
        SET service_type = 'garage'
        WHERE service_type IS NULL OR service_type = ''
    """))

    # Optionally remove server_default so new rows rely on application defaults
    try:
        op.alter_column('ASP_service_catalog', 'service_type', server_default=None)
    except Exception:
        pass


def downgrade():
    # Remove the column if possible (note: SQLite may require table recreation)
    try:
        op.drop_column('ASP_service_catalog', 'service_type')
    except Exception:
        pass
