# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import timedelta

import pytest

from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.util.date_time import now_utc


@pytest.fixture
def make_reg(db, create_event, create_regform):
    def _make(user, end_offset, title='evt'):
        now = now_utc(exact=False)
        end_dt = now + end_offset
        start_dt = end_dt - timedelta(hours=1)
        event = create_event(start_dt=start_dt, end_dt=end_dt, title=title)
        regform = create_regform(event)
        reg = Registration(
            registration_form=regform,
            first_name='Guinea',
            last_name='Pig',
            currency='USD',
            email=user.email,
            user=user,
            state=RegistrationState.complete,
        )
        event.registrations.append(reg)
        db.session.flush()
        return reg

    return _make


def _login(test_client, user):
    with test_client.session_transaction() as sess:
        sess.set_session_user(user)


@pytest.mark.usefixtures('no_csrf_check')
def test_anonymous_cannot_access(test_client, dummy_user):
    resp = test_client.get(f'/user/{dummy_user.id}/my-registrations/')
    # RHProtected → redirects to login (302) or 403; not 200
    assert resp.status_code != 200


@pytest.mark.usefixtures('no_csrf_check')
def test_authenticated_user_sees_own_dashboard(test_client, dummy_user, make_reg):
    make_reg(dummy_user, timedelta(hours=1), title='soon')
    make_reg(dummy_user, -timedelta(days=2), title='gone')
    _login(test_client, dummy_user)
    resp = test_client.get(f'/user/{dummy_user.id}/my-registrations/')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'soon' in body
    assert 'gone' in body


@pytest.mark.usefixtures('no_csrf_check')
def test_url_without_user_id_resolves_to_session_user(test_client, dummy_user, make_reg):
    make_reg(dummy_user, timedelta(hours=1), title='self')
    _login(test_client, dummy_user)
    resp = test_client.get('/user/my-registrations/')
    assert resp.status_code == 200
    assert 'self' in resp.get_data(as_text=True)


@pytest.mark.usefixtures('no_csrf_check')
def test_non_admin_cannot_access_other_user(test_client, dummy_user, create_user):
    other = create_user(42)
    _login(test_client, dummy_user)
    resp = test_client.get(f'/user/{other.id}/my-registrations/')
    assert resp.status_code == 403


@pytest.mark.usefixtures('no_csrf_check')
def test_admin_can_access_other_user(test_client, create_user, dummy_user, make_reg):
    make_reg(dummy_user, timedelta(hours=1), title='owned')
    admin = create_user(100, admin=True)
    _login(test_client, admin)
    resp = test_client.get(f'/user/{dummy_user.id}/my-registrations/')
    assert resp.status_code == 200
    assert 'owned' in resp.get_data(as_text=True)


@pytest.mark.usefixtures('no_csrf_check')
def test_page_beyond_pages_clamps(test_client, dummy_user, make_reg):
    make_reg(dummy_user, timedelta(hours=1))
    _login(test_client, dummy_user)
    resp = test_client.get(f'/user/{dummy_user.id}/my-registrations/?upcoming_page=999')
    assert resp.status_code == 200
