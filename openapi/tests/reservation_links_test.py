# This file is part of the third-party Indico plugins.
# Copyright (C) 2026 CERN
#
# The third-party Indico plugins are free software; you can
# redistribute them and/or modify them under the terms of the;
# MIT License see the LICENSE file for more details.

import re
from datetime import date, datetime, time, timedelta

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.rb.models.reservations import RepeatFrequency


@pytest.fixture
def linked_reservation(db, dummy_reservation, dummy_event):
    dummy_reservation.occurrences[0].linked_object = dummy_event
    db.session.flush()
    return dummy_reservation


@pytest.fixture
def booking_of_every_type(db, create_reservation, dummy_event, dummy_contribution, dummy_session_block):
    today = date.today()
    reservation = create_reservation(
        start_dt=datetime.combine(today, time(8, 30)),
        end_dt=datetime.combine(today + timedelta(days=2), time(17, 30)),
        repeat_frequency=RepeatFrequency.DAY,
    )
    for occurrence, obj in zip(
        reservation.occurrences, (dummy_event, dummy_contribution, dummy_session_block), strict=True
    ):
        occurrence.linked_object = obj
    db.session.flush()
    return reservation


def test_reservation_link_list(linked_reservation, dummy_event, token_headers, test_client):
    occurrence = linked_reservation.occurrences[0]
    resp = test_client.get(f'/api/v1/reservations/{linked_reservation.id}/links', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == [
        {
            'id': occurrence.link.id,
            'type': 'event',
            'event_id': dummy_event.id,
            'contribution_id': None,
            'session_block_id': None,
            'title': dummy_event.title,
            'occurrence_start_dt': occurrence.start_dt.isoformat(),
            'occurrence_state': 'valid',
        }
    ]


def test_reservation_without_links(dummy_reservation, token_headers, test_client):
    resp = test_client.get(f'/api/v1/reservations/{dummy_reservation.id}/links', headers=token_headers)
    assert resp.status_code == 200
    assert resp.json['results'] == []


def test_restricted_linked_object_keeps_its_title(db, linked_reservation, dummy_event, outsider_headers, test_client):
    dummy_event.protection_mode = ProtectionMode.protected
    db.session.flush()
    resp = test_client.get(f'/api/v1/reservations/{linked_reservation.id}/links', headers=outsider_headers)
    assert resp.status_code == 200
    assert [link['title'] for link in resp.json['results']] == [None]
    assert [link['event_id'] for link in resp.json['results']] == [dummy_event.id]


def test_links_of_an_unknown_booking_are_not_found(token_headers, test_client):
    assert test_client.get('/api/v1/reservations/123/links', headers=token_headers).status_code == 404


def test_links_of_every_type(
    booking_of_every_type, dummy_event, dummy_contribution, dummy_session_block, token_headers, test_client
):
    resp = test_client.get(f'/api/v1/reservations/{booking_of_every_type.id}/links', headers=token_headers)
    assert resp.status_code == 200
    links = resp.json['results']
    assert [link['type'] for link in links] == ['event', 'contribution', 'session_block']
    assert [link['event_id'] for link in links] == [dummy_event.id] * 3
    assert [link['contribution_id'] for link in links] == [None, dummy_contribution.id, None]
    assert [link['session_block_id'] for link in links] == [None, None, dummy_session_block.id]
    assert [link['title'] for link in links] == [
        dummy_event.title,
        dummy_contribution.title,
        dummy_session_block.full_title,
    ]


LINK_FIELDS = ('id', 'type')

LINK_KEYS = {'occurrence_start_dt': 'start_dt', 'occurrence_state': 'state'}


def _id_in(url, pattern):
    match = re.search(pattern, url)
    return int(match.group(1)) if match else None


def link_derived(ours):
    # the current API nests the linked object itself, which carries the title of the object and, in its URLs, the
    # id of the event and of the contribution. A session block is linked to through its session, so its own id is
    # nowhere in the payload and the only thing left to compare it against is what this API answers
    block_ids = {link['id']: link['session_block_id'] for link in ours}
    return {
        'event_id': lambda current: _id_in(current['object']['event_url'], r'/event/(\d+)'),
        'contribution_id': lambda current: _id_in(current['object']['url'], r'/contributions/(\d+)'),
        'session_block_id': lambda current: block_ids[current['id']],
        'title': lambda current: current['object']['title'],
    }


def test_reservation_link_list_matches_current_api(
    booking_of_every_type, token_headers, test_client, indico_api, same_json_list
):
    current = indico_api(f'/rooms/api/bookings/{booking_of_every_type.id}/links')
    new = test_client.get(f'/api/v1/reservations/{booking_of_every_type.id}/links', headers=token_headers).json
    same_json_list(new['results'], current, same=LINK_FIELDS, renamed=LINK_KEYS, derived=link_derived(new['results']))
