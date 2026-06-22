# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

# Tests for the focal-point create flow now built on core screens: the pre-create guardrail, core's
# `RHRegistrationCreate` admitting a scoped focal point, and the user-search result filter applied
# to core's `/user/search/`. The guardrail is exercised by calling `create_registration` directly
# in a request context (the cleanest way to assert both the raise and that nothing is persisted);
# the rest is exercised over HTTP. Everything runs against real fixtures, no mocking.

import pytest
from flask import session

from indico.core.errors import UserValueError
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.models.items import PersonalDataType
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.util import create_registration
from indico.modules.users.models.affiliations import Affiliation
from indico.util.user import make_user_search_token


pytest_plugins = 'indico.modules.events.registration.testing.fixtures'


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


def _create_url(regform):
    return f'/event/{regform.event.id}/manage/registration/{regform.id}/registrations/create'


def _affiliation_field(regform):
    return next(field for field in regform.sections[0].fields
                if field.is_field and field.personal_data_type == PersonalDataType.affiliation)


def _make_affiliations(db):
    managed = Affiliation(name='CERN')
    other = Affiliation(name='MIT')
    db.session.add_all([managed, other])
    db.session.flush()
    return managed, other


def _user_with_affiliation(create_user, db, id_, affiliation, **kwargs):
    user = create_user(id_, **kwargs)
    user.affiliation_link = affiliation
    db.session.flush()
    return user


def _registration_data(affiliation_id, email='new@example.test'):
    """Submitted form data keyed by html_field_name, with the affiliation field populated."""
    return {
        'email': email,
        'first_name': 'New',
        'last_name': 'Person',
        'affiliation': {'id': affiliation_id, 'text': 'CERN'},
    }


def _search_token(app, user):
    """Build a user-search token for ``user`` exactly as the templates do (via session)."""
    with app.test_request_context():
        session.set_session_user(user)
        return make_user_search_token()


# -- pre-create guardrail (direct `create_registration`) --------------------------------------

@pytest.mark.usefixtures('request_context')
def test_pre_create_allows_focal_with_managed_affiliation(db, dummy_regform, create_user):
    managed, __ = _make_affiliations(db)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()
    session.set_session_user(focal)

    reg = create_registration(dummy_regform, _registration_data(managed.id),
                              management=True, notify_user=False)
    assert reg.id is not None
    assert reg in dummy_regform.registrations


@pytest.mark.usefixtures('request_context')
def test_pre_create_rejects_focal_without_managed_affiliation(db, dummy_regform, create_user):
    managed, other = _make_affiliations(db)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()
    session.set_session_user(focal)

    with pytest.raises(UserValueError):
        create_registration(dummy_regform, _registration_data(other.id),
                            management=True, notify_user=False)
    # nothing persisted: the guardrail aborts before any DB work
    assert Registration.query.with_parent(dummy_regform).count() == 0


@pytest.mark.usefixtures('request_context')
def test_pre_create_does_not_block_self_service(db, dummy_regform, create_user):
    # A focal point registering through the public form (management=False) must never be blocked,
    # even for an affiliation they do not manage.
    managed, other = _make_affiliations(db)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()
    session.set_session_user(focal)

    reg = create_registration(dummy_regform, _registration_data(other.id),
                              management=False, notify_user=False)
    assert reg.id is not None


@pytest.mark.usefixtures('request_context')
def test_pre_create_never_blocks_full_manager(db, dummy_regform, create_user):
    managed, other = _make_affiliations(db)
    manager = create_user(3)
    dummy_regform.event.update_principal(manager, full_access=True)
    db.session.flush()
    session.set_session_user(manager)

    # A full manager who is also a focal point may register for any affiliation.
    managed.focal_points.add(manager)
    db.session.flush()
    reg = create_registration(dummy_regform, _registration_data(other.id),
                              management=True, notify_user=False)
    assert reg.id is not None


# -- core create RH access (RHRegistrationCreate) ---------------------------------------------

def test_core_create_form_reachable_by_focal_point(test_client, db, dummy_regform, create_user):
    # A scoped focal point may open core's create form (GET): access passes -> not 403.
    set_feature_enabled(dummy_regform.event, 'registration', True)
    managed, __ = _make_affiliations(db)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    _login(test_client, focal)
    resp = test_client.get(_create_url(dummy_regform))
    assert resp.status_code != 403


def test_core_create_post_reachable_by_focal_point(test_client, db, dummy_regform, create_user, no_csrf_check):
    # An invalid POST reaches the handler (access passes) and fails validation -> not 403.
    set_feature_enabled(dummy_regform.event, 'registration', True)
    managed, __ = _make_affiliations(db)
    focal = create_user(1)
    managed.focal_points.add(focal)
    db.session.flush()

    _login(test_client, focal)
    resp = test_client.post(_create_url(dummy_regform), json={})
    assert resp.status_code != 403


def test_core_create_denies_plain_non_manager(test_client, db, dummy_regform, create_user):
    set_feature_enabled(dummy_regform.event, 'registration', True)
    _make_affiliations(db)

    _login(test_client, create_user(2))
    resp = test_client.get(_create_url(dummy_regform))
    assert resp.status_code == 403


# -- core user search result filter (/user/search/) -------------------------------------------

def test_user_search_returns_only_focal_affiliation_users(test_client, app, db, dummy_regform, create_user):
    managed, other = _make_affiliations(db)
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


def test_user_search_drops_other_affiliation_users(test_client, app, db, dummy_regform, create_user):
    managed, other = _make_affiliations(db)
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
