# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


import pytest

from indico.modules.users.models.affiliations import Affiliation


@pytest.fixture
def admin_headers(db, dummy_user, token_headers):
    dummy_user.is_admin = True
    db.session.flush()
    return token_headers


def test_current_user(dummy_user, token_headers, test_client):
    resp = test_client.get('/api/v1/users/me', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_user.id
    assert resp.json['email'] == dummy_user.email
    assert resp.json['full_name'] == dummy_user.full_name
    assert resp.json['identifier'] == dummy_user.identifier
    assert resp.json['is_admin'] is False


def test_current_user_requires_login(test_client):
    resp = test_client.get('/api/v1/users/me')
    assert resp.status_code == 403


def test_user_details(dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/users/{dummy_user.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_user.id
    assert resp.json['first_name'] == dummy_user.first_name
    assert resp.json['last_name'] == dummy_user.last_name


def test_user_of_someone_else_is_forbidden(outsider, token_headers, test_client):
    resp = test_client.get(f'/api/v1/users/{outsider.id}', headers=token_headers)
    assert resp.status_code == 403


def test_admin_sees_every_user(outsider, admin_headers, test_client):
    resp = test_client.get(f'/api/v1/users/{outsider.id}', headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json['email'] == outsider.email


def test_user_list_only_contains_self(dummy_user, outsider, token_headers, test_client):
    resp = test_client.get('/api/v1/users', headers=token_headers)
    assert resp.status_code == 200
    assert [u['id'] for u in resp.json['results']] == [dummy_user.id]


def test_user_list_for_admin(dummy_user, outsider, admin_headers, test_client):
    resp = test_client.get('/api/v1/users', headers=admin_headers)
    assert resp.status_code == 200
    assert {u['id'] for u in resp.json['results']} >= {dummy_user.id, outsider.id}


def test_deleted_user_is_not_found(db, outsider, admin_headers, test_client):
    outsider.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/users/{outsider.id}', headers=admin_headers)
    assert resp.status_code == 404
    resp = test_client.get('/api/v1/users', headers=admin_headers)
    assert outsider.id not in {u['id'] for u in resp.json['results']}


def test_user_affiliation(db, dummy_user, token_headers, test_client):
    affiliation = Affiliation(name='CERN', city='Geneva', country_code='CH')
    db.session.add(affiliation)
    dummy_user.affiliation_link = affiliation
    dummy_user.affiliation = affiliation.name
    db.session.flush()
    resp = test_client.get(f'/api/v1/users/{dummy_user.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['affiliation'] == 'CERN'
    assert resp.json['affiliation_id'] == affiliation.id
    assert resp.json['affiliation_meta']['name'] == 'CERN'


def test_user_matches_legacy_api(dummy_user, token_headers, test_client, legacy_api):
    legacy = legacy_api(f'/export/user/{dummy_user.id}.json')['results'][0]
    new = test_client.get(f'/api/v1/users/{dummy_user.id}', headers=token_headers).json
    for field in legacy:
        assert new[field] == legacy[field]


def test_user_list_matches_legacy_api(dummy_user, token_headers, test_client, legacy_api):
    legacy = legacy_api(f'/export/user/{dummy_user.id}.json')['results'][0]
    results = test_client.get('/api/v1/users', headers=token_headers).json['results']
    listed = next(u for u in results if u['id'] == dummy_user.id)
    for field in legacy:
        assert listed[field] == legacy[field]
