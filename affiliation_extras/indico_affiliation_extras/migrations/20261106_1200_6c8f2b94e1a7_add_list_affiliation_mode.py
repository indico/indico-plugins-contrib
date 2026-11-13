"""Add list affiliation mode

Revision ID: 6c8f2b94e1a7
Revises: a187bc8b5971
Create Date: 2026-11-06 12:00:00.000000

Downgrading discards the configured affiliation modes.
"""

from enum import Enum

import sqlalchemy as sa
from alembic import op

from indico.core.db.sqlalchemy import PyIntEnum


revision = '6c8f2b94e1a7'
down_revision = 'a187bc8b5971'
branch_labels = None
depends_on = None


class _AffiliationListMode(int, Enum):
    predefined = 1
    custom = 2


def upgrade():
    op.add_column(
        'affiliation_lists',
        sa.Column('affiliation_mode', PyIntEnum(_AffiliationListMode), nullable=False, server_default='1'),
        schema='plugin_affiliation_extras',
    )
    op.alter_column('affiliation_lists', 'affiliation_mode', server_default=None, schema='plugin_affiliation_extras')


def downgrade():
    op.drop_column('affiliation_lists', 'affiliation_mode', schema='plugin_affiliation_extras')
