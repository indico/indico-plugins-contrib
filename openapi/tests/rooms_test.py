# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from indico.modules.rb import rb_settings


def test_room_details(dummy_room, token_headers, test_client):
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_room.id
    assert resp.json['name'] == dummy_room.name
    assert resp.json['full_name'] == dummy_room.full_name
    assert resp.json['building'] == dummy_room.building
    assert resp.json['location_name'] == dummy_room.location_name
    assert resp.json['owner_name'] == dummy_room.owner.full_name


def test_room_list(dummy_room, create_room, token_headers, test_client):
    other = create_room(building='9')
    resp = test_client.get('/api/v1/rooms', headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [dummy_room.id, other.id]


def test_room_list_filtered_by_location(dummy_room, create_location, create_room, token_headers, test_client):
    other = create_room(location=create_location('Other'))
    resp = test_client.get(f'/api/v1/rooms?location_id={other.location_id}', headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [other.id]


def test_room_equipment(db, dummy_room, create_equipment_type, token_headers, test_client):
    dummy_room.available_equipment.append(create_equipment_type('Video conference'))
    db.session.flush()
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['available_equipment'] == ['Video conference']


def test_deleted_room_is_not_found(db, dummy_room, token_headers, test_client):
    dummy_room.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}', headers=token_headers)
    assert resp.status_code == 404
    resp = test_client.get('/api/v1/rooms', headers=token_headers)
    assert resp.json['results'] == []


def test_room_requires_booking_access(dummy_room, outsider, outsider_headers, test_client):
    rb_settings.acls.add_principal('authorized_principals', dummy_room.owner)
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}', headers=outsider_headers)
    assert resp.status_code == 403
    resp = test_client.get('/api/v1/rooms', headers=outsider_headers)
    assert resp.status_code == 403


def test_room_requires_login(dummy_room, test_client):
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}')
    assert resp.status_code == 403


ROOM_FIELDS = ('id', 'name', 'full_name', 'verbose_name', 'location_id', 'location_name', 'site', 'building',
               'floor', 'number', 'division', 'capacity', 'surface_area', 'latitude', 'longitude', 'telephone',
               'key_location', 'comments', 'owner_name', 'is_public', 'is_reservable',
               'reservations_need_confirmation', 'max_advance_days', 'has_photo', 'map_url')


def as_equipment_ids(indico_api):
    ids = {eq['name']: eq['id'] for eq in indico_api('/rooms/api/equipment')}
    return lambda names: sorted(ids[name] for name in names)


def test_room_matches_current_api(db, dummy_room, create_equipment_type, token_headers, test_client, indico_api,
                                  same_json):
    dummy_room.available_equipment.append(create_equipment_type('Video conference'))
    db.session.flush()
    current = indico_api(f'/rooms/api/rooms/{dummy_room.id}')
    current['available_equipment'].sort()
    new = test_client.get(f'/api/v1/rooms/{dummy_room.id}', headers=token_headers).json
    same_json(new, current, same=ROOM_FIELDS,
              renamed={'available_equipment': ('available_equipment', as_equipment_ids(indico_api))})


def test_room_list_matches_current_api(db, dummy_room, create_room, create_equipment_type, token_headers, test_client,
                                       indico_api, same_json_list):
    dummy_room.available_equipment.append(create_equipment_type('Video conference'))
    create_room(building='9')
    db.session.flush()
    current = indico_api('/rooms/api/rooms/')
    for room in current:
        room['available_equipment'].sort()
    new = test_client.get('/api/v1/rooms', headers=token_headers).json['results']
    same_json_list(new, current, same=ROOM_FIELDS,
                   renamed={'available_equipment': ('available_equipment', as_equipment_ids(indico_api))})
