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


CATEGORY_FIELDS = ('id', 'title', 'is_protected')


def as_chain_titles(current):
    return [entry['title'] for entry in current['path']]


def as_parent_id(current):
    return current['parent_path'][-1]['id'] if current['parent_path'] else None


def test_category_matches_current_api(dummy_category, dummy_event, token_headers, test_client, indico_api, same_json):
    current = indico_api(f'/category/{dummy_category.id}/info')['category']
    new = test_client.get(f'/api/v1/categories/{dummy_category.id}', headers=token_headers).json
    same_json(new, current, same=CATEGORY_FIELDS, renamed={'deep_events_count': ('deep_event_count', None)},
              derived={'chain_titles': as_chain_titles, 'parent_id': as_parent_id})


def test_category_list_matches_current_api(dummy_category, dummy_event, create_category, token_headers, test_client,
                                           indico_api, same_json_list):
    create_category(1, title='Another category', parent=dummy_category.parent)
    parent = indico_api(f'/category/{dummy_category.parent_id}/info')
    current = parent['subcategories']
    new = test_client.get(f'/api/v1/categories?parent_id={dummy_category.parent_id}',
                          headers=token_headers).json['results']
    same_json_list(new, current, same=CATEGORY_FIELDS, renamed={'deep_events_count': ('deep_event_count', None)},
                   derived={'chain_titles': as_chain_titles, 'parent_id': as_parent_id})
