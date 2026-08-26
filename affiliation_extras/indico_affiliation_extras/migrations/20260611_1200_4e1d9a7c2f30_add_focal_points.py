"""Add focal points

Revision ID: 4e1d9a7c2f30
Revises: 053dd42396ff
Create Date: 2026-06-11 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '4e1d9a7c2f30'
down_revision = '053dd42396ff'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'focal_points',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'affiliation_id'),
        schema='plugin_affiliation_extras',
    )
    op.create_index(None, 'focal_points', ['affiliation_id'], unique=False, schema='plugin_affiliation_extras')


def downgrade():
    op.drop_table('focal_points', schema='plugin_affiliation_extras')
