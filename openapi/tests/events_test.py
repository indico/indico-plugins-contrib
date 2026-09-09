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


def test_event_details(dummy_event, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_event.id
    assert resp.json['title'] == dummy_event.title
    assert resp.json['timezone'] == dummy_event.timezone


def test_event_details_denied_without_access(dummy_event, dummy_personal_token, create_user, db, test_client):
    outsider = create_user(42)
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = ['read:everything']
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}', headers=headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_event_details_denied_without_scope(dummy_event, dummy_personal_token, test_client):
    dummy_personal_token.scopes = ['read:user']
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}', headers=headers)
    assert resp.status_code == 403


def test_event_list(dummy_event, token_headers, test_client):
    resp = test_client.get('/api/v1/events', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['count'] == 1
    assert resp.json['next_offset'] is None
    assert resp.json['results'][0]['id'] == dummy_event.id


def test_event_list_hides_inaccessible_events(dummy_event, dummy_personal_token, create_user, db, test_client):
    outsider = create_user(42)
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = ['read:everything']
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get('/api/v1/events', headers=headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_event_list_paginates(create_event, token_headers, test_client):
    events = [create_event() for _ in range(3)]
    resp = test_client.get('/api/v1/events?limit=2', headers=token_headers)
    assert resp.json['count'] == 2
    assert resp.json['next_offset'] == 2
    resp = test_client.get('/api/v1/events?limit=2&offset=2', headers=token_headers)
    assert resp.json['count'] == 1
    assert resp.json['next_offset'] is None
    listed = {e['id'] for e in resp.json['results']}
    assert listed <= {e.id for e in events}


def test_event_list_filters_by_category(dummy_event, create_category, create_event, token_headers, test_client):
    other = create_event(category=create_category(1))
    resp = test_client.get(f'/api/v1/events?category_id={dummy_event.category_id}', headers=token_headers)
    listed = {e['id'] for e in resp.json['results']}
    assert dummy_event.id in listed
    assert other.id not in listed
