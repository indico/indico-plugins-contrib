# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.


from datetime import date

from dateutil.relativedelta import relativedelta

from indico.modules.rb import rb_settings
from indico.modules.rb.models.reservations import RepeatFrequency


def as_legacy_dt(value):
    return f'{value["date"]}T{value["time"]}'


def test_reservation_details(dummy_reservation, dummy_room, token_headers, test_client):
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_reservation.id
    assert resp.json['room_id'] == dummy_room.id
    assert resp.json['location_name'] == dummy_room.location_name
    assert resp.json['booking_reason'] == 'Testing'
    assert resp.json['booked_for_name'] == dummy_reservation.booked_for_name
    assert resp.json['contact_email'] == dummy_reservation.contact_email
    assert resp.json['start_dt'] == dummy_reservation.start_dt.isoformat()
    assert resp.json['end_dt'] == dummy_reservation.end_dt.isoformat()
    assert resp.json['state'] == 'accepted'
    assert resp.json['is_accepted'] is True
    assert resp.json['is_pending'] is False
    assert resp.json['repeat_frequency'] == 'NEVER'
    assert resp.json['is_repeating'] is False


def test_reservation_occurrences(create_reservation, token_headers, test_client):
    reservation = create_reservation(start_dt=date.today() + relativedelta(hour=8, minute=30),
                                     end_dt=date.today() + relativedelta(days=2, hour=17, minute=30),
                                     repeat_frequency=RepeatFrequency.DAY)
    resp = test_client.get(f'/api/v1/reservations/{reservation.id}', headers=token_headers)
    assert resp.status_code == 200
    occurrences = resp.json['occurrences']
    assert [o['start_dt'] for o in occurrences] == sorted(o['start_dt'] for o in occurrences)
    assert [o['start_dt'] for o in occurrences] == [o.start_dt.isoformat() for o in reservation.occurrences]
    assert all(o['state'] == 'valid' for o in occurrences)


def test_reservation_list_has_no_occurrences(dummy_reservation, token_headers, test_client):
    resp = test_client.get('/api/v1/reservations', headers=token_headers)
    assert resp.status_code == 200
    assert 'occurrences' not in resp.json['results'][0]


def test_reservation_list(dummy_reservation, create_reservation, create_room, token_headers, test_client):
    later = create_reservation(room=create_room(building='9'),
                               start_dt=date.today() + relativedelta(days=1, hour=8, minute=30),
                               end_dt=date.today() + relativedelta(days=1, hour=17, minute=30))
    resp = test_client.get('/api/v1/reservations', headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [later.id, dummy_reservation.id]


def test_reservation_list_filtered_by_room(dummy_reservation, create_reservation, create_room, token_headers,
                                           test_client):
    other = create_reservation(room=create_room(building='9'))
    resp = test_client.get(f'/api/v1/reservations?room_id={other.room_id}', headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [other.id]


def test_reservation_list_filtered_by_date(dummy_reservation, create_reservation, create_room, token_headers,
                                           test_client):
    tomorrow = date.today() + relativedelta(days=1)
    later = create_reservation(room=create_room(building='9'),
                               start_dt=tomorrow + relativedelta(hour=8, minute=30),
                               end_dt=tomorrow + relativedelta(hour=17, minute=30))
    resp = test_client.get(f'/api/v1/reservations?start_after={tomorrow.isoformat()}T00:00:00', headers=token_headers)
    assert resp.status_code == 200
    assert [r['id'] for r in resp.json['results']] == [later.id]
    resp = test_client.get(f'/api/v1/reservations?start_before={tomorrow.isoformat()}T00:00:00', headers=token_headers)
    assert [r['id'] for r in resp.json['results']] == [dummy_reservation.id]


def test_internal_note_only_for_room_managers(db, dummy_reservation, token_headers, test_client):
    dummy_reservation.internal_note = 'Waiting for the projector'
    db.session.flush()
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}', headers=token_headers)
    assert resp.json['internal_note'] == 'Waiting for the projector'


def test_internal_note_hidden_from_others(db, dummy_reservation, outsider_headers, test_client):
    dummy_reservation.internal_note = 'Waiting for the projector'
    db.session.flush()
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}', headers=outsider_headers)
    assert resp.status_code == 200
    assert 'internal_note' not in resp.json


def test_booking_details_hidden_from_others(dummy_reservation, outsider_headers, test_client):
    rb_settings.set('hide_booking_details', True)
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}', headers=outsider_headers)
    assert resp.status_code == 200
    assert resp.json['id'] == dummy_reservation.id
    assert resp.json['booked_for_name'] is None
    assert resp.json['contact_email'] is None


def test_booking_details_visible_to_the_booker(dummy_reservation, token_headers, test_client):
    rb_settings.set('hide_booking_details', True)
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}', headers=token_headers)
    assert resp.json['booked_for_name'] == dummy_reservation.booked_for_name
    assert resp.json['contact_email'] == dummy_reservation.contact_email


def test_reservation_requires_booking_access(dummy_reservation, outsider_headers, test_client):
    rb_settings.acls.add_principal('authorized_principals', dummy_reservation.booked_for_user)
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}', headers=outsider_headers)
    assert resp.status_code == 403
    resp = test_client.get('/api/v1/reservations', headers=outsider_headers)
    assert resp.status_code == 403


def test_reservation_requires_login(dummy_reservation, test_client):
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}')
    assert resp.status_code == 403


def test_reservation_matches_indico_api(dummy_reservation, dummy_room, token_headers, test_client, indico_api):
    legacy = indico_api(f'/export/reservation/{dummy_room.location_name}.json')['results'][0]
    new = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}', headers=token_headers).json
    assert new['id'] == legacy['id']
    assert new['start_dt'] == as_legacy_dt(legacy['startDT'])
    assert new['end_dt'] == as_legacy_dt(legacy['endDT'])
    assert new['booking_reason'] == legacy['reason']
    assert new['booked_for_name'] == legacy['bookedForName']
    assert new['contact_email'] == legacy['booked_for_user_email']
    assert new['external_details_url'] == legacy['bookingUrl']
    assert new['location_name'] == legacy['location']
    assert new['is_accepted'] == legacy['isConfirmed']
    assert new['is_cancelled'] == legacy['is_cancelled']
    assert new['is_rejected'] == legacy['is_rejected']
    assert new['repeat_frequency'] == legacy['repeat_frequency']
    assert new['repeat_interval'] == legacy['repeat_interval']


def test_reservation_list_matches_indico_api(dummy_reservation, dummy_room, create_reservation, create_room,
                                             token_headers, test_client, indico_api):
    create_reservation(room=create_room(building='9'))
    legacy = {r['id']: r for r in indico_api(f'/export/reservation/{dummy_room.location_name}.json')['results']}
    results = test_client.get('/api/v1/reservations', headers=token_headers).json['results']
    assert {r['id'] for r in results} == set(legacy)
    for booking in results:
        assert booking['start_dt'] == as_legacy_dt(legacy[booking['id']]['startDT'])
        assert booking['booking_reason'] == legacy[booking['id']]['reason']
        assert booking['booked_for_name'] == legacy[booking['id']]['bookedForName']
        assert booking['location_name'] == legacy[booking['id']]['location']
