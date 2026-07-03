"""Add inactive contact emails

Revision ID: a187bc8b5971
Revises: 7434e891c031
Create Date: 2026-06-29 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a187bc8b5971'
down_revision = '7434e891c031'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'affiliation_contact_lists',
        sa.Column('inactive_emails', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        schema='plugin_affiliation_extras',
    )
    op.alter_column(
        'affiliation_contact_lists',
        'inactive_emails',
        server_default=None,
        schema='plugin_affiliation_extras',
    )


def downgrade():
    op.drop_column('affiliation_contact_lists', 'inactive_emails', schema='plugin_affiliation_extras')
