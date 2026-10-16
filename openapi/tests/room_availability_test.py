# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 Unconventional
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

from datetime import datetime, time
from operator import itemgetter

import pytest

from indico.modules.rb.models.room_bookable_hours import BookableHours
from indico.modules.rb.models.room_nonbookable_periods import NonBookablePeriod


@pytest.fixture
def create_bookable_hours(db, dummy_room):
    def _create(start_time, end_time, weekday=None):
        hours = BookableHours(room=dummy_room, start_time=start_time, end_time=end_time, weekday=weekday)
        db.session.add(hours)
        db.session.flush()
        return hours

    return _create


@pytest.fixture
def create_nonbookable_period(db, dummy_room):
    def _create(start_dt, end_dt):
        period = NonBookablePeriod(room=dummy_room, start_dt=start_dt, end_dt=end_dt)
        db.session.add(period)
        db.session.flush()
        return period

    return _create


def test_bookable_hours_list(dummy_room, create_bookable_hours, token_headers, test_client):
    hours = create_bookable_hours(time(8, 30), time(18, 0), weekday='mon')
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}/bookable-hours', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [
        {'id': hours.id, 'room_id': dummy_room.id, 'start_time': '08:30:00', 'end_time': '18:00:00', 'weekday': 'mon'}
    ]


def test_bookable_hours_are_sorted(dummy_room, create_bookable_hours, token_headers, test_client):
    create_bookable_hours(time(14, 0), time(18, 0))
    create_bookable_hours(time(8, 0), time(12, 0))
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}/bookable-hours', headers=token_headers)
    assert [hours['start_time'] for hours in resp.json['results']] == ['08:00:00', '14:00:00']


def test_nonbookable_period_list(dummy_room, create_nonbookable_period, token_headers, test_client):
    create_nonbookable_period(datetime(2026, 12, 24, 0, 0), datetime(2027, 1, 2, 23, 59))
    resp = test_client.get(f'/api/v1/rooms/{dummy_room.id}/nonbookable-periods', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [
        {'room_id': dummy_room.id, 'start_dt': '2026-12-24T00:00:00', 'end_dt': '2027-01-02T23:59:00'}
    ]


def test_availability_of_a_deleted_room_is_not_found(db, dummy_room, create_bookable_hours, token_headers, test_client):
    create_bookable_hours(time(8, 0), time(18, 0))
    dummy_room.is_deleted = True
    db.session.flush()
    url = f'/api/v1/rooms/{dummy_room.id}'
    assert test_client.get(f'{url}/bookable-hours', headers=token_headers).status_code == 404
    assert test_client.get(f'{url}/nonbookable-periods', headers=token_headers).status_code == 404


as_day = itemgetter(slice(10))

BOOKABLE_HOURS_FIELDS = ('start_time', 'end_time', 'weekday')

NONBOOKABLE_PERIOD_FIELDS = ('start_dt', 'end_dt')


@pytest.mark.usefixtures('admin_headers')
def test_availability_matches_current_api(
    dummy_room, create_bookable_hours, create_nonbookable_period, token_headers, test_client, indico_api, same_json_list
):
    hours = create_bookable_hours(time(8, 30), time(18, 0), weekday='mon')
    create_nonbookable_period(datetime(2026, 12, 24, 0, 0), datetime(2027, 1, 2, 23, 59))
    # only the administration interface serves the availability of a room as stored, rather than per date
    current = indico_api(f'/rooms/api/admin/rooms/{dummy_room.id}/availability')
    url = f'/api/v1/rooms/{dummy_room.id}'
    new = test_client.get(f'{url}/bookable-hours', headers=token_headers).json
    same_json_list(
        new['results'],
        current['bookable_hours'],
        same=BOOKABLE_HOURS_FIELDS,
        derived={'id': lambda _: hours.id, 'room_id': lambda _: dummy_room.id},
        key='start_time',
    )
    new = test_client.get(f'{url}/nonbookable-periods', headers=token_headers).json
    # the administration interface only edits whole days, so it drops the time of both ends
    same_json_list(
        new['results'],
        current['nonbookable_periods'],
        renamed={'start_dt': ('start_dt', as_day), 'end_dt': ('end_dt', as_day)},
        derived={'room_id': lambda _: dummy_room.id},
        key='start_dt',
    )
