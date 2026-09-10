# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from indico.modules.rb import rb_settings
from indico.modules.rb.models.blocked_rooms import BlockedRoom, BlockedRoomState


def test_blocking_details(dummy_blocking, dummy_room, dummy_user, token_headers, test_client):
    resp = test_client.get(f'/api/v1/blockings/{dummy_blocking.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_blocking.id
    assert resp.json['reason'] == dummy_blocking.reason
    assert resp.json['start_date'] == dummy_blocking.start_date.isoformat()
    assert resp.json['end_date'] == dummy_blocking.end_date.isoformat()
    assert resp.json['created_by'] == dummy_user.full_name
    assert resp.json['allowed'] == []
    assert [r['room']['id'] for r in resp.json['blocked_rooms']] == [dummy_room.id]
    assert resp.json['blocked_rooms'][0]['state'] == 'pending'
    assert resp.json['blocked_rooms'][0]['rejection_reason'] is None


def test_blocking_allowed_principals(db, dummy_blocking, dummy_user, token_headers, test_client):
    dummy_blocking.allowed = {dummy_user}
    db.session.flush()
    resp = test_client.get(f'/api/v1/blockings/{dummy_blocking.id}', headers=token_headers)
    assert resp.json['allowed'] == [dummy_user.identifier]


def test_blocking_sorts_blocked_rooms(db, dummy_blocking, dummy_room, create_room, token_headers, test_client):
    other = create_room(building='9')
    dummy_blocking.blocked_rooms.append(BlockedRoom(room=other))
    db.session.flush()
    resp = test_client.get(f'/api/v1/blockings/{dummy_blocking.id}', headers=token_headers)
    assert [r['room']['id'] for r in resp.json['blocked_rooms']] == [dummy_room.id, other.id]


def test_rejected_blocked_room(db, dummy_blocking, token_headers, test_client):
    blocked_room = dummy_blocking.blocked_rooms[0]
    blocked_room.state = BlockedRoomState.rejected
    blocked_room.rejected_by = 'Some Manager'
    blocked_room.rejection_reason = 'The room is needed'
    db.session.flush()
    resp = test_client.get(f'/api/v1/blockings/{dummy_blocking.id}', headers=token_headers)
    assert resp.json['blocked_rooms'][0]['state'] == 'rejected'
    assert resp.json['blocked_rooms'][0]['rejected_by'] == 'Some Manager'
    assert resp.json['blocked_rooms'][0]['rejection_reason'] == 'The room is needed'


def test_blocking_list(dummy_blocking, create_blocking, token_headers, test_client):
    other = create_blocking(reason='Maintenance')
    resp = test_client.get('/api/v1/blockings', headers=token_headers)
    assert resp.status_code == 200
    assert [b['id'] for b in resp.json['results']] == [dummy_blocking.id, other.id]


def test_blocking_list_filtered_by_room(dummy_blocking, dummy_room, create_blocking, create_room, token_headers,
                                        test_client):
    create_blocking(room=create_room(building='9'))
    resp = test_client.get(f'/api/v1/blockings?room_id={dummy_room.id}', headers=token_headers)
    assert [b['id'] for b in resp.json['results']] == [dummy_blocking.id]


def test_blocking_requires_booking_access(dummy_blocking, dummy_user, outsider_headers, test_client):
    rb_settings.acls.add_principal('authorized_principals', dummy_user)
    resp = test_client.get(f'/api/v1/blockings/{dummy_blocking.id}', headers=outsider_headers)
    assert resp.status_code == 403
    resp = test_client.get('/api/v1/blockings', headers=outsider_headers)
    assert resp.status_code == 403


def test_blocking_requires_login(dummy_blocking, test_client):
    resp = test_client.get(f'/api/v1/blockings/{dummy_blocking.id}')
    assert resp.status_code == 403


BLOCKING_FIELDS = ('id', 'start_date', 'end_date', 'reason', 'created_by', 'allowed', 'blocked_rooms')


def test_blocking_matches_current_api(dummy_blocking, token_headers, test_client, indico_api, same_json):
    current = indico_api(f'/rooms/api/blockings/{dummy_blocking.id}')
    new = test_client.get(f'/api/v1/blockings/{dummy_blocking.id}', headers=token_headers).json
    same_json(new, current, same=BLOCKING_FIELDS)


def test_blocking_list_matches_current_api(dummy_blocking, create_blocking, token_headers, test_client, indico_api,
                                           same_json_list):
    create_blocking(reason='Maintenance')
    current = indico_api('/rooms/api/blockings/?timeframe=recent')
    new = test_client.get('/api/v1/blockings', headers=token_headers).json['results']
    same_json_list(new, current, same=BLOCKING_FIELDS)
