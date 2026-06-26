# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest
from flask import session

from indico.core.errors import UserValueError
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.users.models.affiliations import Affiliation
from indico.util.user import make_user_search_token

from indico_affiliation_extras.fields import RepresentationField
from indico_affiliation_extras.models.catalogs import AffiliationCatalog
from indico_affiliation_extras.models.lists import AffiliationList
from indico_affiliation_extras.settings import event_settings


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _create_url(regform):
    return f'/event/{regform.event.id}/manage/registration/{regform.id}/registrations/create'


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


def _add_event_catalog(db, event, affiliations):
    catalog = AffiliationCatalog(name='Catalog', event=event)
    db.session.add(catalog)
    db.session.flush()
    affiliation_list = AffiliationList(catalog=catalog, name='Representatives', position=1, is_enabled=True)
    affiliation_list.affiliations.update(affiliations)
    db.session.add(affiliation_list)
    db.session.flush()
    event_settings.set(event, 'default_catalog_id', catalog.id)


def _make_affiliations(db, event):
    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()
    _add_event_catalog(db, event, [managed, other])
    return managed, other


def _user_with_affiliation(create_user, db, id_, affiliation, **kwargs):
    user = create_user(id_, **kwargs)
    user.affiliation_link = affiliation
    db.session.flush()
    return user


def _registration_data(field, affiliation_id, email='new@example.test'):
    return {
        'email': email,
        'first_name': 'New',
        'last_name': 'Person',
        field.html_field_name: {'affiliation': {'id': affiliation_id, 'text': 'CERN'}},
    }


def _guardrail(regform, user, data, management):
    from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

    AffiliationExtrasPlugin.instance._check_registration_pre_create(regform, user, data, management)


def _search_token(app, user):
    with app.test_request_context():
        session.set_session_user(user)
        return make_user_search_token()


@pytest.mark.usefixtures('request_context')
def test_pre_create_allows_focal_with_managed_affiliation(db, dummy_regform, create_user):
    managed, __ = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    _guardrail(dummy_regform, focal, _registration_data(field, managed.id), True)


@pytest.mark.usefixtures('request_context')
def test_pre_create_rejects_focal_without_managed_affiliation(db, dummy_regform, create_user):
    managed, other = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    with pytest.raises(UserValueError):
        _guardrail(dummy_regform, focal, _registration_data(field, other.id), True)


@pytest.mark.usefixtures('request_context')
def test_pre_create_does_not_block_self_service(db, dummy_regform, create_user):
    managed, other = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    _guardrail(dummy_regform, focal, _registration_data(field, other.id), False)


@pytest.mark.usefixtures('request_context')
def test_pre_create_never_blocks_full_manager(db, dummy_regform, create_user):
    managed, other = _make_affiliations(db, dummy_regform.event)
    field = _add_representation_field(db, dummy_regform)
    manager = create_user(3)
    dummy_regform.event.update_principal(manager, full_access=True)
    managed.focal_points.add(manager)
    db.session.flush()

    _guardrail(dummy_regform, manager, _registration_data(field, other.id), True)


@pytest.mark.usefixtures('request_context')
def test_pre_create_blocked_on_disabled_form(db, dummy_regform, create_regform, create_user):
    from indico_affiliation_extras.permissions import set_focal_point_management_enabled

    managed, __ = _make_affiliations(db, dummy_regform.event)
    form_a, form_b = dummy_regform, create_regform(dummy_regform.event, title='Form B')
    field_a = _add_representation_field(db, form_a)
    field_b = _add_representation_field(db, form_b)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()
    set_focal_point_management_enabled(form_a, False)

    _guardrail(form_b, focal, _registration_data(field_b, managed.id), True)
    with pytest.raises(UserValueError):
        _guardrail(form_a, focal, _registration_data(field_a, managed.id), True)


def test_core_create_form_reachable_by_focal_point(test_client, db, dummy_regform, create_user):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    _add_representation_field(db, dummy_regform)
    managed, __ = _make_affiliations(db, dummy_regform.event)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    _login(test_client, focal)
    resp = test_client.get(_create_url(dummy_regform))
    assert resp.status_code != 403


def test_core_create_post_reachable_by_focal_point(test_client, db, dummy_regform, create_user, no_csrf_check):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    _add_representation_field(db, dummy_regform)
    managed, __ = _make_affiliations(db, dummy_regform.event)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    _login(test_client, focal)
    resp = test_client.post(_create_url(dummy_regform), json={})
    assert resp.status_code != 403


def test_core_create_denies_plain_non_manager(test_client, db, dummy_regform, create_user):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    _make_affiliations(db, dummy_regform.event)

    _login(test_client, create_user(2))
    resp = test_client.get(_create_url(dummy_regform))
    assert resp.status_code == 403


def test_user_search_returns_only_focal_affiliation_users(test_client, app, db, dummy_regform, create_user,
                                                          monkeypatch):
    monkeypatch.setitem(app.config, 'INDICO', {**app.config['INDICO'], 'ALLOW_PUBLIC_USER_SEARCH': False})
    managed, other = _make_affiliations(db, dummy_regform.event)
    focal = create_user(1)
    managed.focal_points.add(focal)
    mine = _user_with_affiliation(create_user, db, 10, managed, first_name='Alice', last_name='Managed')
    theirs = _user_with_affiliation(create_user, db, 11, other, first_name='Alice', last_name='Other')
    db.session.flush()
    token = _search_token(app, focal)

    _login(test_client, focal)
    resp = test_client.get('/user/search/', query_string={'last_name': 'Managed', 'token': token})
    assert resp.status_code == 200
    returned_ids = {u['id'] for u in resp.json['users']}
    assert mine.id in returned_ids
    assert theirs.id not in returned_ids


def test_user_search_drops_other_affiliation_users(test_client, app, db, dummy_regform, create_user, monkeypatch):
    monkeypatch.setitem(app.config, 'INDICO', {**app.config['INDICO'], 'ALLOW_PUBLIC_USER_SEARCH': False})
    managed, other = _make_affiliations(db, dummy_regform.event)
    focal = create_user(1)
    managed.focal_points.add(focal)
    _user_with_affiliation(create_user, db, 10, managed, first_name='Bob', last_name='Shared')
    _user_with_affiliation(create_user, db, 11, other, first_name='Carol', last_name='Shared')
    db.session.flush()
    token = _search_token(app, focal)

    _login(test_client, focal)
    resp = test_client.get('/user/search/', query_string={'last_name': 'Shared', 'token': token})
    assert resp.status_code == 200
    returned_affiliation_ids = {u['affiliation_id'] for u in resp.json['users']}
    assert returned_affiliation_ids <= {managed.id}


def test_user_search_unbounded_when_public_search_allowed(test_client, app, db, dummy_regform, create_user):
    managed, other = _make_affiliations(db, dummy_regform.event)
    focal = create_user(1)
    managed.focal_points.add(focal)
    mine = _user_with_affiliation(create_user, db, 10, managed, first_name='Dan', last_name='Open')
    theirs = _user_with_affiliation(create_user, db, 11, other, first_name='Dana', last_name='Open')
    db.session.flush()
    token = _search_token(app, focal)

    _login(test_client, focal)
    resp = test_client.get('/user/search/', query_string={'last_name': 'Open', 'token': token})
    assert resp.status_code == 200
    returned_ids = {u['id'] for u in resp.json['users']}
    assert {mine.id, theirs.id} <= returned_ids


def _toggle_url(regform):
    return (f'/event/{regform.event.id}/manage/affiliation-extras/'
            f'registration/{regform.id}/focal-point-management')


def test_toggle_endpoint_denies_focal_point(test_client, db, dummy_regform, create_user, no_csrf_check):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    _add_representation_field(db, dummy_regform)
    managed, __ = _make_affiliations(db, dummy_regform.event)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    _login(test_client, focal)
    resp = test_client.post(_toggle_url(dummy_regform), data={'enabled': '0'})
    assert resp.status_code == 403


def test_toggle_endpoint_allows_manager_and_flips_flag(test_client, db, dummy_regform, dummy_user, no_csrf_check):
    from indico_affiliation_extras.permissions import focal_point_management_enabled

    set_feature_enabled(dummy_regform.event, 'registration', True)
    _add_representation_field(db, dummy_regform)
    dummy_regform.event.update_principal(dummy_user, full_access=True)
    db.session.flush()

    _login(test_client, dummy_user)
    resp = test_client.post(_toggle_url(dummy_regform), data={'enabled': '0'})
    assert resp.status_code == 200
    assert resp.json['enabled'] is False
    assert focal_point_management_enabled(dummy_regform) is False
