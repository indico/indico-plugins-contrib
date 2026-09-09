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


def test_category_details(dummy_category, token_headers, test_client):
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_category.id
    assert resp.json['title'] == dummy_category.title
    assert resp.json['chain_titles'] == dummy_category.chain_titles


def test_category_details_denied_without_access(dummy_category, dummy_personal_token, create_user, db, test_client):
    outsider = create_user(42)
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = ['read:everything']
    dummy_category.protection_mode = ProtectionMode.protected
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}', headers=headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_category_list_hides_inaccessible_categories(dummy_category, dummy_personal_token, create_user, db,
                                                     test_client):
    outsider = create_user(42)
    dummy_personal_token.user = outsider
    dummy_personal_token.scopes = ['read:everything']
    dummy_category.protection_mode = ProtectionMode.protected
    db.session.flush()
    headers = {'Authorization': f'Bearer {dummy_personal_token._plaintext_token}'}
    resp = test_client.get('/api/v1/categories', headers=headers)
    assert resp.status_code == 200
    assert dummy_category.id not in {c['id'] for c in resp.json['results']}


def test_category_list_filters_by_parent(dummy_category, token_headers, test_client):
    resp = test_client.get(f'/api/v1/categories?parent_id={dummy_category.parent_id}', headers=token_headers)
    assert {c['id'] for c in resp.json['results']} == {dummy_category.id}
