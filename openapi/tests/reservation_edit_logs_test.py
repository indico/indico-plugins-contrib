# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import UTC, datetime

import pytest

from indico.modules.rb import rb_settings
from indico.modules.rb.models.reservation_edit_logs import ReservationEditLog


@pytest.fixture
def create_edit_log(db, dummy_reservation):
    def _create(info, user_name='Guinea Pig', timestamp=datetime(2026, 9, 1, 8, 0, tzinfo=UTC)):
        entry = ReservationEditLog(reservation=dummy_reservation, info=info, user_name=user_name, timestamp=timestamp)
        db.session.add(entry)
        db.session.flush()
        return entry

    return _create


def test_edit_log_list(dummy_reservation, create_edit_log, token_headers, test_client):
    entry = create_edit_log(['Booking created'])
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}/edit-logs', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [
        {
            'id': entry.id,
            'reservation_id': dummy_reservation.id,
            'timestamp': '2026-09-01T08:00:00+00:00',
            'user_name': 'Guinea Pig',
            'info': ['Booking created'],
        }
    ]


def test_edit_logs_are_sorted_oldest_first(dummy_reservation, create_edit_log, token_headers, test_client):
    create_edit_log(['Booking accepted'], timestamp=datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    create_edit_log(['Booking created'])
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}/edit-logs', headers=token_headers)
    assert [entry['info'] for entry in resp.json['results']] == [['Booking created'], ['Booking accepted']]


def test_edit_logs_follow_the_booking_details(dummy_reservation, create_edit_log, outsider_headers, test_client):
    create_edit_log(['Booking created'])
    rb_settings.set('hide_booking_details', True)
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}/edit-logs', headers=outsider_headers)
    assert resp.status_code == 403
    assert 'error' in resp.json


def test_edit_logs_of_an_unknown_booking_are_not_found(token_headers, test_client):
    assert test_client.get('/api/v1/reservations/123/edit-logs', headers=token_headers).status_code == 404


EDIT_LOG_FIELDS = ('id', 'timestamp', 'user_name', 'info')


def test_edit_log_list_matches_current_api(
    dummy_reservation, create_edit_log, token_headers, test_client, indico_api, same_json_list
):
    create_edit_log(['Booking created'])
    create_edit_log(['Booking accepted'], timestamp=datetime(2026, 9, 2, 8, 0, tzinfo=UTC))
    current = indico_api(f'/rooms/api/bookings/{dummy_reservation.id}')
    new = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}/edit-logs', headers=token_headers).json
    same_json_list(
        new['results'],
        current['edit_logs'],
        same=EDIT_LOG_FIELDS,
        derived={'reservation_id': lambda _: dummy_reservation.id},
    )
