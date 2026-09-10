# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from indico.modules.rb import rb_settings


def test_location_details(dummy_location, dummy_room, token_headers, test_client):
    resp = test_client.get(f'/api/v1/locations/{dummy_location.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_location.id
    assert resp.json['name'] == dummy_location.name
    assert [r['id'] for r in resp.json['rooms']] == [dummy_room.id]
    assert resp.json['rooms'][0]['full_name'] == dummy_room.full_name


def test_location_details_sorts_rooms(dummy_location, dummy_room, create_room, token_headers, test_client):
    other = create_room(building='9')
    resp = test_client.get(f'/api/v1/locations/{dummy_location.id}', headers=token_headers)
    assert [r['id'] for r in resp.json['rooms']] == [dummy_room.id, other.id]


def test_location_details_skips_deleted_rooms(db, dummy_location, dummy_room, token_headers, test_client):
    dummy_room.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/locations/{dummy_location.id}', headers=token_headers)
    assert resp.json['rooms'] == []


def test_location_list(dummy_location, create_location, token_headers, test_client):
    other = create_location('Other')
    resp = test_client.get('/api/v1/locations', headers=token_headers)
    assert resp.status_code == 200
    assert [loc['id'] for loc in resp.json['results']] == [other.id, dummy_location.id]
    assert [loc['name'] for loc in resp.json['results']] == ['Other', 'Test']
    assert 'rooms' not in resp.json['results'][0]


def test_deleted_location_is_not_found(db, dummy_location, token_headers, test_client):
    dummy_location.is_deleted = True
    db.session.flush()
    resp = test_client.get(f'/api/v1/locations/{dummy_location.id}', headers=token_headers)
    assert resp.status_code == 404
    resp = test_client.get('/api/v1/locations', headers=token_headers)
    assert resp.json['results'] == []


def test_location_requires_booking_access(dummy_location, dummy_user, outsider_headers, test_client):
    rb_settings.acls.add_principal('authorized_principals', dummy_user)
    resp = test_client.get(f'/api/v1/locations/{dummy_location.id}', headers=outsider_headers)
    assert resp.status_code == 403
    resp = test_client.get('/api/v1/locations', headers=outsider_headers)
    assert resp.status_code == 403


def test_location_requires_login(dummy_location, test_client):
    resp = test_client.get(f'/api/v1/locations/{dummy_location.id}')
    assert resp.status_code == 403


LOCATION_FIELDS = ('id', 'name')


def test_location_matches_current_api(dummy_location, dummy_room, create_room, token_headers, test_client,
                                      indico_api, same_json):
    create_room(building='9')
    current = next(loc for loc in indico_api('/rooms/api/locations') if loc['id'] == dummy_location.id)
    new = test_client.get(f'/api/v1/locations/{dummy_location.id}', headers=token_headers).json
    same_json(new, current, same=(*LOCATION_FIELDS, 'rooms'))


def test_location_list_matches_current_api(dummy_location, dummy_room, create_location, create_room, token_headers,
                                           test_client, indico_api, same_json_list):
    create_room(location=create_location('Other'))
    current = indico_api('/rooms/api/locations')
    new = test_client.get('/api/v1/locations', headers=token_headers).json['results']
    same_json_list(new, current, same=LOCATION_FIELDS)
