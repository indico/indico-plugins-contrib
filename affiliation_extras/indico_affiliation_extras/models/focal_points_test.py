# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.modules.users.models.affiliations import Affiliation


def test_focal_points_relationship_both_directions(db, create_user):
    user = create_user(123)
    affiliation = Affiliation(name='CERN')
    db.session.add(affiliation)
    db.session.flush()

    affiliation.focal_points.add(user)
    db.session.flush()

    assert user in affiliation.focal_points
    assert affiliation in user.focal_point_affiliations


def test_focal_point_for_multiple_affiliations(db, create_user):
    user = create_user(123)
    cern = Affiliation(name='CERN')
    mit = Affiliation(name='MIT')
    db.session.add_all([cern, mit])
    db.session.flush()

    user.focal_point_affiliations.update({cern, mit})
    db.session.flush()

    assert {cern, mit} <= set(user.focal_point_affiliations)
    assert user in cern.focal_points
    assert user in mit.focal_points


def test_affiliation_with_multiple_focal_points(db, create_user):
    affiliation = Affiliation(name='CERN')
    db.session.add(affiliation)
    db.session.flush()
    alice = create_user(1)
    bob = create_user(2)

    affiliation.focal_points.update({alice, bob})
    db.session.flush()

    assert {alice, bob} == set(affiliation.focal_points)
