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
from indico.util.user import make_user_search_token

from indico_affiliation_extras.focal_points import set_focal_points
from indico_affiliation_extras.permissions import set_focal_point_management_enabled


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _create_url(regform):
    return f'/event/{regform.event.id}/manage/registration/{regform.id}/registrations/create'


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
def test_pre_create_allows_focal_with_managed_affiliation(
    db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
):
    managed, __ = create_catalog_affiliations(dummy_regform.event)
    field = create_representation_field(dummy_regform)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    _guardrail(dummy_regform, focal, _registration_data(field, managed.id), True)


@pytest.mark.usefixtures('request_context')
def test_pre_create_rejects_focal_without_managed_affiliation(
    db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
):
    managed, other = create_catalog_affiliations(dummy_regform.event)
    field = create_representation_field(dummy_regform)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    with pytest.raises(UserValueError):
        _guardrail(dummy_regform, focal, _registration_data(field, other.id), True)


@pytest.mark.usefixtures('request_context')
def test_pre_create_does_not_block_self_service(
    db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
):
    managed, other = create_catalog_affiliations(dummy_regform.event)
    field = create_representation_field(dummy_regform)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    _guardrail(dummy_regform, focal, _registration_data(field, other.id), False)


@pytest.mark.usefixtures('request_context')
def test_pre_create_never_blocks_full_manager(
    db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
):
    managed, other = create_catalog_affiliations(dummy_regform.event)
    field = create_representation_field(dummy_regform)
    manager = create_user(3)
    dummy_regform.event.update_principal(manager, full_access=True)
    set_focal_points(managed, {manager})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    _guardrail(dummy_regform, manager, _registration_data(field, other.id), True)


@pytest.mark.usefixtures('request_context')
def test_pre_create_blocked_on_disabled_form(
    db, dummy_regform, create_regform, create_user, create_catalog_affiliations, create_representation_field
):
    managed, __ = create_catalog_affiliations(dummy_regform.event)
    form_a, form_b = dummy_regform, create_regform(dummy_regform.event, title='Form B')
    field_a = create_representation_field(form_a)
    field_b = create_representation_field(form_b)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(form_b, True)
    db.session.flush()

    _guardrail(form_b, focal, _registration_data(field_b, managed.id), True)
    with pytest.raises(UserValueError):
        _guardrail(form_a, focal, _registration_data(field_a, managed.id), True)


def test_core_create_reachable_by_focal_point(
    test_client, db, dummy_regform, create_user, create_catalog_affiliations, create_representation_field
):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    create_representation_field(dummy_regform)
    managed, __ = create_catalog_affiliations(dummy_regform.event)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    set_focal_point_management_enabled(dummy_regform, True)
    db.session.flush()

    _login(test_client, focal)
    resp = test_client.get(_create_url(dummy_regform))
    assert resp.status_code == 200


def test_core_create_denies_plain_non_manager(test_client, dummy_regform, create_user, create_catalog_affiliations):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    create_catalog_affiliations(dummy_regform.event)

    _login(test_client, create_user(2))
    resp = test_client.get(_create_url(dummy_regform))
    assert resp.status_code == 403


def test_user_search_drops_other_affiliation_users(
    test_client, app, db, dummy_regform, create_user, monkeypatch, create_catalog_affiliations
):
    monkeypatch.setitem(app.config, 'INDICO', {**app.config['INDICO'], 'ALLOW_PUBLIC_USER_SEARCH': False})
    managed, other = create_catalog_affiliations(dummy_regform.event)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    _user_with_affiliation(create_user, db, 10, managed, first_name='Bob', last_name='Shared')
    _user_with_affiliation(create_user, db, 11, other, first_name='Carol', last_name='Shared')
    db.session.flush()
    token = _search_token(app, focal)

    _login(test_client, focal)
    resp = test_client.get('/user/search/', query_string={'last_name': 'Shared', 'token': token})
    assert resp.status_code == 200
    returned_affiliation_ids = {u['affiliation_id'] for u in resp.json['users']}
    assert returned_affiliation_ids <= {managed.id}


def test_user_search_unbounded_when_public_search_allowed(
    test_client, app, db, dummy_regform, create_user, create_catalog_affiliations
):
    managed, other = create_catalog_affiliations(dummy_regform.event)
    focal = create_user(1)
    set_focal_points(managed, {focal})
    mine = _user_with_affiliation(create_user, db, 10, managed, first_name='Dan', last_name='Open')
    theirs = _user_with_affiliation(create_user, db, 11, other, first_name='Dana', last_name='Open')
    db.session.flush()
    token = _search_token(app, focal)

    _login(test_client, focal)
    resp = test_client.get('/user/search/', query_string={'last_name': 'Open', 'token': token})
    assert resp.status_code == 200
    returned_ids = {u['id'] for u in resp.json['users']}
    assert {mine.id, theirs.id} <= returned_ids


def test_user_search_unbounded_for_admin_focal_point(
    test_client, app, db, dummy_regform, create_user, monkeypatch, create_catalog_affiliations
):
    monkeypatch.setitem(app.config, 'INDICO', {**app.config['INDICO'], 'ALLOW_PUBLIC_USER_SEARCH': False})
    managed, other = create_catalog_affiliations(dummy_regform.event)
    admin = create_user(1, admin=True)
    set_focal_points(managed, {admin})
    mine = _user_with_affiliation(create_user, db, 10, managed, first_name='Erin', last_name='Admin')
    theirs = _user_with_affiliation(create_user, db, 11, other, first_name='Frank', last_name='Admin')
    db.session.flush()
    token = _search_token(app, admin)

    _login(test_client, admin)
    resp = test_client.get('/user/search/', query_string={'last_name': 'Admin', 'token': token})
    assert resp.status_code == 200
    returned_ids = {u['id'] for u in resp.json['users']}
    assert {mine.id, theirs.id} <= returned_ids


def test_settings_save_persists_focal_point_toggle(dummy_regform, app, create_representation_field):
    from indico_affiliation_extras.permissions import focal_point_management_enabled
    from indico_affiliation_extras.plugin import AffiliationExtrasPlugin

    create_representation_field(dummy_regform)
    with app.test_request_context(method='POST', data={'focal_point_management': '1'}):
        AffiliationExtrasPlugin.instance._persist_focal_point_setting(dummy_regform)
    assert focal_point_management_enabled(dummy_regform) is True

    with app.test_request_context(method='POST', data={}):
        AffiliationExtrasPlugin.instance._persist_focal_point_setting(dummy_regform)
    assert focal_point_management_enabled(dummy_regform) is False
