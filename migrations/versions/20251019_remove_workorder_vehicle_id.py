"""Remove vehicle_id from ASP_work_orders (alembic revision)

Revision ID: 20251019_remove_workorder_vehicle_id
Revises: 20251019_alembic_add_service_type
Create Date: 2025-10-19 00:00:00.000000

This revision removes the vehicle_id foreign key and column from the
`ASP_work_orders` table. It is written for PostgreSQL and uses safe checks
(IF EXISTS) to avoid errors when the migration is re-run or the column/constraint
is already absent.

If you use Alembic, place this file in your `migrations/versions/` folder and
run `alembic upgrade head`.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251019_remove_workorder_vehicle_id'
down_revision = '20251019_alembic_add_service_type'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Drop foreign key constraint if exists, then drop the column
    try:
        # Try to find FK name and drop it; Postgres allows IF EXISTS for constraints
        conn.execute(sa.text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = 'asp_work_orders' AND kcu.column_name = 'vehicle_id'
                ) THEN
                    -- Drop the FK constraint(s) referencing vehicle_id
                    ALTER TABLE "ASP_work_orders" DROP CONSTRAINT IF EXISTS "fk_asp_work_orders_vehicle_id";
                    -- Attempt generic drop: find and drop constraint by querying pg_constraint
                    PERFORM set_config('search_path', '', false);
                    FOR r IN (
                        SELECT con.conname
                        FROM pg_constraint con
                        JOIN pg_class rel ON rel.oid = con.conrelid
                        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ANY(con.conkey)
                        WHERE rel.relname = 'ASP_work_orders' AND att.attname = 'vehicle_id'
                    ) LOOP
                        EXECUTE format('ALTER TABLE "ASP_work_orders" DROP CONSTRAINT IF EXISTS %I', r.conname);
                    END LOOP;
                END IF;
            END$$;
        """))
    except Exception:
        # Non-fatal: proceed to drop column if present
        pass

    # Drop the column if it exists
    try:
        op.drop_column('ASP_work_orders', 'vehicle_id')
    except Exception:
        # Column may not exist; ignore
        pass


def downgrade():
    # Recreate vehicle_id column as nullable, and add FK to ASP_vehicles.id
    try:
        op.add_column('ASP_work_orders', sa.Column('vehicle_id', sa.Integer(), nullable=True))
    except Exception:
        pass

    # Add foreign key constraint (best effort)
    try:
        op.create_foreign_key('fk_asp_work_orders_vehicle_id', 'ASP_work_orders', 'ASP_vehicles', ['vehicle_id'], ['id'])
    except Exception:
        pass
