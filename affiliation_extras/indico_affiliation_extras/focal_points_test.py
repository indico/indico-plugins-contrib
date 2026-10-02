# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import timedelta

import pytest

from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.util import get_linked_events, merge_users
from indico.util.date_time import now_utc

from indico_affiliation_extras.focal_points import focal_event_ids, get_focal_affiliation_ids, set_focal_points
from indico_affiliation_extras.permissions import set_focal_point_management_enabled


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


@pytest.fixture
def create_focal_event(
    create_event,
    create_regform,
    create_event_catalog,
    create_representation_field,
    create_representation_registration,
):
    def _create_focal_event(affiliation, **kwargs):
        event = create_event(**kwargs)
        regform = create_regform(event)
        create_event_catalog(event, [affiliation])
        create_representation_registration(create_representation_field(regform), affiliation.id)
        set_focal_point_management_enabled(regform, True)
        return event

    return _create_focal_event


def test_get_focal_affiliation_ids(db, create_user):
    user = create_user(1)
    cern = Affiliation(name='CERN')
    db.session.add(cern)
    db.session.flush()
    set_focal_points(cern, {user})
    db.session.flush()

    assert get_focal_affiliation_ids(user) == {cern.id}
    assert get_focal_affiliation_ids(None) == set()


def test_merge_users_moves_focal_points(db, create_user):
    source, target = create_user(1), create_user(2)
    cern, mit, epfl = Affiliation(name='CERN'), Affiliation(name='MIT'), Affiliation(name='EPFL')
    db.session.add_all([cern, mit, epfl])
    db.session.flush()
    set_focal_points(cern, {source})
    set_focal_points(mit, {source, target})
    set_focal_points(epfl, {target})
    db.session.flush()

    merge_users(source, target)

    assert get_focal_affiliation_ids(target) == {cern.id, mit.id, epfl.id}
    assert get_focal_affiliation_ids(source) == set()


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


def test_linked_events_scoped_by_end_date(db, create_user, create_focal_event):
    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    now = now_utc()
    ongoing = create_focal_event(managed, start_dt=now - timedelta(days=30), end_dt=now + timedelta(days=1))
    create_focal_event(managed, start_dt=now - timedelta(days=60), end_dt=now - timedelta(days=30))
    focal = create_user(1)
    set_focal_points(managed, {focal})
    db.session.flush()

    assert set(get_linked_events(focal, now - timedelta(days=7))) == {ongoing}


def test_linked_events_not_truncated(db, create_user, create_focal_event):
    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    events = {create_focal_event(managed) for __ in range(30)}
    focal = create_user(1)
    set_focal_points(managed, {focal})
    db.session.flush()

    assert set(get_linked_events(focal)) == events


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
