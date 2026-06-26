# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from sqlalchemy.ext.associationproxy import association_proxy

from indico.core.db import db
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.models.users import User


class FocalPoint(db.Model):
    """A user designated as a focal point for an affiliation.

    A focal point may manage the registrations whose affiliation is one they are linked to here.
    """

    __tablename__ = 'focal_points'
    __table_args__ = (
        db.Index(None, 'affiliation_id'),
        {'schema': 'plugin_affiliation_extras'},
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id', ondelete='CASCADE'),
        primary_key=True,
    )
    affiliation_id = db.Column(
        db.Integer,
        db.ForeignKey('indico.affiliations.id', ondelete='CASCADE'),
        primary_key=True,
    )

    user = db.relationship(
        User,
        lazy=True,
        backref=db.backref('focal_point_entries', collection_class=set, lazy=True, cascade='all, delete-orphan'),
    )
    affiliation = db.relationship(
        Affiliation,
        lazy=True,
        backref=db.backref('focal_point_entries', collection_class=set, lazy=True, cascade='all, delete-orphan'),
    )


#: The users that act as focal points for an affiliation.
Affiliation.focal_points = association_proxy(
    'focal_point_entries', 'user', creator=lambda user: FocalPoint(user=user)
)
#: The affiliations a user acts as a focal point for.
User.focal_point_affiliations = association_proxy(
    'focal_point_entries', 'affiliation', creator=lambda affiliation: FocalPoint(affiliation=affiliation)
)
