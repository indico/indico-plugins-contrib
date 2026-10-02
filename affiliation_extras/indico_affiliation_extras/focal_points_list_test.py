# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.models.items import PersonalDataType
from indico.modules.events.registration.models.registrations import Registration, RegistrationData

from indico_affiliation_extras.focal_points import focal_list_criterion, set_focal_points
from indico_affiliation_extras.permissions import set_focal_point_management_enabled


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _reglist_url(regform):
    return f'/event/{regform.event.id}/manage/registration/{regform.id}/registrations/'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _affiliation_field(regform):
    return next(
        field
        for field in regform.sections[0].fields
        if field.is_field and field.personal_data_type == PersonalDataType.affiliation
    )


def _set_affiliation(db, registration, field, affiliation_id):
    db.session.add(
        RegistrationData(
            registration=registration,
            field_data=field.current_data,
            data={'id': affiliation_id, 'text': 'CERN'},
        )
    )
    db.session.flush()


def _focal_query(regform, user):
    return Registration.query.with_parent(regform).filter(focal_list_criterion(user, regform.event)).all()


def test_reglist_reachable_by_focal_point(
    test_client, db, dummy_regform, create_user, create_representation_field, create_catalog_affiliations
):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    create_representation_field(dummy_regform)
    managed, __ = create_catalog_affiliations(dummy_regform.event)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    _login(test_client, focal)
    resp = test_client.get(_reglist_url(dummy_regform))
    assert resp.status_code == 200


def test_reglist_denies_plain_non_manager(test_client, dummy_regform, create_user, create_catalog_affiliations):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    create_catalog_affiliations(dummy_regform.event)

    _login(test_client, create_user(2))
    resp = test_client.get(_reglist_url(dummy_regform))
    assert resp.status_code == 403


def test_reglist_reachable_by_manager(test_client, db, dummy_regform, dummy_user):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    db.session.flush()

    _login(test_client, dummy_user)
    resp = test_client.get(_reglist_url(dummy_regform))
    assert resp.status_code == 200


def test_criterion_matches_representation_field(
    db,
    dummy_regform,
    create_user,
    create_catalog_affiliations,
    create_representation_field,
    create_representation_registration,
):
    managed, other = create_catalog_affiliations(dummy_regform.event)
    field = create_representation_field(dummy_regform)
    mine = create_representation_registration(field, managed.id)
    create_representation_registration(field, other.id)
    create_representation_registration(field, None)

    focal = create_user(1)
    set_focal_points(managed, {focal})
    db.session.flush()

    assert _focal_query(dummy_regform, focal) == [mine]


def test_criterion_matches_representation_only(
    db,
    dummy_regform,
    create_user,
    create_registration,
    create_catalog_affiliations,
    create_representation_field,
    create_representation_registration,
):
    managed, __ = create_catalog_affiliations(dummy_regform.event)
    via_affiliation = create_registration(create_user(5), dummy_regform)
    _set_affiliation(db, via_affiliation, _affiliation_field(dummy_regform), managed.id)
    via_representation = create_representation_registration(create_representation_field(dummy_regform), managed.id)

    focal = create_user(1)
    set_focal_points(managed, {focal})
    db.session.flush()

    assert _focal_query(dummy_regform, focal) == [via_representation]


def test_criterion_empty_for_non_focal(
    db,
    dummy_regform,
    create_user,
    create_catalog_affiliations,
    create_representation_field,
    create_representation_registration,
):
    managed, other = create_catalog_affiliations(dummy_regform.event)
    create_representation_registration(create_representation_field(dummy_regform), managed.id)

    non_focal = create_user(2)
    set_focal_points(other, {non_focal})
    db.session.flush()

    assert _focal_query(dummy_regform, non_focal) == []


def test_manager_handler_unrestricted(db, dummy_regform, create_user, create_catalog_affiliations):
    from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

    managed, __ = create_catalog_affiliations(dummy_regform.event)
    manager = create_user(3)
    set_focal_points(managed, {manager})
    dummy_regform.event.update_principal(manager, full_access=True)
    db.session.flush()

    assert AffiliationExtrasPlugin.instance._filter_registration_list(dummy_regform, manager) is None


def test_generator_scopes_list_for_focal_point(
    db,
    dummy_regform,
    create_user,
    create_catalog_affiliations,
    create_representation_field,
    create_representation_registration,
    get_scoped_list,
):
    managed, other = create_catalog_affiliations(dummy_regform.event)
    field = create_representation_field(dummy_regform)
    mine = create_representation_registration(field, managed.id)
    create_representation_registration(field, other.id)

    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    assert get_scoped_list(dummy_regform, focal) == [mine]


def test_generator_unrestricted_for_manager(
    db,
    dummy_regform,
    create_user,
    create_catalog_affiliations,
    create_representation_field,
    create_representation_registration,
    get_scoped_list,
):
    managed, other = create_catalog_affiliations(dummy_regform.event)
    field = create_representation_field(dummy_regform)
    mine = create_representation_registration(field, managed.id)
    theirs = create_representation_registration(field, other.id)

    manager = create_user(3)
    set_focal_points(managed, {manager})
    dummy_regform.event.update_principal(manager, full_access=True)
    db.session.flush()

    assert set(get_scoped_list(dummy_regform, manager)) == {mine, theirs}


def test_criterion_admin_override_intact(
    db,
    dummy_regform,
    create_user,
    create_catalog_affiliations,
    create_representation_field,
    create_representation_registration,
):
    managed, __ = create_catalog_affiliations(dummy_regform.event)
    create_representation_registration(create_representation_field(dummy_regform), managed.id)

    admin = create_user(7, admin=True)
    db.session.flush()

    assert _focal_query(dummy_regform, admin) == []
