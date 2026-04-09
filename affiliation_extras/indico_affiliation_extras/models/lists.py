# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.modules.users.models.affiliations import Affiliation
from indico.util.string import format_repr

from indico_affiliation_extras.models.groups import AffiliationGroup


list_affiliation_link_table = db.Table(
    'list_affiliation_links',
    db.Column(
        'list_id',
        db.Integer,
        db.ForeignKey('plugin_affiliation_extras.affiliation_lists.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    db.Column(
        'affiliation_id', db.Integer, db.ForeignKey('indico.affiliations.id', ondelete='CASCADE'), primary_key=True
    ),
    schema='plugin_affiliation_extras',
)
db.Index(None, list_affiliation_link_table.c.affiliation_id)

list_group_link_table = db.Table(
    'list_group_links',
    db.Column(
        'list_id',
        db.Integer,
        db.ForeignKey('plugin_affiliation_extras.affiliation_lists.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    db.Column(
        'group_id',
        db.Integer,
        db.ForeignKey('plugin_affiliation_extras.affiliation_groups.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    schema='plugin_affiliation_extras',
)
db.Index(None, list_group_link_table.c.group_id)

list_tag_link_table = db.Table(
    'list_tag_links',
    db.Column(
        'list_id',
        db.Integer,
        db.ForeignKey('plugin_affiliation_extras.affiliation_lists.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    db.Column(
        'tag_id',
        db.Integer,
        db.ForeignKey('plugin_affiliation_extras.affiliation_tags.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    schema='plugin_affiliation_extras',
)
db.Index(None, list_tag_link_table.c.tag_id)


class AffiliationList(db.Model):
    __tablename__ = 'affiliation_lists'
    __table_args__ = {'schema': 'plugin_affiliation_extras'}

    id = db.Column(db.Integer, primary_key=True)
    catalog_id = db.Column(
        db.Integer,
        db.ForeignKey('plugin_affiliation_extras.affiliation_catalogs.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    position = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String, nullable=False, default='')
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)

    catalog = db.relationship(
        'AffiliationCatalog',
        lazy=True,
        foreign_keys=catalog_id,
        backref=db.backref(
            'lists',
            primaryjoin='(AffiliationList.catalog_id == AffiliationCatalog.id) & ~AffiliationCatalog.is_deleted',
            lazy=True,
        ),
    )
    affiliations = db.relationship(
        'Affiliation',
        secondary=list_affiliation_link_table,
        secondaryjoin=lambda: db.and_(
            Affiliation.id == list_affiliation_link_table.c.affiliation_id,
            ~Affiliation.is_deleted,
        ),
        collection_class=set,
        lazy=True,
        backref=db.backref('lists', collection_class=set, lazy=True),
    )
    groups = db.relationship(
        'AffiliationGroup',
        secondary=list_group_link_table,
        secondaryjoin=lambda: db.and_(
            AffiliationGroup.id == list_group_link_table.c.group_id,
            ~AffiliationGroup.is_deleted,
        ),
        collection_class=set,
        lazy=True,
        backref=db.backref('lists', collection_class=set, lazy=True),
    )
    tags = db.relationship(
        'AffiliationTag',
        secondary=list_tag_link_table,
        collection_class=set,
        lazy=True,
        backref=db.backref('lists', collection_class=set, lazy=True),
    )

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', 'category_id', _text=self.name)
