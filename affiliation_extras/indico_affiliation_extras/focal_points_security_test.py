# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.models.focal_points import set_focal_points
from indico_affiliation_extras.permissions import set_focal_point_management_enabled


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


@pytest.fixture
def setup_focal_point(
    db, create_user, create_catalog_affiliations, create_representation_field, create_representation_registration
):
    def _setup_focal_point(regform, *, user_id=1, full_manager=False):
        managed, other = create_catalog_affiliations(regform.event)
        field = create_representation_field(regform)
        in_range = create_representation_registration(field, managed.id)
        out_range = create_representation_registration(field, other.id)
        user = create_user(user_id)
        set_focal_points(managed, {user})
        set_focal_point_management_enabled(regform, True)
        if full_manager:
            regform.event.update_principal(user, full_access=True)
        db.session.flush()
        return user, in_range, out_range

    return _setup_focal_point


def test_focal_point_bounded_to_own_affiliation(dummy_regform, setup_focal_point, get_scoped_list):
    focal, in_range, out_range = setup_focal_point(dummy_regform)

    assert in_range.can_manage(focal, 'registration_edit') is True
    assert out_range.can_manage(focal, 'registration_edit') is False
    assert in_range.can_manage(focal, 'registration') is False
    assert in_range.can_manage(focal, 'registration_checkin') is False
    assert get_scoped_list(dummy_regform, focal) == [in_range]
    assert dummy_regform.get_managed_registration_count(focal) == 1


def test_focal_point_can_moderate_own_affiliation(dummy_regform, setup_focal_point):
    focal, in_range, out_range = setup_focal_point(dummy_regform)

    assert in_range.can_manage(focal, 'registration_moderation') is True
    assert out_range.can_manage(focal, 'registration_moderation') is False


def test_focal_point_management_disabled_blocks_moderation(dummy_regform, setup_focal_point):
    focal, in_range, __ = setup_focal_point(dummy_regform)
    set_focal_point_management_enabled(dummy_regform, False)

    assert in_range.can_manage(focal, 'registration_moderation') is False


def test_genuine_moderator_also_focal_is_unrestricted(db, dummy_regform, setup_focal_point, get_scoped_list):
    focal, in_range, out_range = setup_focal_point(dummy_regform)
    dummy_regform.event.update_principal(focal, permissions={'registration_moderation'})
    db.session.flush()

    assert out_range.can_manage(focal, 'registration_moderation') is True
    assert set(get_scoped_list(dummy_regform, focal)) == {in_range, out_range}
    assert dummy_regform.is_download_blocked(focal) is False


def test_genuine_manager_also_focal_is_unrestricted(dummy_regform, setup_focal_point, get_scoped_list):
    manager, in_range, out_range = setup_focal_point(dummy_regform, user_id=3, full_manager=True)

    assert in_range.can_manage(manager, 'registration_edit') is True
    assert out_range.can_manage(manager, 'registration_edit') is True
    assert set(get_scoped_list(dummy_regform, manager)) == {in_range, out_range}
    assert dummy_regform.get_managed_registration_count(manager) == 2


def test_non_focal_user_unaffected(db, dummy_regform, create_user, setup_focal_point):
    from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

    __, in_range, out_range = setup_focal_point(dummy_regform)
    outsider = create_user(9)
    db.session.flush()

    assert in_range.can_manage(outsider, 'registration_edit') is False
    assert out_range.can_manage(outsider, 'registration_edit') is False
    assert AffiliationExtrasPlugin.instance._filter_registration_list(dummy_regform, outsider) is None


def test_focal_point_management_disabled_blocks_access(dummy_regform, setup_focal_point):
    focal, in_range, __ = setup_focal_point(dummy_regform)
    assert in_range.can_manage(focal, 'registration_edit') is True
    set_focal_point_management_enabled(dummy_regform, False)
    assert in_range.can_manage(focal, 'registration_edit') is False


def test_per_form_toggle_isolates_forms(
    db,
    dummy_regform,
    create_regform,
    create_user,
    create_event_catalog,
    create_representation_field,
    create_representation_registration,
    get_scoped_list,
):
    event = dummy_regform.event
    managed = Affiliation(name='CERN')
    db.session.add(managed)
    db.session.flush()
    create_event_catalog(event, [managed])

    form_a, form_b = dummy_regform, create_regform(event, title='Form B')
    reg_a = create_representation_registration(create_representation_field(form_a), managed.id)
    reg_b = create_representation_registration(create_representation_field(form_b), managed.id)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(form_a, True)
    set_focal_point_management_enabled(form_b, True)
    db.session.flush()

    assert reg_a.can_manage(focal, 'registration_edit') is True
    assert reg_b.can_manage(focal, 'registration_edit') is True

    set_focal_point_management_enabled(form_a, False)
    assert reg_a.can_manage(focal, 'registration_edit') is False
    assert reg_b.can_manage(focal, 'registration_edit') is True
    assert get_scoped_list(form_a, focal) == []
    assert get_scoped_list(form_b, focal) == [reg_b]


def test_focal_point_cannot_download(dummy_regform, setup_focal_point):
    focal, __, __ = setup_focal_point(dummy_regform)
    assert dummy_regform.is_download_blocked(focal) is True


def test_genuine_manager_and_outsider_can_download(db, dummy_regform, create_user, setup_focal_point):
    manager, __, __ = setup_focal_point(dummy_regform, user_id=3, full_manager=True)
    outsider = create_user(9)
    db.session.flush()
    assert dummy_regform.is_download_blocked(manager) is False
    assert dummy_regform.is_download_blocked(outsider) is False


def test_focal_point_management_disabled_allows_download(dummy_regform, setup_focal_point):
    focal, __, __ = setup_focal_point(dummy_regform)
    set_focal_point_management_enabled(dummy_regform, False)
    assert dummy_regform.is_download_blocked(focal) is False
