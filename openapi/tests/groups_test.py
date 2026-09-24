# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest


@pytest.fixture
def group_member(create_user, dummy_group):
    return create_user(50, groups=[dummy_group])


@pytest.fixture
def other_group(create_group):
    return create_group(1338, 'Another group')


def test_group_details(dummy_group, group_member, admin_headers, test_client):
    resp = test_client.get(f'/api/v1/groups/{dummy_group.id}', headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_group.id
    assert resp.json['name'] == dummy_group.name
    assert resp.json['identifier'] == f'Group::{dummy_group.id}'
    assert [m['email'] for m in resp.json['members']] == [group_member.email]


def test_group_members_are_sorted(db, dummy_group, group_member, outsider, admin_headers, test_client):
    dummy_group.group.members.add(outsider)
    db.session.flush()
    resp = test_client.get(f'/api/v1/groups/{dummy_group.id}', headers=admin_headers)
    assert [m['id'] for m in resp.json['members']] == sorted([group_member.id, outsider.id])


def test_group_list(dummy_group, other_group, admin_headers, test_client):
    resp = test_client.get('/api/v1/groups', headers=admin_headers)
    assert resp.status_code == 200
    assert [g['id'] for g in resp.json['results']] == [other_group.id, dummy_group.id]


def test_groups_are_admin_only(dummy_group, token_headers, test_client):
    resp = test_client.get(f'/api/v1/groups/{dummy_group.id}', headers=token_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get('/api/v1/groups', headers=token_headers)
    assert resp.status_code == 403


def test_unknown_group_is_not_found(dummy_group, admin_headers, test_client):
    resp = test_client.get('/api/v1/groups/9999', headers=admin_headers)
    assert resp.status_code == 404


def test_groups_are_forbidden_while_local_groups_are_disabled(
    dummy_group, admin_headers, patch_indico_config, test_client
):
    patch_indico_config('LOCAL_GROUPS', False)
    resp = test_client.get(f'/api/v1/groups/{dummy_group.id}', headers=admin_headers)
    assert resp.status_code == 403
    resp = test_client.get('/api/v1/groups', headers=admin_headers)
    assert resp.status_code == 403


GROUP_FIELDS = ('id', 'name', 'identifier')


def without_members(group):
    # the member list of a group is only ever rendered as HTML, so there is no JSON to compare it against
    return {key: value for key, value in group.items() if key != 'members'}


def test_group_matches_current_api(dummy_group, group_member, admin_headers, test_client, indico_api, same_json):
    current = indico_api(f'/groups/api/search?name={dummy_group.name}&exact=true')['groups'][0]
    new = test_client.get(f'/api/v1/groups/{dummy_group.id}', headers=admin_headers).json
    same_json(without_members(new), current, same=GROUP_FIELDS)


def test_group_list_matches_current_api(create_group, admin_headers, test_client, indico_api, same_json_list):
    create_group(1339, 'Listed group one')
    create_group(1340, 'Listed group two')
    current = indico_api('/groups/api/search?name=Listed group')['groups']
    new = test_client.get('/api/v1/groups', headers=admin_headers).json['results']
    same_json_list([without_members(group) for group in new], current, same=GROUP_FIELDS)
