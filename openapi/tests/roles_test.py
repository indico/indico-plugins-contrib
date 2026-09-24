# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from operator import itemgetter

import pytest

from indico.modules.events.models.roles import EventRole


@pytest.fixture
def create_role(db, dummy_event):
    def _create(name, code, color='5c6bc0', members=()):
        role = EventRole(event=dummy_event, name=name, code=code, color=color, members=set(members))
        db.session.add(role)
        db.session.flush()
        return role

    return _create


@pytest.fixture
def dummy_role(create_role, dummy_user):
    return create_role('Dummy role', 'DUM', members=[dummy_user])


@pytest.mark.usefixtures('event_manager')
def test_role_details(dummy_event, dummy_role, dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/roles/{dummy_role.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_role.id
    assert resp.json['name'] == 'Dummy role'
    assert resp.json['code'] == 'DUM'
    assert resp.json['color'] == '5c6bc0'
    assert [m['email'] for m in resp.json['members']] == [dummy_user.email]


@pytest.mark.usefixtures('event_manager')
def test_role_members_are_sorted(dummy_event, create_role, dummy_user, outsider, token_headers, test_client):
    role = create_role('Crowded role', 'CRW', members=[outsider, dummy_user])
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/roles/{role.id}', headers=token_headers)
    assert [m['id'] for m in resp.json['members']] == sorted([dummy_user.id, outsider.id])


@pytest.mark.usefixtures('event_manager')
def test_role_list(dummy_event, dummy_role, create_role, token_headers, test_client):
    other = create_role('Another role', 'ANO')
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/roles', headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [other.id, dummy_role.id]


def test_roles_are_manager_only(dummy_event, dummy_role, outsider_headers, test_client):
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/roles/{dummy_role.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    resp = test_client.get(f'/api/v1/events/{dummy_event.id}/roles', headers=outsider_headers)
    assert resp.status_code == 403


@pytest.mark.usefixtures('event_manager')
def test_role_of_another_event_is_not_found(dummy_role, create_event, token_headers, test_client):
    other = create_event()
    resp = test_client.get(f'/api/v1/events/{other.id}/roles/{dummy_role.id}', headers=token_headers)
    assert resp.status_code == 404


ROLE_FIELDS = ('id', 'name', 'code', 'color')


def by_id(role):
    return sorted(role['members'], key=itemgetter('id'))


@pytest.fixture
def merged_roles(dummy_event, indico_api):
    def _merge():
        # only the management API serves the members, and only the protection API serves the id,
        # so the two payloads are zipped together on the code both of them order by
        detailed = sorted(indico_api(f'/event/{dummy_event.id}/manage/roles/api/roles/'), key=itemgetter('code'))
        basic = indico_api(f'/event/{dummy_event.id}/manage/api/event-roles')
        return [{**role, **extra} for role, extra in zip(detailed, basic, strict=True)]

    return _merge


@pytest.mark.usefixtures('event_manager')
def test_role_matches_current_api(dummy_event, dummy_role, token_headers, test_client, merged_roles, same_json):
    current = next(role for role in merged_roles() if role['id'] == dummy_role.id)
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/roles/{dummy_role.id}', headers=token_headers).json
    same_json(new, current, same=ROLE_FIELDS, derived={'members': by_id})


@pytest.mark.usefixtures('event_manager')
def test_role_list_matches_current_api(
    dummy_event, dummy_role, create_role, outsider, token_headers, test_client, merged_roles, same_json_list
):
    create_role('Another role', 'ANO', members=[outsider])
    new = test_client.get(f'/api/v1/events/{dummy_event.id}/roles', headers=token_headers).json['results']
    same_json_list(new, merged_roles(), same=ROLE_FIELDS, derived={'members': by_id})
