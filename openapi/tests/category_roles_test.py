# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from operator import itemgetter

import pytest

from indico.modules.categories.models.roles import CategoryRole


@pytest.fixture
def category_manager(db, dummy_category, dummy_user):
    dummy_category.update_principal(dummy_user, full_access=True)
    db.session.flush()


@pytest.fixture
def create_category_role(db, dummy_category):
    def _create(name, code, color='5c6bc0', members=()):
        role = CategoryRole(category=dummy_category, name=name, code=code, color=color, members=set(members))
        db.session.add(role)
        db.session.flush()
        return role

    return _create


@pytest.fixture
def dummy_category_role(create_category_role, dummy_user):
    return create_category_role('Dummy role', 'DUM', members=[dummy_user])


@pytest.mark.usefixtures('category_manager')
def test_category_role_details(dummy_category, dummy_category_role, dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}/roles/{dummy_category_role.id}',
                           headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_category_role.id
    assert resp.json['category_id'] == dummy_category.id
    assert resp.json['name'] == 'Dummy role'
    assert resp.json['code'] == 'DUM'
    assert resp.json['color'] == '5c6bc0'
    assert [m['email'] for m in resp.json['members']] == [dummy_user.email]


@pytest.mark.usefixtures('category_manager')
def test_category_role_members_are_sorted(dummy_category, create_category_role, dummy_user, outsider, token_headers,
                                          test_client):
    role = create_category_role('Crowded role', 'CRW', members=[outsider, dummy_user])
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}/roles/{role.id}', headers=token_headers)
    assert [m['id'] for m in resp.json['members']] == sorted([dummy_user.id, outsider.id])


@pytest.mark.usefixtures('category_manager')
def test_category_role_list(dummy_category, dummy_category_role, create_category_role, token_headers, test_client):
    other = create_category_role('Another role', 'ANO')
    resp = test_client.get(f'/api/v1/categories/{dummy_category.id}/roles', headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [other.id, dummy_category_role.id]


def test_category_roles_are_manager_only(dummy_category, dummy_category_role, outsider_headers, test_client):
    url = f'/api/v1/categories/{dummy_category.id}/roles'
    resp = test_client.get(f'{url}/{dummy_category_role.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    assert test_client.get(url, headers=outsider_headers).status_code == 403


@pytest.mark.usefixtures('category_manager')
def test_category_role_of_another_category_is_not_found(dummy_category_role, create_category, dummy_user, db,
                                                        token_headers, test_client):
    other = create_category(1)
    other.update_principal(dummy_user, full_access=True)
    db.session.flush()
    resp = test_client.get(f'/api/v1/categories/{other.id}/roles/{dummy_category_role.id}', headers=token_headers)
    assert resp.status_code == 404


CATEGORY_ROLE_FIELDS = ('name', 'code', 'color')


def by_id(role):
    return sorted(role['members'], key=itemgetter('id'))


@pytest.mark.usefixtures('category_manager')
def test_category_role_list_matches_current_api(dummy_category, dummy_category_role, create_category_role,
                                                token_headers, test_client, indico_api, same_json_list):
    other = create_category_role('Another role', 'ANO')
    ids = {role.code: role.id for role in (dummy_category_role, other)}
    current = indico_api(f'/category/{dummy_category.id}/manage/roles/api/roles/')
    new = test_client.get(f'/api/v1/categories/{dummy_category.id}/roles', headers=token_headers).json
    # the management API serves the roles of one category, so neither the role id nor the category is in the payload
    same_json_list(new['results'], current, same=CATEGORY_ROLE_FIELDS,
                   derived={'members': by_id, 'id': lambda current: ids[current['code']],
                            'category_id': lambda _: dummy_category.id},
                   key='code')
