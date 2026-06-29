# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from flask import session

from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.lists import RegistrationListGenerator
from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.events.registration.models.items import PersonalDataType
from indico.modules.events.registration.models.registrations import Registration, RegistrationData, RegistrationState
from indico.modules.users.models.affiliations import Affiliation

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.focal_points import focal_list_criterion
from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.permissions import set_focal_point_management_enabled
from indico_affiliation_extras.settings import event_settings


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _reglist_url(regform):
    return f'/event/{regform.event.id}/manage/registration/{regform.id}/registrations/'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _affiliation_field(regform):
    return next(field for field in regform.sections[0].fields
                if field.is_field and field.personal_data_type == PersonalDataType.affiliation)


def _add_representation_field(db, regform):
    field = RegistrationFormField(
        input_type=RepresentationField.name,
        title='Representation',
        parent=regform.sections[0],
        registration_form=regform,
    )
    field.data = {}
    field.versioned_data = {}
    db.session.add(field)
    db.session.flush()
    return field


def _create_registration(db, regform, last_name, email):
    reg = Registration(
        first_name='Focal',
        last_name=last_name,
        state=RegistrationState.complete,
        currency='USD',
        email=email,
        registration_form=regform,
    )
    regform.event.registrations.append(reg)
    db.session.flush()
    return reg


def _set_affiliation(db, registration, field, affiliation_id, text='CERN'):
    db.session.add(RegistrationData(
        registration=registration,
        field_data=field.current_data,
        data={'id': affiliation_id, 'text': text},
    ))
    db.session.flush()


def _set_representation(db, registration, field, affiliation_id, text='CERN'):
    db.session.add(RegistrationData(
        registration=registration,
        field_data=field.current_data,
        data={
            'representation_id': 1,
            'representation_name': 'Delegates',
            'affiliation': {'id': affiliation_id, 'text': text},
        },
    ))
    db.session.flush()


def _add_event_catalog(db, event, affiliations):
    catalog = AffiliationCatalog(name='Catalog', event=event)
    db.session.add(catalog)
    db.session.flush()
    affiliation_list = AffiliationList(catalog=catalog, name='Representatives', position=1, is_enabled=True)
    affiliation_list.affiliations.update(affiliations)
    db.session.add(affiliation_list)
    db.session.flush()
    event_settings.set(event, 'default_catalog_id', catalog.id)
    return affiliation_list


def _make_affiliations(db, event):
    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()
    _add_event_catalog(db, event, [managed, other])
    return managed, other


def _focal_query(regform, user):
    return Registration.query.with_parent(regform).filter(focal_list_criterion(user, regform.event)).all()


def _scoped_list(regform, user):
    session.set_session_user(user)
    return RegistrationListGenerator(regform=regform).get_list_kwargs()['registrations']


def test_reglist_reachable_by_focal_point(test_client, db, dummy_regform, create_user):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    _add_representation_field(db, dummy_regform)
    managed, __ = _make_affiliations(db, dummy_regform.event)
    focal = create_user(1)
    managed.focal_points.add(focal)
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    _login(test_client, focal)
    resp = test_client.get(_reglist_url(dummy_regform))
    assert resp.status_code == 200


def test_reglist_denies_plain_non_manager(test_client, db, dummy_regform, create_user):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    _make_affiliations(db, dummy_regform.event)

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


def test_criterion_matches_representation_field(db, dummy_regform, create_user):
    managed, other = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    mine = _create_registration(db, dummy_regform, 'Mine', 'mine@example.test')
    theirs = _create_registration(db, dummy_regform, 'Theirs', 'theirs@example.test')
    free_text = _create_registration(db, dummy_regform, 'Free', 'free@example.test')
    _set_representation(db, mine, field, managed.id)
    _set_representation(db, theirs, field, other.id, text='MIT')
    _set_representation(db, free_text, field, None, text='Some University')

    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    assert _focal_query(dummy_regform, focal) == [mine]


def test_criterion_ignores_affiliation_field(db, dummy_regform, create_user):
    managed, __ = _make_affiliations(db, dummy_regform.event)
    field = _affiliation_field(dummy_regform)
    mine = _create_registration(db, dummy_regform, 'Mine', 'mine@example.test')
    _set_affiliation(db, mine, field, managed.id)

    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    assert _focal_query(dummy_regform, focal) == []


def test_criterion_matches_representation_only(db, dummy_regform, create_user):
    managed, __ = _make_affiliations(db, dummy_regform.event)
    affiliation_field = _affiliation_field(dummy_regform)
    representation_field = _add_representation_field(db, dummy_regform)
    via_affiliation = _create_registration(db, dummy_regform, 'Aff', 'aff@example.test')
    via_representation = _create_registration(db, dummy_regform, 'Rep', 'rep@example.test')
    _set_affiliation(db, via_affiliation, affiliation_field, managed.id)
    _set_representation(db, via_representation, representation_field, managed.id)

    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    assert _focal_query(dummy_regform, focal) == [via_representation]


def test_criterion_empty_for_non_focal(db, dummy_regform, create_user):
    managed, other = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    reg = _create_registration(db, dummy_regform, 'Mine', 'mine@example.test')
    _set_representation(db, reg, field, managed.id)

    non_focal = create_user(2)
    other.focal_points.add(non_focal)
    db.session.flush()

    assert _focal_query(dummy_regform, non_focal) == []


def test_manager_handler_unrestricted(db, dummy_regform, create_user):
    from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

    managed, __ = _make_affiliations(db, dummy_regform.event)
    manager = create_user(3)
    managed.focal_points.add(manager)
    dummy_regform.event.update_principal(manager, full_access=True)
    db.session.flush()

    assert AffiliationExtrasPlugin.instance._filter_registration_list(dummy_regform, manager) is None


def test_focal_handler_returns_criterion(db, dummy_regform, create_user):
    from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

    managed, __ = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    mine = _create_registration(db, dummy_regform, 'Mine', 'mine@example.test')
    _set_representation(db, mine, field, managed.id)

    focal = create_user(1)
    managed.focal_points.add(focal)
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    criterion = AffiliationExtrasPlugin.instance._filter_registration_list(dummy_regform, focal)
    assert criterion is not None
    assert Registration.query.with_parent(dummy_regform).filter(criterion).all() == [mine]


def test_generator_scopes_list_for_focal_point(db, dummy_regform, create_user, request_context):
    managed, other = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    mine = _create_registration(db, dummy_regform, 'Mine', 'mine@example.test')
    theirs = _create_registration(db, dummy_regform, 'Theirs', 'theirs@example.test')
    _set_representation(db, mine, field, managed.id)
    _set_representation(db, theirs, field, other.id, text='MIT')

    focal = create_user(1)
    managed.focal_points.add(focal)
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    assert _scoped_list(dummy_regform, focal) == [mine]


def test_generator_unrestricted_for_manager(db, dummy_regform, create_user, request_context):
    managed, other = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    mine = _create_registration(db, dummy_regform, 'Mine', 'mine@example.test')
    theirs = _create_registration(db, dummy_regform, 'Theirs', 'theirs@example.test')
    _set_representation(db, mine, field, managed.id)
    _set_representation(db, theirs, field, other.id, text='MIT')

    manager = create_user(3)
    managed.focal_points.add(manager)
    dummy_regform.event.update_principal(manager, full_access=True)
    db.session.flush()

    assert set(_scoped_list(dummy_regform, manager)) == {mine, theirs}


def test_criterion_admin_override_intact(db, dummy_regform, create_user):
    managed, __ = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    reg = _create_registration(db, dummy_regform, 'Mine', 'mine@example.test')
    _set_representation(db, reg, field, managed.id)

    admin = create_user(7, admin=True)
    db.session.flush()

    assert _focal_query(dummy_regform, admin) == []
