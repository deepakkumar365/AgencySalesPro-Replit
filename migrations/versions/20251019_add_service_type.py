"""Add service_type to ASP_service_catalog

Revision ID: 20251019_add_service_type
Revises: 
Create Date: 2025-10-19 00:00:00.000000

This is a helper Alembic-style migration script. If you use Alembic, convert this
into an actual revision with `alembic revision --autogenerate` and paste the
upgrade/downgrade operations. This script can also be run directly as a helper
from the project root.
"""

from sqlalchemy import text


def upgrade(engine, connection):
    inspector = engine.dialect
    dialect = engine.name.lower()

    # Add column (safe)
    if dialect in ('postgresql', 'postgres', 'mysql', 'mariadb'):
        alter_sql = "ALTER TABLE ASP_service_catalog ADD COLUMN service_type VARCHAR(50) DEFAULT 'garage';"
    else:
        alter_sql = "ALTER TABLE ASP_service_catalog ADD COLUMN service_type VARCHAR(50);"

    connection.execute(text(alter_sql))

    # Backfill
    connection.execute(text("UPDATE ASP_service_catalog SET service_type = 'garage' WHERE service_type IS NULL OR service_type = '';"))


def downgrade(engine, connection):
    # Remove column if needed. Be careful in production.
    try:
        connection.execute(text("ALTER TABLE ASP_service_catalog DROP COLUMN service_type;"))
    except Exception:
        # Some dialects (SQLite) require table recreation; skip automatic drop to be safe
        pass


if __name__ == '__main__':
    # Helper runner: create a minimal engine via DATABASE_URL env if available
    import os
    from sqlalchemy import create_engine

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('Please set DATABASE_URL environment variable to run this script.')
        raise SystemExit(1)

    engine = create_engine(db_url)
    with engine.connect() as conn:
        print('Applying upgrade...')
        upgrade(engine, conn)
        print('Done')
