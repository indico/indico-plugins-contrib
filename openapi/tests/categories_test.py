# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from indico.core.db.sqlalchemy.protection import ProtectionMode


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


def test_category_matches_legacy_api(dummy_category, dummy_event, token_headers, test_client, legacy_api):
    legacy = legacy_api(f'/export/categ/{dummy_category.id}.json')
    path = legacy['additionalInfo']['eventCategories'][0]['path']
    entry = next(p for p in path if p.get('id') == dummy_category.id)
    new = test_client.get(f'/api/v1/categories/{dummy_category.id}', headers=token_headers).json
    assert new['title'] == entry['name']
    assert new['url'] == entry['url']
    assert new['chain_titles'] == [p['name'] for p in path if 'name' in p]


def test_category_events_match_legacy_api(dummy_category, dummy_event, token_headers, test_client, legacy_api):
    legacy = legacy_api(f'/export/categ/{dummy_category.id}.json')['results']
    new = test_client.get(f'/api/v1/events?category_id={dummy_category.id}', headers=token_headers).json
    assert {str(e['id']) for e in new['results']} == {e['id'] for e in legacy}
