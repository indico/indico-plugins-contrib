# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest


@pytest.fixture
def room_attributes(db, dummy_room, create_room_attribute):
    def _set(**values):
        attributes = {}
        for name, value in values.items():
            attributes[name] = create_room_attribute(name)
            dummy_room.set_attribute_value(name, value)
        db.session.flush()
        return attributes

    return _set


def test_room_attribute_list(dummy_room, room_attributes, token_headers, test_client):
    attributes = room_attributes(notes='Ask at the front desk')
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}/attributes', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [
        {
            'attribute_id': attributes['notes'].id,
            'name': 'notes',
            'title': 'notes',
            'value': 'Ask at the front desk',
            'is_hidden': False,
        }
    ]


def test_room_attributes_are_sorted_by_name(dummy_room, room_attributes, token_headers, test_client):
    room_attributes(notes='Ask at the front desk', manager='Some Manager')
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}/attributes', headers=token_headers)
    assert [attr['name'] for attr in resp.json['results']] == ['manager', 'notes']


def test_hidden_room_attributes_are_kept_from_other_users(
    db, dummy_room, room_attributes, outsider_headers, test_client
):
    attributes = room_attributes(notes='Ask at the front desk', code='1234')
    attributes['code'].is_hidden = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}/attributes', headers=outsider_headers)
    assert [attr['name'] for attr in resp.json['results']] == ['notes']


def test_room_managers_see_the_hidden_attributes(db, dummy_room, room_attributes, token_headers, test_client):
    attributes = room_attributes(notes='Ask at the front desk', code='1234')
    attributes['code'].is_hidden = True
    db.session.flush()
    # the room is owned by the user the token belongs to
    listed = test_client.get(f'/api/v1/rooms/{dummy_room.id}/attributes', headers=token_headers).json['results']
    assert [attr['name'] for attr in listed] == ['code', 'notes']
    assert listed[0]['is_hidden']


def test_room_attributes_of_a_deleted_room_are_not_found(db, dummy_room, room_attributes, token_headers, test_client):
    room_attributes(notes='Ask at the front desk')
    dummy_room.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}/attributes', headers=token_headers)
    assert resp.status_code == 404


ATTRIBUTE_FIELDS = ('name', 'title', 'value')


def test_room_attribute_list_matches_current_api(
    dummy_room, room_attributes, token_headers, test_client, indico_api, same_json_list
):
    attributes = room_attributes(notes='Ask at the front desk', manager='Some Manager')
    current = indico_api(f'/rooms/api/rooms/{dummy_room.id}/attributes')
    new = test_client.get(f'/api/v1/rooms/{dummy_room.id}/attributes', headers=token_headers).json
    # the current API drops the hidden attributes for everybody, so it never has to say which ones they are
    same_json_list(
        new['results'],
        current,
        same=ATTRIBUTE_FIELDS,
        derived={'attribute_id': lambda current: attributes[current['name']].id, 'is_hidden': lambda _: False},
        key='name',
    )
