# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.modules.logs.models.entries import AppLogEntry
from indico.modules.users.models.affiliations import Affiliation
from indico.util.string import format_repr


affiliation_tag_link_table = db.Table(
    'affiliation_tag_links',
    db.Column(
        'affiliation_id',
        db.Integer,
        db.ForeignKey('indico.affiliations.id', ondelete='CASCADE'),
        primary_key=True
    ),
    db.Column(
        'tag_id',
        db.Integer,
        db.ForeignKey('plugin_affiliations.affiliation_tags.id', ondelete='CASCADE'),
        primary_key=True
    ),
    schema='plugin_affiliations'
)
db.Index(None, affiliation_tag_link_table.c.tag_id)


class AffiliationTag(db.Model):
    __tablename__ = 'affiliation_tags'
    __table_args__ = (
        db.Index(None, 'code', unique=True, postgresql_where=db.text('NOT is_deleted')),
        {'schema': 'plugin_affiliations'},
    )

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    name = db.Column(
        db.String,
        nullable=False
    )
    code = db.Column(
        db.String,
        nullable=False
    )
    color = db.Column(
        db.String,
        nullable=False
    )
    is_deleted = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    affiliations = db.relationship(
        'Affiliation',
        secondary=affiliation_tag_link_table,
        primaryjoin=lambda: db.and_(
            AffiliationTag.id == affiliation_tag_link_table.c.tag_id,
            ~AffiliationTag.is_deleted,
        ),
        secondaryjoin=lambda: db.and_(
            Affiliation.id == affiliation_tag_link_table.c.affiliation_id,
            ~Affiliation.is_deleted,
        ),
        collection_class=set,
        lazy=True,
        backref=db.backref(
            'tags',
            collection_class=set,
            lazy=True
        )
    )

    def __repr__(self):
        return format_repr(self, 'id', 'code', _text=self.name)

    def log(self, *args, **kwargs):
        """Log with prefilled metadata for the affiliation tag."""
        return AppLogEntry.log(*args, meta={'affiliation_tag_id': self.id}, **kwargs)
