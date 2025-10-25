"""Add RBAC tables: roles, permissions, user_roles, role_permissions

Revision ID: 20251019_add_rbac
Revises: 
Create Date: 2025-10-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251019_add_rbac'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ASP_roles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=50), nullable=False, unique=True),
        sa.Column('description', sa.String(length=255)),
    )

    op.create_table(
        'ASP_permissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=100), nullable=False, unique=True),
        sa.Column('description', sa.String(length=255)),
    )

    op.create_table(
        'ASP_user_roles',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('ASP_users.id'), primary_key=True),
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('ASP_roles.id'), primary_key=True),
    )

    op.create_table(
        'ASP_role_permissions',
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('ASP_roles.id'), primary_key=True),
        sa.Column('permission_id', sa.Integer(), sa.ForeignKey('ASP_permissions.id'), primary_key=True),
    )


def downgrade():
    op.drop_table('ASP_role_permissions')
    op.drop_table('ASP_user_roles')
    op.drop_table('ASP_permissions')
    op.drop_table('ASP_roles')
