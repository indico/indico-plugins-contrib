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
    op.add_column(
        'affiliations',
        sa.Column('contact_emails', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        schema='indico',
    )
    op.alter_column('affiliations', 'contact_emails', server_default=None, schema='indico')


def downgrade():
    op.drop_column('affiliations', 'contact_emails', schema='indico')
