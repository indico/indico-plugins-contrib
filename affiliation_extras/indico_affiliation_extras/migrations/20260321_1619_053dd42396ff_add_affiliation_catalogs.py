"""Add affiliation catalogs

Revision ID: 053dd42396ff
Revises: 7434e891c031
Create Date: 2026-03-21 16:19:44.837708
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '053dd42396ff'
down_revision = '7434e891c031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'affiliation_catalogs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=True),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.categories.id']),
        sa.ForeignKeyConstraint(['event_id'], ['events.events.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['plugin_affiliation_extras.affiliation_catalogs.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='plugin_affiliation_extras',
    )
    op.create_index(None, 'affiliation_catalogs', ['category_id'], unique=False, schema='plugin_affiliation_extras')
    op.create_index(None, 'affiliation_catalogs', ['event_id'], unique=False, schema='plugin_affiliation_extras')
    op.create_index(None, 'affiliation_catalogs', ['parent_id'], unique=False, schema='plugin_affiliation_extras')
    op.create_table(
        'affiliation_lists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('catalog_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ['catalog_id'], ['plugin_affiliation_extras.affiliation_catalogs.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        schema='plugin_affiliation_extras',
    )
    op.create_index(None, 'affiliation_lists', ['catalog_id'], unique=False, schema='plugin_affiliation_extras')
    op.create_table(
        'list_affiliation_links',
        sa.Column('list_id', sa.Integer(), nullable=False),
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['list_id'], ['plugin_affiliation_extras.affiliation_lists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('list_id', 'affiliation_id'),
        schema='plugin_affiliation_extras',
    )
    op.create_index(
        None, 'list_affiliation_links', ['affiliation_id'], unique=False, schema='plugin_affiliation_extras'
    )
    op.create_table(
        'list_group_links',
        sa.Column('list_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['plugin_affiliation_extras.affiliation_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['list_id'], ['plugin_affiliation_extras.affiliation_lists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('list_id', 'group_id'),
        schema='plugin_affiliation_extras',
    )
    op.create_index(None, 'list_group_links', ['group_id'], unique=False, schema='plugin_affiliation_extras')
    op.create_table(
        'list_tag_links',
        sa.Column('list_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['list_id'], ['plugin_affiliation_extras.affiliation_lists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['plugin_affiliation_extras.affiliation_tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('list_id', 'tag_id'),
        schema='plugin_affiliation_extras',
    )
    op.create_index(None, 'list_tag_links', ['tag_id'], unique=False, schema='plugin_affiliation_extras')


def downgrade():
    op.drop_table('list_tag_links', schema='plugin_affiliation_extras')
    op.drop_table('list_group_links', schema='plugin_affiliation_extras')
    op.drop_table('list_affiliation_links', schema='plugin_affiliation_extras')
    op.drop_table('affiliation_lists', schema='plugin_affiliation_extras')
    op.drop_table('affiliation_catalogs', schema='plugin_affiliation_extras')
