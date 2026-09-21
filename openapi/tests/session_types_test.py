# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.events.sessions.models.types import SessionType


@pytest.fixture
def create_session_type(db, dummy_event):
    def _create(name, **kwargs):
        session_type = SessionType(event=dummy_event, name=name, **kwargs)
        db.session.add(session_type)
        db.session.flush()
        return session_type

    return _create


@pytest.fixture
def poster_session_type(create_session_type):
    return create_session_type('Poster session', code='POS', is_poster=True)


def test_session_type_details(dummy_event, poster_session_type, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/session-types/{poster_session_type.id}',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {'id': poster_session_type.id, 'event_id': dummy_event.id, 'name': 'Poster session',
                         'code': 'POS', 'is_poster': True}


def test_session_type_list_is_sorted_by_name(dummy_event, poster_session_type, create_session_type, token_headers,
                                             test_client):
    plenary = create_session_type('Plenary')
    breakout = create_session_type('breakout')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/session-types', headers=token_headers)
    assert resp.status_code == 200
    assert [t['id'] for t in resp.json['results']] == [breakout.id, plenary.id, poster_session_type.id]


def test_session_type_denied_without_event_access(db, dummy_event, poster_session_type, outsider_headers,
                                                  test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/session-types/{poster_session_type.id}',
                           headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/session-types', headers=outsider_headers)
    assert resp.status_code == 403


def test_session_type_of_another_event_is_not_found(db, poster_session_type, create_event, token_headers,
                                                    test_client):
    other = create_event()
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{other.id}/session-types/{poster_session_type.id}',
                          headers=token_headers)
    assert resp.status_code == 404


def test_session_type_matches_the_session_it_is_used_by(db, dummy_event, dummy_session, poster_session_type,
                                                        token_headers, test_client):
    # the current API only names the type of a session; its definition is in an HTML dialog
    dummy_session.type = poster_session_type
    db.session.flush()
    session = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}',
                              headers=token_headers).json
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/session-types/{poster_session_type.id}',
                          headers=token_headers).json
    assert (new['name'], new['is_poster']) == (session['type'], session['is_poster'])
