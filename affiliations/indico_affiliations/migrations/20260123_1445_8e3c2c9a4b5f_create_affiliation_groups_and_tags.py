"""Create affiliation groups and tags

Revision ID: 8e3c2c9a4b5f
Revises:
Create Date: 2026-01-23 14:45:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.ddl import CreateSchema, DropSchema


# revision identifiers, used by Alembic.
revision = '8e3c2c9a4b5f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(CreateSchema('plugin_affiliations'))

    op.create_table(
        'affiliation_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('meta', postgresql.JSONB(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('system', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='plugin_affiliations'
    )
    op.create_index(
        None,
        'affiliation_groups',
        ['code'],
        unique=True,
        schema='plugin_affiliations',
        postgresql_where=sa.text('NOT is_deleted')
    )
    op.create_table(
        'affiliation_group_links',
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['plugin_affiliations.affiliation_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('affiliation_id', 'group_id'),
        schema='plugin_affiliations'
    )
    op.create_index(None, 'affiliation_group_links', ['group_id'], schema='plugin_affiliations')

    op.create_table(
        'affiliation_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('color', sa.String(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='plugin_affiliations'
    )
    op.create_index(
        None,
        'affiliation_tags',
        ['code'],
        unique=True,
        schema='plugin_affiliations',
        postgresql_where=sa.text('NOT is_deleted')
    )
    op.create_table(
        'affiliation_tag_links',
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['plugin_affiliations.affiliation_tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('affiliation_id', 'tag_id'),
        schema='plugin_affiliations'
    )
    op.create_index(None, 'affiliation_tag_links', ['tag_id'], schema='plugin_affiliations')


    op.create_table(
        'group_tag_links',
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['plugin_affiliations.affiliation_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['plugin_affiliations.affiliation_tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('group_id', 'tag_id'),
        schema='plugin_affiliations'
    )
    op.create_index(None, 'group_tag_links', ['tag_id'], unique=False, schema='plugin_affiliations')


def downgrade():
    op.drop_table('group_tag_links', schema='plugin_affiliations')

    op.drop_table('affiliation_tag_links', schema='plugin_affiliations')
    op.drop_table('affiliation_tags', schema='plugin_affiliations')

    op.drop_table('affiliation_group_links', schema='plugin_affiliations')
    op.drop_table('affiliation_groups', schema='plugin_affiliations')

    op.execute(DropSchema('plugin_affiliations'))
