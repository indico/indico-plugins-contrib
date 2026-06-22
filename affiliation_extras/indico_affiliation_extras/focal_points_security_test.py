# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Security invariant for focal-point registration management. On an event with an affiliation-bearing
# registration form (focal-point management is enabled by default), a focal point is bounded to the
# registrations of their own affiliation across EVERY registration_edit path: the per-registration
# `Registration.can_manage` gate (which guards details, edit, delete and attachment download), the
# management list and the managed count. A genuine manager who is also a focal point is never
# restricted, and a non-focal user is unaffected.

from flask import session

from indico.modules.events.registration.lists import RegistrationListGenerator
from indico.modules.events.registration.models.items import PersonalDataType
from indico.modules.events.registration.models.registrations import Registration, RegistrationData, RegistrationState
from indico.modules.users.models.affiliations import Affiliation


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _affiliation_field(regform):
    return next(field for field in regform.sections[0].fields
                if field.is_field and field.personal_data_type == PersonalDataType.affiliation)


def _create_registration(db, regform, last_name, email):
    reg = Registration(first_name='Focal', last_name=last_name, state=RegistrationState.complete,
                       currency='USD', email=email, registration_form=regform)
    regform.event.registrations.append(reg)
    db.session.flush()
    return reg


def _set_affiliation(db, registration, field, affiliation_id, text='CERN'):
    db.session.add(RegistrationData(registration=registration, field_data=field.current_data,
                                    data={'id': affiliation_id, 'text': text}))
    db.session.flush()


def _scoped_list(regform, user):
    """Drive the real management list generator as the reglist RH does for ``user``."""
    session.set_session_user(user)
    return RegistrationListGenerator(regform=regform).get_list_kwargs()['registrations']


def _setup(db, regform, create_user, *, user_id=1, full_manager=False):
    """One in-range and one out-of-range registration; ``user`` is a focal point for the in-range org.

    Focal-point management is enabled by default, so there is no opt-in step.
    """
    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()
    field = _affiliation_field(regform)
    in_range = _create_registration(db, regform, 'Mine', 'mine@example.test')
    out_range = _create_registration(db, regform, 'Theirs', 'theirs@example.test')
    _set_affiliation(db, in_range, field, managed.id)
    _set_affiliation(db, out_range, field, other.id, text='MIT')
    user = create_user(user_id)
    managed.focal_points.add(user)
    if full_manager:
        regform.event.update_principal(user, full_access=True)
    db.session.flush()
    return user, in_range, out_range


def test_focal_point_bounded_to_own_affiliation(db, dummy_regform, create_user, request_context):
    focal, in_range, out_range = _setup(db, dummy_regform, create_user)

    # per-registration gate (guards details, edit, delete and attachment download)
    assert in_range.can_manage(focal, 'registration_edit') is True
    assert out_range.can_manage(focal, 'registration_edit') is False
    # edit only: never full management, moderation or check-in
    assert in_range.can_manage(focal, 'registration') is False
    assert in_range.can_manage(focal, 'registration_moderation') is False
    assert in_range.can_manage(focal, 'registration_checkin') is False
    # list rows and managed count are scoped to the in-range registration
    assert _scoped_list(dummy_regform, focal) == [in_range]
    assert dummy_regform.get_managed_registration_count(focal) == 1


def test_genuine_manager_also_focal_is_unrestricted(db, dummy_regform, create_user, request_context):
    manager, in_range, out_range = _setup(db, dummy_regform, create_user, user_id=3, full_manager=True)

    assert in_range.can_manage(manager, 'registration_edit') is True
    assert out_range.can_manage(manager, 'registration_edit') is True
    assert set(_scoped_list(dummy_regform, manager)) == {in_range, out_range}
    assert dummy_regform.get_managed_registration_count(manager) == 2


def test_non_focal_user_unaffected(db, dummy_regform, create_user, request_context):
    from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

    __, in_range, out_range = _setup(db, dummy_regform, create_user)
    outsider = create_user(9)
    db.session.flush()

    assert in_range.can_manage(outsider, 'registration_edit') is False
    assert out_range.can_manage(outsider, 'registration_edit') is False
    # the plugin does not scope a non-focal user, so stock behaviour is unchanged for them
    assert AffiliationExtrasPlugin.instance._filter_registration_list(dummy_regform, outsider) is None


def test_focal_point_management_disabled_blocks_access(db, dummy_regform, create_user, request_context):
    from indico_affiliation_extras.settings import event_settings

    focal, in_range, __ = _setup(db, dummy_regform, create_user)
    # enabled by default: the focal point manages their in-range registration
    assert in_range.can_manage(focal, 'registration_edit') is True
    # a full manager turns focal-point management off for this event -> the focal point loses access
    event_settings.set(dummy_regform.event, 'focal_point_management_enabled', False)
    assert in_range.can_manage(focal, 'registration_edit') is False
