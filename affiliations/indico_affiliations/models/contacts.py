# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.util.string import format_repr


class AffiliationContactList(db.Model):
    __tablename__ = 'affiliation_contact_lists'
    __table_args__ = (
        db.Index(
            'ix_uq_affiliation_contacts_affiliation_id_name_lower',
            'affiliation_id',
            db.text('lower(name)'),
            unique=True,
        ),
        {'schema': 'plugin_affiliations'},
    )

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    affiliation_id = db.Column(
        db.Integer,
        db.ForeignKey('indico.affiliations.id', ondelete='CASCADE'),
        nullable=False
    )
    name = db.Column(
        db.String,
        nullable=False,
        default=''
    )
    emails = db.Column(
        db.ARRAY(db.String),
        nullable=False,
        default=list
    )

    affiliation = db.relationship(
        'Affiliation',
        lazy=True,
        backref=db.backref(
            'contacts',
            order_by=lambda: db.func.indico.indico_unaccent(db.func.lower(AffiliationContactList.name)),
            lazy=True,
            cascade='all, delete-orphan'
        )
    )

    def __repr__(self):
        return format_repr(self, 'id', _text=self.name)
