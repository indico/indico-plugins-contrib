# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.modules.logs.models.entries import CategoryLogRealm, EventLogRealm
from indico.util.string import format_repr


class AffiliationCatalog(db.Model):
    __tablename__ = 'affiliation_catalogs'
    __table_args__ = (
        db.CheckConstraint('(event_id IS NULL) != (category_id IS NULL)', 'event_xor_category_id_null'),
        {'schema': 'plugin_affiliation_extras'},
    )

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.events.id', ondelete='CASCADE'), index=True, nullable=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey('categories.categories.id', ondelete='CASCADE'), index=True, nullable=True
    )
    name = db.Column(db.String, nullable=False, default='')
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)

    category = db.relationship(
        'Category',
        lazy=True,
        foreign_keys=category_id,
        backref=db.backref(
            'affiliation_catalogs',
            primaryjoin='(AffiliationCatalog.category_id == Category.id) & ~AffiliationCatalog.is_deleted',
            lazy=True,
        ),
    )
    event = db.relationship(
        'Event',
        lazy=True,
        foreign_keys=event_id,
        backref=db.backref(
            'affiliation_catalogs',
            primaryjoin='(AffiliationCatalog.event_id == Event.id) & ~AffiliationCatalog.is_deleted',
            lazy=True,
        ),
    )
    # relationship backrefs:
    # - lists (AffiliationList.catalog)

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', 'category_id', is_deleted=False, _text=self.name)

    @property
    def owner(self):
        return self.event or self.category

    @property
    def log_realm(self):
        return EventLogRealm.management if self.event else CategoryLogRealm.category
