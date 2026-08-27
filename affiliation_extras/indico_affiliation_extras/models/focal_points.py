# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.models.users import User


class FocalPoint(db.Model):
    """A user designated as a focal point for an affiliation."""

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


def get_focal_points(affiliation):
    return {entry.user for entry in affiliation.focal_point_entries}


def set_focal_points(affiliation, users):
    entries = {entry.user: entry for entry in affiliation.focal_point_entries}
    for user in users - entries.keys():
        affiliation.focal_point_entries.add(FocalPoint(user=user))
    for user, entry in entries.items():
        if user not in users:
            affiliation.focal_point_entries.discard(entry)
