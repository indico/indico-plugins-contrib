# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.core.db import db
from indico.modules.users.models.affiliations import Affiliation


#: Association between affiliations and the users that act as their focal points. A focal point
#: may manage registrations whose affiliation is one they are linked to here.
focal_points_table = db.Table(
    'focal_points',
    db.Column('user_id', db.Integer, db.ForeignKey('users.users.id', ondelete='CASCADE'), primary_key=True),
    db.Column(
        'affiliation_id', db.Integer, db.ForeignKey('indico.affiliations.id', ondelete='CASCADE'), primary_key=True
    ),
    schema='plugin_affiliation_extras',
)
db.Index(None, focal_points_table.c.affiliation_id)


Affiliation.focal_points = db.relationship(
    'User',
    secondary=focal_points_table,
    collection_class=set,
    lazy=True,
    backref=db.backref('focal_point_affiliations', collection_class=set, lazy=True),
)
