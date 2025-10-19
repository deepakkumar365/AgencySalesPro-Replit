"""
Drop ASP_vehicles table (vehicle model removed)

Revision ID: 20251019_drop_asp_vehicles
Revises: 
Create Date: 2025-10-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251019_drop_asp_vehicles'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Drop table if it exists. This is destructive; ensure backups exist before running.
    op.execute('DROP TABLE IF EXISTS "ASP_vehicles" CASCADE;')


def downgrade():
    # Recreate a reasonable approximation of the previous ASP_vehicles table.
    op.create_table(
        'ASP_vehicles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('agency_id', sa.Integer, sa.ForeignKey('ASP_agencies.id'), nullable=True, index=True),
        sa.Column('customer_id', sa.Integer, sa.ForeignKey('ASP_customers.id'), nullable=True, index=True),
        sa.Column('license_plate', sa.String(50), nullable=True),
        sa.Column('make', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('year', sa.String(10), nullable=True),
        sa.Column('vin', sa.String(64), nullable=True),
        sa.Column('color_code', sa.String(12), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
"""
Drop ASP_vehicles table (vehicle model removed)

Revision ID: 20251019_drop_asp_vehicles
Revises: 
Create Date: 2025-10-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251019_drop_asp_vehicles'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Drop table if it exists. This is destructive; ensure backups exist before running.
    op.execute('DROP TABLE IF EXISTS "ASP_vehicles" CASCADE;')


def downgrade():
    # Recreate a reasonable approximation of the previous ASP_vehicles table.
    op.create_table(
        'ASP_vehicles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('agency_id', sa.Integer, sa.ForeignKey('ASP_agencies.id'), nullable=True),
        sa.Column('customer_id', sa.Integer, sa.ForeignKey('ASP_customers.id'), nullable=True),
        sa.Column('license_plate', sa.String(50), nullable=True),
        sa.Column('make', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('year', sa.String(10), nullable=True),
        sa.Column('vin', sa.String(64), nullable=True),
        sa.Column('color_code', sa.String(12), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )