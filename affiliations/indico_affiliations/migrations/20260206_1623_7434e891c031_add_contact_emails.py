"""Add contact emails to affiliations

Revision ID: 7434e891c031
Revises: 8e3c2c9a4b5f
Create Date: 2026-02-06 16:23:47.339691
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '7434e891c031'
down_revision = '8e3c2c9a4b5f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('affiliation_contact_lists',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('emails', postgresql.ARRAY(sa.String()), nullable=False),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='plugin_affiliations'
    )
    op.create_index(None, 'affiliation_contact_lists', ['affiliation_id', sa.text('lower(name)')], unique=True,
                    schema='plugin_affiliations')


def downgrade():
    op.drop_table('affiliation_contact_lists', schema='plugin_affiliations')
