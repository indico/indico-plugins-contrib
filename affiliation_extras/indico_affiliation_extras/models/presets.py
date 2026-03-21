# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.modules.logs.models.entries import AppLogEntry
from indico.util.string import format_repr


class AffiliationPresets(db.Model):
    __tablename__ = 'affiliation_presets'
    __table_args__ = {'schema': 'plugin_affiliation_extras'}

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.events.id'), index=True, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.categories.id'), index=True, nullable=True)
    parent_id = db.Column(
        db.Integer, db.ForeignKey('plugin_affiliation_extras.affiliation_presets.id'), index=True, nullable=True
    )
    name = db.Column(db.String, nullable=False, default='')
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)

    category = db.relationship(
        'Category',
        lazy=True,
        foreign_keys=category_id,
        backref=db.backref(
            'affiliation_presets',
            primaryjoin='(AffiliationPresets.category_id == Category.id) & ~AffiliationPresets.is_deleted',
            lazy=True,
        ),
    )
    event = db.relationship(
        'Event',
        lazy=True,
        foreign_keys=event_id,
        backref=db.backref(
            'affiliation_presets',
            primaryjoin='(AffiliationPresets.event_id == Event.id) & ~AffiliationPresets.is_deleted',
            lazy=True,
        ),
    )
    parent = db.relationship(
        'AffiliationPresets',
        lazy=True,
        remote_side=id,
        backref=db.backref(
            'children',
            primaryjoin='(AffiliationPresets.parent_id == AffiliationPresets.id) & ~AffiliationPresets.is_deleted',
            lazy=True,
        ),
    )

    # relationship backrefs:
    # - lists (AffiliationList.preset)

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', 'category_id', is_deleted=False, _text=self.name)

    def log(self, *args, **kwargs):
        """Log with prefilled metadata for the affiliation preset."""
        return AppLogEntry.log(*args, meta={'affiliation_preset_id': self.id}, **kwargs)
