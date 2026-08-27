# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.models.focal_points import get_focal_points, set_focal_points


def test_focal_points_relationship_both_directions(db, create_user):
    user = create_user(123)
    affiliation = Affiliation(name='CERN')
    db.session.add(affiliation)
    db.session.flush()

    set_focal_points(affiliation, {user})
    db.session.flush()

    assert user in get_focal_points(affiliation)
    assert affiliation in {entry.affiliation for entry in user.focal_point_entries}


def test_focal_point_for_multiple_affiliations(db, create_user):
    user = create_user(123)
    cern = Affiliation(name='CERN')
    mit = Affiliation(name='MIT')
    db.session.add_all([cern, mit])
    db.session.flush()

    set_focal_points(cern, {user})
    set_focal_points(mit, {user})
    db.session.flush()

    assert {cern, mit} <= {entry.affiliation for entry in user.focal_point_entries}
    assert user in get_focal_points(cern)
    assert user in get_focal_points(mit)


def test_affiliation_with_multiple_focal_points(db, create_user):
    affiliation = Affiliation(name='CERN')
    db.session.add(affiliation)
    db.session.flush()
    alice = create_user(1)
    bob = create_user(2)

    set_focal_points(affiliation, {alice, bob})
    db.session.flush()

    assert {alice, bob} == get_focal_points(affiliation)
