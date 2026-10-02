# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.focal_points import focal_event_ids, get_focal_affiliation_ids, set_focal_points
from indico_affiliation_extras.permissions import set_focal_point_management_enabled


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def test_get_focal_affiliation_ids(db, create_user):
    user = create_user(1)
    cern = Affiliation(name='CERN')
    db.session.add(cern)
    db.session.flush()
    set_focal_points(cern, {user})
    db.session.flush()

    assert get_focal_affiliation_ids(user) == {cern.id}
    assert get_focal_affiliation_ids(None) == set()


def test_focal_event_ids(
    db, dummy_regform, create_user, create_representation_field, create_representation_registration
):
    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    create_representation_registration(create_representation_field(dummy_regform), managed.id)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    assert focal_event_ids(focal) == {dummy_regform.event.id}
    assert focal_event_ids(create_user(2)) == set()

    set_focal_point_management_enabled(dummy_regform, False)
    db.session.flush()
    assert focal_event_ids(focal) == set()


def test_registration_can_manage_grants_focal_point_edit(
    db,
    dummy_regform,
    create_user,
    create_event_catalog,
    create_representation_field,
    create_representation_registration,
):
    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    create_event_catalog(dummy_regform.event, [managed])
    registration = create_representation_registration(create_representation_field(dummy_regform), managed.id)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    assert registration.can_manage(focal, 'registration_edit') is True
    assert registration.can_manage(focal, 'registration') is False
    assert registration.can_manage(create_user(2), 'registration_edit') is False
