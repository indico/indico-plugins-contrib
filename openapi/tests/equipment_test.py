# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import pytest

from indico.modules.rb import rb_settings
from indico.modules.rb.models.room_features import RoomFeature


@pytest.fixture
def create_room_feature(db):
    def _create(name, title, icon=''):
        feature = RoomFeature(name=name, title=title, icon=icon)
        db.session.add(feature)
        db.session.flush()
        return feature

    return _create


@pytest.fixture
def dummy_room_feature(create_room_feature):
    return create_room_feature('vc', 'Videoconference', icon='videocam')


@pytest.fixture
def dummy_equipment_type(db, create_equipment_type, dummy_room_feature):
    equipment = create_equipment_type('Webcam')
    equipment.features.append(dummy_room_feature)
    db.session.flush()
    return equipment


def test_equipment_type_details(dummy_equipment_type, dummy_room_feature, token_headers, test_client):
    resp = test_client.get(f'/api/v1/equipment-types/{dummy_equipment_type.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {
        'id': dummy_equipment_type.id,
        'name': 'Webcam',
        'used': False,
        'features': [{'id': dummy_room_feature.id, 'name': 'vc', 'title': 'Videoconference', 'icon': 'videocam'}],
    }


def test_equipment_type_list_is_sorted_by_name(dummy_equipment_type, create_equipment_type, token_headers, test_client):
    other = create_equipment_type('Blackboard')
    resp = test_client.get('/api/v1/equipment-types', headers=token_headers)
    assert resp.status_code == 200
    assert [equipment['id'] for equipment in resp.json['results']] == [other.id, dummy_equipment_type.id]


def test_equipment_type_is_used_while_a_room_has_it(db, dummy_equipment_type, dummy_room, token_headers, test_client):
    dummy_room.available_equipment.append(dummy_equipment_type)
    db.session.flush()
    assert test_client.get('/api/v1/equipment-types', headers=token_headers).json['results'][0]['used']
    dummy_room.is_deleted = True
    db.session.flush()
    assert not test_client.get('/api/v1/equipment-types', headers=token_headers).json['results'][0]['used']


def test_room_feature_details(dummy_room_feature, token_headers, test_client):
    resp = test_client.get(f'/api/v1/room-features/{dummy_room_feature.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json == {'id': dummy_room_feature.id, 'name': 'vc', 'title': 'Videoconference', 'icon': 'videocam'}


def test_room_feature_list_is_sorted_by_title(dummy_room_feature, create_room_feature, token_headers, test_client):
    other = create_room_feature('blackboard', 'Blackboard')
    resp = test_client.get('/api/v1/room-features', headers=token_headers)
    assert resp.status_code == 200
    assert [feature['id'] for feature in resp.json['results']] == [other.id, dummy_room_feature.id]


def test_equipment_requires_booking_access(
    dummy_equipment_type, dummy_room_feature, dummy_user, outsider_headers, test_client
):
    rb_settings.acls.add_principal('authorized_principals', dummy_user)
    assert test_client.get('/api/v1/equipment-types', headers=outsider_headers).status_code == 403
    assert test_client.get('/api/v1/room-features', headers=outsider_headers).status_code == 403
    resp = test_client.get(f'/api/v1/equipment-types/{dummy_equipment_type.id}', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json
    assert (
        test_client.get(f'/api/v1/room-features/{dummy_room_feature.id}', headers=outsider_headers).status_code == 403
    )


EQUIPMENT_TYPE_FIELDS = ('id', 'name', 'used', 'features')
ROOM_FEATURE_FIELDS = ('id', 'name', 'title', 'icon')


def test_equipment_type_list_matches_current_api(
    db, dummy_equipment_type, create_equipment_type, dummy_room, token_headers, test_client, indico_api, same_json_list
):
    create_equipment_type('Blackboard')
    dummy_room.available_equipment.append(dummy_equipment_type)
    db.session.flush()
    current = indico_api('/rooms/api/equipment')
    new = test_client.get('/api/v1/equipment-types', headers=token_headers).json
    same_json_list(new['results'], current, same=EQUIPMENT_TYPE_FIELDS)


def test_room_feature_list_matches_current_api(
    dummy_room_feature, create_room_feature, admin_headers, test_client, indico_api, same_json_list
):
    create_room_feature('blackboard', 'Blackboard')
    # the interface only lists the features in the administration area, while every user of the room booking
    # system already gets them next to the equipment they belong to
    current = indico_api('/rooms/api/admin/features')
    new = test_client.get('/api/v1/room-features', headers=admin_headers).json
    same_json_list(new['results'], current, same=ROOM_FEATURE_FIELDS)
