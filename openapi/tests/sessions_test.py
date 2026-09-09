# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode


@pytest.fixture
def token_headers(dummy_personal_token):
    dummy_personal_token.scopes = ['read:everything']
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


@pytest.fixture
def outsider_headers(db, dummy_personal_token, create_user):
    dummy_personal_token.user = create_user(42)
    dummy_personal_token.scopes = ['read:everything']
    db.session.flush()
    return {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}


def test_session_details(dummy_event, dummy_session, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_session.id
    assert resp.json['title'] == dummy_session.title
    assert resp.json['friendly_id'] == dummy_session.friendly_id
    assert resp.json['text_color'] == f'#{dummy_session.colors.text}'
    assert resp.json['blocks'] == []


def test_session_details_include_blocks(dummy_event, dummy_session, dummy_session_block, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}', headers=token_headers)
    assert resp.status_code == 200
    assert [b['id'] for b in resp.json['blocks']] == [dummy_session_block.id]
    assert resp.json['blocks'][0]['duration'] == dummy_session_block.duration.total_seconds()


def test_session_list(dummy_event, dummy_session, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions', headers=token_headers)
    assert resp.status_code == 200
    assert [s['id'] for s in resp.json['results']] == [dummy_session.id]


def test_session_denied_without_access(db, dummy_event, dummy_session, outsider_headers, test_client):
    dummy_session.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions/{dummy_session.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_session_list_hides_protected_sessions(db, dummy_event, dummy_session, create_session, outsider_headers,
                                               test_client):
    dummy_session.protection_mode = ProtectionMode.protected
    public = create_session(dummy_event, 'Public session')
    db.session.flush()
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/sessions', headers=outsider_headers)
    assert resp.status_code == 200
    assert [s['id'] for s in resp.json['results']] == [public.id]


def test_session_of_another_event_is_not_found(dummy_session, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/sessions/{dummy_session.id}', headers=token_headers)
    assert resp.status_code == 404
